"""Stage provider-only environment edits without changing process-global configuration."""

import asyncio
import copy
import logging
from collections.abc import Mapping
from contextlib import asynccontextmanager
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bot import MaxwellBot
    from providers import OpenAICompatibleProvider

from dotenv.parser import parse_stream
from dotenv.variables import parse_variables

from provider_settings import parse_provider_settings

logger = logging.getLogger(__name__)


def provider_environment(text: str, inherited: Mapping[str, str]) -> dict[str, str]:
    """Resolve dotenv against the pre-load environment, preserving bare and blank keys."""
    parsed: dict[str, str | None] = {}
    for binding in parse_stream(StringIO(text)):
        if binding.error:
            raise ValueError("Invalid environment file syntax")
        if binding.key is not None:
            value = binding.value
            if value is not None:
                scope = {**inherited, **parsed}
                value = "".join(atom.resolve(scope) for atom in parse_variables(value))
            parsed[binding.key] = value
    return {**inherited, **{key: value for key, value in parsed.items() if value is not None}}


class ProviderReload:
    """Keep pending edits separate from the last provider configuration actually applied."""

    def __init__(self, path: Path, inherited: Mapping[str, str], applied: dict[str, object]):
        self.path = path
        self.inherited = dict(inherited)
        self.applied = applied.copy()
        self.pending: dict[str, object] | None = None
        self.checked: tuple[int, int, int, int] | None = None
        self.status = "unchanged"
        self.generation = 1

    def poll(self) -> dict[str, object] | None:
        """Read a stable file version; reject incomplete edits without exposing their values."""
        try:
            stat = self.path.stat()
            stamp = (stat.st_ino, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
            if stamp != self.checked:
                text = self.path.read_text(encoding="utf-8")
                after = self.path.stat()
                if stamp != (after.st_ino, after.st_mtime_ns, after.st_ctime_ns, after.st_size):
                    self.pending = None
                    self.status = "editing"
                    return None
                self.checked = stamp
                candidate = parse_provider_settings(provider_environment(text, self.inherited))
                self.pending = candidate if candidate != self.applied else None
                self.status = "pending idle" if self.pending is not None else "unchanged"
        except (OSError, UnicodeError, ValueError) as error:
            self.pending = None
            if self.status != "rejected":
                logger.warning(
                    "Provider configuration reload rejected (%s); keeping active providers",
                    type(error).__name__,
                )
            self.status = "rejected"
        return self.pending

    def accept(self, settings: dict[str, object]) -> None:
        """Advance the process-local generation only after the full provider swap succeeds."""
        changed = sorted(key for key in settings if settings[key] != self.applied.get(key))
        self.applied = settings.copy()
        self.pending = None
        self.generation += 1
        self.status = "applied"
        logger.info(
            "Provider configuration applied at idle: generation %s; fields %s",
            self.generation, ", ".join(changed),
        )

    def describe(self) -> str:
        """Report applied configuration state without keys, endpoints or file contents."""
        return f"Provider configuration generation: {self.generation} | reload: {self.status}"


@asynccontextmanager
async def provider_round(bot: MaxwellBot):
    """Hold provider profiles across multi-call maintenance work, including between-call gaps."""
    bot._provider_rounds_active += 1
    try:
        yield
    finally:
        bot._provider_rounds_active -= 1


def providers_idle(bot: MaxwellBot, excluding: asyncio.Task | None = None) -> bool:
    """Require complete rounds and transport calls to finish, including between-tool gaps."""
    slots = bot.ai_slot_stats()
    tasks = [
        *bot._active_requests.values(), *bot._vc_active_tasks.values(), *bot._context_tasks,
        *bot.bg_jobs._tasks.values(),
    ]
    providers = (
        bot.ai_provider, bot.autonomy_provider, bot.aux_provider, *bot._retired_providers,
    )
    return not (
        bot._replying_channels or bot._inflight_context
        or bot._reply_queue.any_active(excluding=excluding)
        or slots["active"] or slots["waiting"] or bot.bg_jobs.active_count()
        or bot._rem_running or bot.autonomy_engine._tick_in_flight or bot._provider_rounds_active
        or any(task is not excluding and not task.done() for task in tasks)
        or any(provider is not None and provider.active_requests for provider in providers)
    )


def apply_provider_reload(bot: MaxwellBot, *, excluding: asyncio.Task | None = None) -> bool:
    """Swap validated settings synchronously at idle; no network or await can split the swap."""
    reload = getattr(bot, "_provider_reload", None)
    settings = reload.poll() if reload is not None else None
    if settings is None or not providers_idle(bot, excluding):
        return False
    candidate = copy.copy(bot.config)
    vars(candidate).update(settings)
    try:
        provider = bot._create_main_provider(candidate)
    except (TypeError, ValueError) as error:
        reload.pending = None
        reload.status = "rejected"
        logger.warning(
            "Provider replacement rejected (%s); keeping active providers", type(error).__name__,
        )
        return False
    retired = [item for item in (bot.ai_provider, bot.autonomy_provider, bot.aux_provider) if item is not None]
    vars(bot.config).update(settings)
    bot.ai_provider = provider
    bot.autonomy_provider = bot.aux_provider = None
    bot._autonomy_provider_sig = bot._aux_provider_sig = ""
    for old in retired:
        retire_provider(bot, old)
    reload.accept(settings)
    return True


def retire_provider(bot: MaxwellBot, provider: OpenAICompatibleProvider) -> None:
    """Retain displaced role/main transports for idle cleanup rather than closing in-flight calls."""
    retired = vars(bot).setdefault("_retired_providers", [])
    if all(item is not provider for item in retired):
        retired.append(provider)


async def close_retired_providers(bot: MaxwellBot, *, shutdown: bool = False) -> None:
    """Keep retired transports reachable until whole rounds and their close have finished."""
    retired = tuple(getattr(bot, "_retired_providers", ()))
    if not retired or (not shutdown and not providers_idle(bot)):
        return
    for provider in retired:
        if shutdown or not provider.active_requests:
            await provider.close()
            bot._retired_providers.remove(provider)
