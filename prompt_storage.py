"""Shared live prompt storage for the bot and admin API."""

import json
import logging
import os
from functools import lru_cache
from pathlib import Path

from control_defaults import DEFAULT_CONTROL
from utils import FileLock, _atomic_json_write_sync, _atomic_text_write_sync

logger = logging.getLogger(__name__)


class PromptStorageError(ValueError):
    pass


class PromptStore:
    def __init__(self, data_dir: Path | str, prompts_dir: Path | str = ""):
        self.external = bool(prompts_dir)
        self.personality_path = (
            Path(prompts_dir) / "personality.txt"
            if self.external else Path(data_dir) / "bot_control.json"
        )
        self.servers_path = (
            Path(prompts_dir) / "servers.json"
            if self.external else Path(data_dir) / "prompts.json"
        )
        self._personality: str | None = None
        self._servers: dict[str, str] = {}

    def read_mapping(self, path: Path) -> dict:
        try:
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except (OSError, UnicodeError) as exc:
            raise PromptStorageError(f"Cannot read {path}: {exc}; fix the file and retry") from exc
        try:
            result = json.loads(content)
        except ValueError as exc:
            raise PromptStorageError(f"Invalid JSON in {path}: {exc}; fix the file before saving") from exc
        if not isinstance(result, dict):
            raise PromptStorageError(f"{path} must contain a JSON object; fix the file before saving")
        if path == self.servers_path and not all(isinstance(v, str) for v in result.values()):
            raise PromptStorageError(f"{path} must map server IDs to strings; fix the file before saving")
        return result

    def read_servers(self, *, retain_valid: bool = False) -> dict[str, str]:
        try:
            self._servers = self.read_mapping(self.servers_path)
        except PromptStorageError as exc:
            if not retain_valid:
                raise
            logger.error("%s; retaining last valid server prompts", exc)
        return dict(self._servers)

    def set_server(self, server_id: str, text: str) -> None:
        with FileLock(self.servers_path):
            servers = self.read_mapping(self.servers_path)
            servers[str(server_id)] = text
            _atomic_json_write_sync(self.servers_path, servers)
            self._servers = servers

    def delete_server(self, server_id: str) -> bool:
        with FileLock(self.servers_path):
            servers = self.read_mapping(self.servers_path)
            existed = str(server_id) in servers
            servers.pop(str(server_id), None)
            _atomic_json_write_sync(self.servers_path, servers)
            self._servers = servers
        return existed

    def read_personality(self, *, retain_valid: bool = False) -> str:
        try:
            if self.external:
                text = self.personality_path.read_text(encoding="utf-8")
                if not text.strip():
                    raise PromptStorageError(f"{self.personality_path} is empty; provide a non-empty personality")
            else:
                text = self.read_mapping(self.personality_path).get(
                    "base_personality", DEFAULT_CONTROL["base_personality"]
                )
                if not isinstance(text, str):
                    raise PromptStorageError(f"{self.personality_path}: base_personality must be a string")
            self._personality = text
        except (OSError, UnicodeError, PromptStorageError) as exc:
            error = PromptStorageError(f"Cannot load personality from {self.personality_path}: {exc}; fix the file and retry")
            if not retain_valid or self._personality is None:
                raise error from exc
            logger.error("%s; retaining last valid personality", error)
        return self._personality

    def set_personality(self, text: str) -> None:
        if not isinstance(text, str) or not text.strip():
            raise PromptStorageError("base_personality must be a non-empty string")
        with FileLock(self.personality_path):
            if self.external:
                _atomic_text_write_sync(self.personality_path, text)
            else:
                control = self.read_mapping(self.personality_path)
                control["base_personality"] = text
                _atomic_json_write_sync(self.personality_path, control)
            self._personality = text


_cached_store = lru_cache(maxsize=32)(PromptStore)


def get_prompt_store(data_dir: Path | str, prompts_dir: str | None = None) -> PromptStore:
    directory = os.getenv("MAXWELL_PROMPTS_DIR", "").strip() if prompts_dir is None else prompts_dir
    return _cached_store(Path(data_dir).resolve(), str(Path(directory).resolve()) if directory else "")
