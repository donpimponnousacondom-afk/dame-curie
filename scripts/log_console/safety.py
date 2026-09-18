import json
import math
import re
import unicodedata
from uuid import uuid4

from error_reporting import redact_sensitive_text


type JSONValue = str | int | float | bool | None | list[JSONValue] | dict[str, JSONValue]

REDACTED = "[REDACTED]"
SENSITIVE_KEY = re.compile(
    r"(?i)(?:^|[_-])(?:auth|authorization|cookie|password|secret|token|api[_-]?key|"
    r"headers|config|configuration|env|environ|environment)(?:$|[_-])"
)
CONFIG_DUMP = re.compile(
    r'''(?i)(?:["']?\b(?:config|configuration|env|environ|environment|headers)["']?\s*[:=]\s*|server config)'''
)
PRIVATE_BEGIN = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----")
PRIVATE_END = re.compile(r"-----END (?:[A-Z0-9]+ )*PRIVATE KEY-----")
SGR = re.compile(r"\x1b\[[0-9;:]*m")
QUOTED = re.compile(r'''"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*' ''', re.VERBOSE)
JSON_KEY = re.compile(r"\s*:")


def terminal_text(text: str) -> str:
    return "".join(
        char if char in "\n\t" or unicodedata.category(char) not in {"Cc", "Cf", "Cs"}
        else (f"\\x{ord(char):02x}" if ord(char) < 256 else f"\\u{ord(char):04x}")
        for char in text
    )


def safe_fields(fields: dict[str, JSONValue]) -> dict[str, JSONValue]:
    return {
        redact_sensitive_text(key): REDACTED if SENSITIVE_KEY.search(key) else safe_value(item)
        for key, item in fields.items()
    }


def safe_value(value: JSONValue) -> JSONValue:
    result: JSONValue
    if isinstance(value, dict):
        result = safe_fields(value)
    elif isinstance(value, list):
        result = [safe_value(item) for item in value]
    elif isinstance(value, float) and not math.isfinite(value):
        result = str(value)
    else:
        result = redact_sensitive_text(value) if isinstance(value, str) else value
    return result


def safe_fallback(text: str) -> str:
    marker = "\x00" + uuid4().hex + "\x00"
    parts, tokens = [], []
    end = 0
    for match in QUOTED.finditer(text):
        try:
            value = json.loads(match[0]) if match[0].startswith('"') else match[0][1:-1]
        except json.JSONDecodeError:
            value = match[0]
        if JSON_KEY.match(text, match.end()) and SENSITIVE_KEY.search(value):
            return REDACTED
        safe = redact_sensitive_text(value)
        token = json.dumps(safe, ensure_ascii=True) if safe != value else match[0]
        parts.extend((text[end:match.start()], f"{marker}{len(tokens)}{marker}"))
        tokens.append(token)
        end = match.end()
    parts.append(text[end:])
    outside = redact_sensitive_text("".join(parts))
    return re.sub(re.escape(marker) + r"(\d+)" + re.escape(marker), lambda match: tokens[int(match[1])], outside)


class EvidenceRedactor:
    def __init__(self) -> None:
        self.private_keys: set[str | None] = set()
        self.config_depth: dict[str | None, int] = {}

    def text(self, text: str, *, service: str | None, redacted: bool = False) -> str:
        hidden = service in self.private_keys
        if service in self.config_depth or CONFIG_DUMP.search(text):
            punctuation = QUOTED.sub("", text)
            depth = self.config_depth.get(service, 0) + sum(punctuation.count(char) for char in "[{")
            depth -= sum(punctuation.count(char) for char in "]}")
            if depth > 0:
                self.config_depth[service] = depth
            else:
                self.config_depth.pop(service, None)
            hidden = True
        if PRIVATE_BEGIN.search(text):
            self.private_keys.add(service)
            hidden = True
        if PRIVATE_END.search(text):
            self.private_keys.discard(service)
        if hidden or CONFIG_DUMP.search(text):
            text = REDACTED
        elif not redacted:
            text = redact_sensitive_text(text)
        return text

    def message(self, text: str, *, service: str | None) -> str:
        structured = None
        if text.startswith(("{", "[")):
            structured = json.loads(text)
        if isinstance(structured, (dict, list)) and service not in self.private_keys and service not in self.config_depth:
            result = json.dumps(safe_value(structured), ensure_ascii=True)
        else:
            result = self.text(text, service=service)
        return result
