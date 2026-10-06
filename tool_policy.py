"""Actor authorization shared by catalog selection and tool execution."""

from typing import Protocol

from discord import Message


class ToolAuthority(Protocol):
    """The bot's existing administrator and shell-allowlist contract."""

    _shell_whitelist: set[str]

    def _is_admin(self, user_id: int) -> bool: ...


def tool_authorized(bot: ToolAuthority | None, message: Message | None, name: str) -> bool:
    """Fail closed for privileged tools when the permission actor is unavailable."""
    if name not in {"shell", "join_server", "update_base_personality", "update_server_prompt"}:
        return True
    actor_id = getattr(getattr(message, "author", None), "id", None)
    check_admin = getattr(bot, "_is_admin", None)
    allowed = actor_id is not None and check_admin is not None and check_admin(actor_id)
    if name == "shell" and actor_id is not None:
        allowed = allowed or str(actor_id) in getattr(bot, "_shell_whitelist", ())
    return bool(allowed)
