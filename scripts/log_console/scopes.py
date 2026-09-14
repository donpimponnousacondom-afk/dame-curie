import re

from .recognizers import Envelope, Recognition


SCOPE_KEYS = {"s": "system", "b": "bot", "p": "provider", "d": "discord", "t": "tool",
              "c": "context", "w": "web", "a": "subagent"}
LOGGER_SCOPES = (
    ("jobs", "subagent"), ("discord", "discord"), ("providers", "provider"),
    ("provider_telemetry", "provider"), ("aiohttp", "provider"), ("httpx", "provider"),
    ("bot_tools", "tool"), ("tool_registry", "tool"), ("tool_schemas", "tool"),
    ("rag_memory", "context"), ("prompt_storage", "context"),
    ("api", "web"), ("site_server", "web"), ("docker_runtime", "system"), ("bot", "bot"),
)
SERVICE_SCOPES = (
    (re.compile(r"(?:^|[-_])ollama(?:[-_]pull)?(?:[-_]\d+)?$"), "provider"),
    (re.compile(r"(?:^|[-_])(?:api|web)(?:[-_]\d+)?$"), "web"),
    (re.compile(r"(?:^|[-_])bot(?:[-_]\d+)?$"), "bot"),
)
TOOL_DISPATCH = re.compile(r"^(?:Executing tool \w+$|Tool \w+ finished: |Tool execution error for \w+: )")


def metadata_scope(envelope: Envelope, service: str | None) -> Recognition:
    logger = envelope.logger or ""
    scope = next((scope for prefix, scope in LOGGER_SCOPES if logger == prefix or logger.startswith(prefix + ".")), None)
    if scope is None:
        scope = next((scope for pattern, scope in SERVICE_SCOPES if pattern.search(service or "")), "system")
    if logger in {"bot", "__main__"} and scope == "bot" and TOOL_DISPATCH.match(envelope.message):
        scope = "tool"
    return Recognition("text", scope)
