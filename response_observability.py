"""Per-call Discord presentation, delivered-message measurements, and build identity."""

from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import time
from urllib.parse import urlsplit

from provider_telemetry import CallMetrics
from utils import FileLock, _atomic_json_write_sync


FOOTER_MARKER = "\u2063\u2060\u2063\u2060"
DEFAULT_FOOTER_FORMAT = "TTFT {{TTFT}} | TPS {{TPS}}"
FOOTER_TOKENS = frozenset({"TTFT", "TPS", "PROVIDER", "CONTEXT", "MODEL", "BOT"})


def update_footer_control(path: Path, key: str, value: str | bool) -> None:
    with FileLock(path):
        control = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        if not isinstance(control, dict):
            raise TypeError("Control file must contain a JSON object")
        control[key] = value
        _atomic_json_write_sync(path, control)


def footer_template_error(template: str) -> str | None:
    error = None
    if not template.strip() or len(template) > 300 or len(template.splitlines()) != 1:
        error = "footer format must be one nonempty line, at most 300 characters"
    elif (
        any(c in template for c in "\r\n\x85\u2028\u2029") or FOOTER_MARKER in template
    ):
        error = "footer format must be one line without the reserved footer marker"
    elif set(re.findall(r"\{\{(.*?)\}\}", template)) - FOOTER_TOKENS:
        error = "unknown footer token; use {{TTFT}} {{TPS}} {{PROVIDER}} {{CONTEXT}} {{MODEL}} {{BOT}}"
    return error


def render_footer(
    template: str,
    metrics: CallMetrics | None,
    bot_name: str,
    *,
    code_block: bool = False,
) -> str:
    values = dict.fromkeys(FOOTER_TOKENS, "—")
    values["BOT"] = bot_name
    if metrics is not None:
        values.update(
            {
                "TTFT": "n/a"
                if metrics.ttft_ms is None
                else f"{'~' if metrics.ttft_estimated else ''}{metrics.ttft_ms:.0f}ms",
                "TPS": "n/a"
                if metrics.tps is None
                else f"{'~' if metrics.estimated else ''}{metrics.tps:.1f}",
                "PROVIDER": metrics.provider,
                "CONTEXT": f"{'~' if metrics.input_source != 'provider' else ''}{metrics.input_tokens}",
                "MODEL": metrics.model,
            }
        )
    rendered = re.sub(r"\{\{(.*?)\}\}", lambda match: str(values[match[1]]), template)
    rendered = (
        " ".join(rendered.split()).replace(FOOTER_MARKER, "").replace("@", "@\u200b")
    )
    prefix = "" if code_block else "-# "
    if code_block:
        rendered = re.sub(r"`(?=`)", "`\u200b", rendered)
    return prefix + rendered[: 300 - len(prefix) - len(FOOTER_MARKER)] + FOOTER_MARKER


def strip_footer(text: str, *, self_authored: bool) -> str:
    fenced = text.startswith("```\n") and text.endswith("\n```")
    body, separator, last_line = (text[:-4] if fenced else text).rpartition("\n")
    if (
        self_authored
        and separator
        and (fenced or last_line.startswith("-# "))
        and last_line.endswith(FOOTER_MARKER)
    ):
        return body + "\n```" if fenced else body
    return text


def footer_text(text: str) -> str:
    if strip_footer(text, self_authored=True) == text:
        return ""
    body = text[:-4] if text.startswith("```\n") and text.endswith("\n```") else text
    return body.rpartition("\n")[2].removesuffix(FOOTER_MARKER).removeprefix("-# ")


def discord_message_excerpt(message, limit: int = 150) -> str:
    text = str(getattr(message, "content", "") or "")
    body = strip_footer(text, self_authored=True).replace(FOOTER_MARKER, "")
    excerpt = body[:limit] + ("..." if len(body) > limit else "")
    footer = footer_text(text)
    return excerpt + (f"\n[Message footer: {footer}]" if footer else "")


def latest_delivered_footer(bot, channel_id: str) -> str:
    for (cid, mid), text in reversed(getattr(bot, "_delivered_footers", {}).items()):
        if cid == str(channel_id):
            return f"[Runtime-added footer on your Discord message {mid}: {text}]"
    return ""


def clean_message_content(bot, message, content: str | None = None) -> str:
    text = str(getattr(message, "content", "") or "") if content is None else content
    own_id = str(getattr(getattr(bot, "user", None), "id", "") or "")
    author_id = str(getattr(getattr(message, "author", None), "id", "") or "")
    return strip_footer(text, self_authored=bool(own_id and author_id == own_id))


def prepare_delivery(
    bot,
    text: str,
    metrics: CallMetrics | None,
    splitter=None,
    *,
    platform: str = "discord",
    limit: int = 1900,
    unmeasured: bool = False,
    code_block: bool = False,
) -> tuple[list[str], list[str]]:
    control = getattr(bot, "_control", {}) or {}
    footer = ""
    if (
        (metrics is not None or unmeasured)
        and platform == "discord"
        and control.get("footer_enabled", True)
    ):
        template = control.get("footer_format", DEFAULT_FOOTER_FORMAT)
        if not isinstance(template, str) or footer_template_error(template):
            template = DEFAULT_FOOTER_FORMAT
        footer = render_footer(
            template,
            metrics,
            str(getattr(bot, "bot_name", "Maxwell")),
            code_block=code_block,
        )
    limit = min(limit, 2000 - len(footer) - 1) if footer else limit
    if code_block:
        text = re.sub(r"`(?=`)", "`\u200b", text)
        limit = min(limit, 2000) - 8
    clean_chunks = (
        splitter(text, limit=limit)
        if splitter is not None
        else [text[i : i + limit] for i in range(0, len(text), limit)]
    )
    wire_chunks = list(clean_chunks)
    if footer and wire_chunks and wire_chunks[-1]:
        wire_chunks[-1] += "\n" + footer
    if code_block:
        clean_chunks = [f"```\n{chunk}\n```" for chunk in clean_chunks]
        wire_chunks = [f"```\n{chunk}\n```" for chunk in wire_chunks]
    return clean_chunks, wire_chunks


async def send_measured(bot, channel, text: str, metrics: CallMetrics | None) -> None:
    _, chunks = prepare_delivery(
        bot, text, metrics, getattr(bot, "_split_response", None)
    )
    for chunk in chunks:
        sent = await channel.send(chunk)
        record_delivery(bot, getattr(sent, "channel", channel), sent, metrics)


async def send_command_response(
    bot,
    channel,
    text: str,
    *,
    allowed_mentions,
    code_block: bool = False,
    unmeasured: bool = True,
) -> None:
    _, chunks = prepare_delivery(
        bot,
        text,
        None,
        getattr(bot, "_split_response", None),
        unmeasured=unmeasured,
        code_block=code_block,
    )
    for chunk in chunks:
        sent = await channel.send(chunk, allowed_mentions=allowed_mentions)
        record_delivery(bot, channel, sent, None)


class MeasuredActions(list[dict]):
    def __init__(self, actions: list[dict], metrics: CallMetrics | None):
        super().__init__(actions)
        self.metrics = metrics


class DeliveryMeasurements:
    def __init__(self, limit: int = 1024):
        self.limit = limit
        self.records: OrderedDict[tuple[str, str], CallMetrics] = OrderedDict()

    def record(self, channel_id: str, message_id: str, metrics: CallMetrics) -> None:
        key = (str(channel_id), str(message_id))
        self.records[key] = metrics
        self.records.move_to_end(key)
        while len(self.records) > self.limit:
            self.records.popitem(last=False)

    def lookup(
        self, channel_id: str, message_id: str | None = None
    ) -> tuple[str, CallMetrics] | None:
        for (cid, mid), metrics in reversed(self.records.items()):
            if cid == str(channel_id) and (
                message_id is None or mid == str(message_id)
            ):
                return mid, metrics
        return None


def record_delivered_footer(bot, channel, sent_message, *, replace: bool = False) -> None:
    message_id = getattr(sent_message, "id", None)
    channel_id = getattr(channel, "id", None)
    if message_id is None or channel_id is None:
        return
    key = (str(channel_id), str(message_id))
    footers = getattr(bot, "_delivered_footers", None)
    if replace and footers is not None:
        footers.pop(key, None)
    delivered_footer = footer_text(str(getattr(sent_message, "content", "") or ""))
    if delivered_footer:
        if footers is None:
            footers = bot._delivered_footers = OrderedDict()
        footers[key] = delivered_footer
        footers.move_to_end(key)
        while len(footers) > 1024:
            footers.popitem(last=False)


def record_delivery(
    bot,
    channel,
    sent_message,
    metrics: CallMetrics | None,
    *,
    platform: str = "discord",
    replace: bool = False,
) -> None:
    message_id = getattr(sent_message, "id", None)
    channel_id = getattr(channel, "id", None)
    if platform == "discord":
        record_delivered_footer(bot, channel, sent_message, replace=replace)
    registry = getattr(bot, "_delivery_measurements", None)
    if replace and registry is not None and platform == "discord":
        registry.records.pop((str(channel_id), str(message_id)), None)
    if (
        metrics is not None
        and platform == "discord"
        and message_id is not None
        and channel_id is not None
    ):
        if registry is None:
            registry = bot._delivery_measurements = DeliveryMeasurements()
        registry.record(str(channel_id), str(message_id), metrics)


def format_runtime_provider(provider) -> str:
    lines = ["Loaded runtime configuration:"]
    if provider is None:
        lines.append("Provider not initialized.")
    else:
        for endpoint in provider._endpoints:
            if endpoint.name in ("primary", "fallback"):
                label = endpoint.name.capitalize()
                lines.extend(
                    [
                        f"{label} model: {endpoint.model}",
                        f"{label} provider: {urlsplit(endpoint.base_url).hostname or 'unknown'}",
                    ]
                )
        lines.append(
            "Per-request fallback/overrides may differ; see measurements below."
        )
    return "\n".join(lines)


def format_debug(
    registry: DeliveryMeasurements, channel_id: str, message_id: str | None = None
) -> str:
    found = registry.lookup(channel_id, message_id)
    if found is None:
        target = (
            f"message {message_id}"
            if message_id is not None
            else "a measured bot message in this channel"
        )
        return f"No measurements recorded by this process for {target}."
    mid, metrics = found
    ttft = (
        "n/a"
        if metrics.ttft_ms is None
        else f"{'~' if metrics.ttft_estimated else ''}{metrics.ttft_ms:.0f}ms"
    )
    tps = (
        "n/a"
        if metrics.tps is None
        else f"{'~' if metrics.estimated else ''}{metrics.tps:.1f} tok/s"
    )
    return "\n".join(
        [
            f"Measured bot message: {mid} (channel {channel_id})",
            f"Call: {metrics.call_id}",
            f"Model: {metrics.model}",
            f"Provider: {metrics.provider} ({metrics.endpoint})",
            f"Tokens: {metrics.input_tokens} input / {metrics.output_tokens} output; reasoning: {metrics.reasoning_tokens if metrics.reasoning_tokens is not None else 'n/a'}",
            f"Token sources: input {metrics.input_source}, output {metrics.output_source}",
            f"TTFT: {ttft} | TPS: {tps}",
            f"Request: {metrics.elapsed_ms:.0f}ms | attempt {metrics.attempt} | {'SSE' if metrics.stream else 'JSON'} | {metrics.output_bytes} output bytes",
        ]
    )


@dataclass(frozen=True)
class RunningBuild:
    commit: str
    branch: str
    date: str
    subject: str
    dirty: bool | None
    started_at: str
    python: str

    def format(self) -> str:
        dirty = "unknown" if self.dirty is None else "yes" if self.dirty else "no"
        return "\n".join(
            [
                f"Checkout at boot: {self.commit[:12]} ({self.commit})",
                f"Branch: {self.branch} | dirty at startup: {dirty}",
                f"Commit date: {self.date}",
                f"Subject: {self.subject}",
                f"Process started: {self.started_at}",
                f"Python: {self.python}",
            ]
        )


def read_startup_git_snapshot(path: str) -> dict[str, str | bool]:
    deadline = time.monotonic() + 10
    body = bytearray()
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(5)
        connection.connect(path)
        while len(body) <= 65536:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("startup Git snapshot timed out")
            connection.settimeout(remaining)
            chunk = connection.recv(min(4096, 65537 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
    if len(body) > 65536:
        raise ValueError("startup Git snapshot exceeds 64 KiB")
    snapshot = json.loads(body)
    fields = {"commit", "branch", "date", "subject", "dirty"}
    if not isinstance(snapshot, dict) or snapshot.keys() != fields:
        raise ValueError("invalid startup Git snapshot fields")
    if type(snapshot["dirty"]) is not bool or any(
        not isinstance(snapshot[field], str) for field in fields - {"dirty"}
    ):
        raise ValueError("invalid startup Git snapshot types")
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", snapshot["commit"]) or not snapshot["branch"]:
        raise ValueError("invalid startup Git commit or branch")
    date = datetime.fromisoformat(snapshot["date"])
    if date.tzinfo is None:
        raise ValueError("startup Git date has no timezone")
    snapshot["date"] = date.astimezone(timezone.utc).isoformat()
    return snapshot


def capture_running_build(root: Path) -> RunningBuild:
    started_at = datetime.now(timezone.utc).isoformat()
    socket_path = os.getenv("MAXWELL_STARTUP_GIT_SOCKET", "").strip()
    if socket_path:
        snapshot = read_startup_git_snapshot(socket_path)
        return RunningBuild(**snapshot, started_at=started_at, python=platform.python_version())
    commit = branch = date = subject = "unknown"
    dirty = None
    git = shutil.which("git")
    if git and (root / ".git").exists():
        result = subprocess.run(
            [git, "-C", str(root), "log", "-1", "--format=%H%n%cI%n%s"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            commit, date, subject = result.stdout.rstrip("\n").split("\n", 2)
            date = datetime.fromisoformat(date).astimezone(timezone.utc).isoformat()
        result = subprocess.run(
            [git, "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
        result = subprocess.run(
            [git, "-C", str(root), "status", "--porcelain", "--untracked-files=normal"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            dirty = bool(result.stdout.strip())
    return RunningBuild(
        commit, branch, date, subject, dirty, started_at, platform.python_version()
    )
