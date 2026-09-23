"""Reload-side provider settings parsing: purity, semantics and fail-closed errors.

These tests import ``provider_settings`` and nothing else -- no application
module, no event loop, no network, no dotenv file. Every environment is an
explicit mapping, which is also what proves the parser never reads
``os.environ``.
"""

import ast
import os
import traceback
from pathlib import Path

import pytest

import provider_settings
from provider_settings import PROVIDER_FIELDS, parse_provider_settings

_BASE = {
    "OPENAI_BASE_URL": "https://primary.example.test/v1",
    "OPENAI_MODEL": "primary-model",
}

_EXPECTED_FIELDS = frozenset(
    {
        "OPENAI_BASE_URL",
        "OPENAI_MODEL",
        "OPENAI_API_KEY",
        "OPENAI_COMPAT_API_KEY",
        "OPENAI_MAX_TOKENS",
        "OPENAI_TEMPERATURE",
        "OPENAI_TOP_P",
        "OPENAI_TOP_K",
        "OPENAI_DISABLE_REASONING",
        "OPENAI_EXTRA_HEADERS",
        "OPENAI_EXTRA_BODY",
        "OPENAI_RETRY_ATTEMPTS",
        "OPENAI_EMPTY_RESPONSE_RETRIES",
        "OPENAI_ENDPOINT_COOLDOWN_SECONDS",
        "OPENAI_FALLBACK_BASE_URL",
        "OPENAI_FALLBACK_API_KEY",
        "OPENAI_FALLBACK_MODEL",
        "OPENAI_FALLBACK_DISABLE_REASONING",
        "OPENAI_VISION_BASE_URL",
        "OPENAI_VISION_API_KEY",
        "OPENAI_VISION_MODEL",
        "OPENAI_VISION_DISABLE_REASONING",
        "OPENAI_REM_MODEL",
        "AUTONOMY_BASE_URL",
        "AUTONOMY_API_KEY",
        "AUTONOMY_MODEL",
        "AUTONOMY_DISABLE_REASONING",
        "AUX_BASE_URL",
        "AUX_API_KEY",
        "AUX_MODEL",
        "AUX_DISABLE_REASONING",
    }
)

_INT_FIELDS = (
    "OPENAI_MAX_TOKENS",
    "OPENAI_TOP_K",
    "OPENAI_RETRY_ATTEMPTS",
    "OPENAI_EMPTY_RESPONSE_RETRIES",
)
_FLOAT_FIELDS = (
    "OPENAI_TEMPERATURE",
    "OPENAI_TOP_P",
    "OPENAI_ENDPOINT_COOLDOWN_SECONDS",
)
_JSON_FIELDS = ("OPENAI_EXTRA_HEADERS", "OPENAI_EXTRA_BODY")
_URL_FIELDS = (
    "OPENAI_BASE_URL",
    "OPENAI_FALLBACK_BASE_URL",
    "OPENAI_VISION_BASE_URL",
    "AUTONOMY_BASE_URL",
    "AUX_BASE_URL",
)
_OPTIONAL_URL_FIELDS = tuple(
    field for field in _URL_FIELDS if field != "OPENAI_BASE_URL"
)


def parse(**overrides):
    """Parse the minimal valid environment plus ``overrides``."""
    return parse_provider_settings({**_BASE, **overrides})


# --- surface --------------------------------------------------------------


def test_returns_exactly_the_provider_field_set():
    """The parser must not silently broaden into unrelated configuration."""
    assert set(parse()) == _EXPECTED_FIELDS


def test_provider_fields_matches_the_parsed_names_and_order():
    """PROVIDER_FIELDS is the exported contract for capturing startup values."""
    assert isinstance(PROVIDER_FIELDS, tuple)
    assert tuple(parse()) == PROVIDER_FIELDS
    assert set(PROVIDER_FIELDS) == _EXPECTED_FIELDS
    assert len(PROVIDER_FIELDS) == len(set(PROVIDER_FIELDS))


def test_feature_switches_are_not_reload_fields():
    """ENABLE_* stays restart-only; process_audio already hot-reloads live."""
    settings = parse(
        ENABLE_AUDIO_INPUT="false", ENABLE_RAG="false", ENABLE_SHELL="false"
    )
    assert "ENABLE_AUDIO_INPUT" not in settings
    assert set(settings) == _EXPECTED_FIELDS


def test_storable_endpoint_and_model_are_required():
    for field in ("OPENAI_BASE_URL", "OPENAI_MODEL"):
        for blank in ("", "   "):
            with pytest.raises(ValueError, match=field) as excinfo:
                parse_provider_settings({**_BASE, field: blank})
            assert field in str(excinfo.value)


# --- purity ---------------------------------------------------------------


def test_parser_reads_only_the_mapping_it_is_given(monkeypatch):
    """A stale process value must never win over the mapping under test."""
    monkeypatch.setenv("OPENAI_MODEL", "process-environment-model")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://from-process.example/v1")
    settings = parse(OPENAI_MODEL="mapping-model")
    assert settings["OPENAI_MODEL"] == "mapping-model"
    assert settings["OPENAI_BASE_URL"] == "https://primary.example.test/v1"


def test_parser_does_not_mutate_the_process_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://before.example/v1")
    before = dict(os.environ)
    parse(OPENAI_BASE_URL="https://after.example/v1", OPENAI_EXTRA_BODY='{"a": 1}')
    assert dict(os.environ) == before


def test_module_imports_nothing_from_the_application_or_dotenv():
    tree = ast.parse(Path(provider_settings.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    assert imported <= {"json", "math", "collections.abc", "urllib.parse"}


# --- absent versus blank --------------------------------------------------


def test_absent_optional_fields_take_the_startup_defaults():
    settings = parse()
    assert settings["OPENAI_MAX_TOKENS"] == 16384
    assert settings["OPENAI_TEMPERATURE"] == 0.6
    assert settings["OPENAI_TOP_P"] == 0.95
    assert settings["OPENAI_TOP_K"] == 20
    assert settings["OPENAI_RETRY_ATTEMPTS"] == 5
    assert settings["OPENAI_EMPTY_RESPONSE_RETRIES"] == 2
    assert settings["OPENAI_ENDPOINT_COOLDOWN_SECONDS"] == 60.0
    assert settings["OPENAI_DISABLE_REASONING"] is False
    assert settings["OPENAI_FALLBACK_DISABLE_REASONING"] is True
    assert settings["OPENAI_VISION_DISABLE_REASONING"] is True
    assert settings["AUTONOMY_DISABLE_REASONING"] is False
    assert settings["AUX_DISABLE_REASONING"] is True
    assert settings["OPENAI_EXTRA_BODY"] == {}
    assert settings["OPENAI_EXTRA_HEADERS"] == {}


@pytest.mark.parametrize("field", _INT_FIELDS + _FLOAT_FIELDS)
def test_blank_numeric_fields_read_as_unset(field):
    assert parse(**{field: ""})[field] == parse()[field]
    assert parse(**{field: "   "})[field] == parse()[field]


def test_blank_auth_is_valid_for_a_local_compatible_endpoint():
    """No key is required: a local OpenAI-compatible server serves without one."""
    settings = parse(OPENAI_BASE_URL="http://127.0.0.1:8080/v1", OPENAI_API_KEY="")
    assert settings["OPENAI_BASE_URL"] == "http://127.0.0.1:8080/v1"
    assert settings["OPENAI_API_KEY"] == ""
    assert settings["OPENAI_COMPAT_API_KEY"] == ""


def test_absent_primary_key_cascades_to_the_shared_key():
    settings = parse(OPENAI_COMPAT_API_KEY="shared-key")
    assert settings["OPENAI_API_KEY"] == "shared-key"
    assert settings["OPENAI_COMPAT_API_KEY"] == "shared-key"


def test_explicitly_blank_primary_key_does_not_cascade():
    """Blank is a value: it must not silently re-enable the shared key."""
    settings = parse(OPENAI_API_KEY="", OPENAI_COMPAT_API_KEY="shared-key")
    assert settings["OPENAI_API_KEY"] == ""
    assert settings["OPENAI_COMPAT_API_KEY"] == "shared-key"


def test_role_keys_cascade_to_the_shared_key_and_are_independent():
    settings = parse(
        OPENAI_COMPAT_API_KEY="shared-key",
        AUTONOMY_API_KEY="autonomy-key",
        AUX_BASE_URL="https://aux.example.test/v1",
        AUX_MODEL="aux-model",
    )
    assert settings["AUTONOMY_API_KEY"] == "autonomy-key"
    assert settings["AUX_API_KEY"] == "shared-key"
    assert settings["AUTONOMY_BASE_URL"] == ""
    assert settings["AUTONOMY_MODEL"] == ""
    assert settings["AUX_BASE_URL"] == "https://aux.example.test/v1"
    assert settings["AUX_MODEL"] == "aux-model"


def test_explicitly_blank_role_key_does_not_cascade():
    settings = parse(OPENAI_COMPAT_API_KEY="shared-key", AUX_API_KEY="  ")
    assert settings["AUX_API_KEY"] == ""


def test_rem_model_derives_from_the_primary_model():
    """OPENAI_REM_MODEL is a derived model slug, not REM scheduling or storage."""
    assert parse()["OPENAI_REM_MODEL"] == "primary-model"
    assert parse(OPENAI_REM_MODEL="rem-model")["OPENAI_REM_MODEL"] == "rem-model"
    assert parse(OPENAI_REM_MODEL="")["OPENAI_REM_MODEL"] == "primary-model"


def test_provider_free_text_fields_are_stripped():
    settings = parse(
        OPENAI_BASE_URL="  https://primary.example.test/v1  ",
        OPENAI_MODEL="  primary-model  ",
        OPENAI_FALLBACK_BASE_URL="  https://fallback.example.test/v1  ",
        OPENAI_VISION_MODEL="  vision-model  ",
    )
    assert settings["OPENAI_BASE_URL"] == "https://primary.example.test/v1"
    assert settings["OPENAI_MODEL"] == "primary-model"
    assert settings["OPENAI_FALLBACK_BASE_URL"] == "https://fallback.example.test/v1"
    assert settings["OPENAI_VISION_MODEL"] == "vision-model"


# --- booleans -------------------------------------------------------------


@pytest.mark.parametrize("value", ["1", "true", "YES", " On "])
def test_true_words_enable_a_boolean_field(value):
    assert parse(OPENAI_DISABLE_REASONING=value)["OPENAI_DISABLE_REASONING"] is True


@pytest.mark.parametrize("value", ["0", "false", "NO", "off"])
def test_false_words_disable_a_boolean_field(value):
    assert parse(OPENAI_FALLBACK_DISABLE_REASONING=value)[
        "OPENAI_FALLBACK_DISABLE_REASONING"
    ] is False


def test_garbage_boolean_reads_as_false_like_startup():
    assert parse(OPENAI_DISABLE_REASONING="maybe")["OPENAI_DISABLE_REASONING"] is False


# --- endpoint URLs --------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [
        "https://primary.example.test/v1",
        "http://127.0.0.1:8080/v1",
        "https://host.example.test",
        "HTTPS://Upper.Example.Test/v1",
        "http://[::1]:11434/v1",
        "https://primary.example.test:443/v1",
        "https://primary.example.test:8443/v1",
    ],
)
def test_well_formed_endpoint_urls_are_accepted(value):
    assert parse(OPENAI_BASE_URL=value)["OPENAI_BASE_URL"] == value


@pytest.mark.parametrize("field", _URL_FIELDS)
@pytest.mark.parametrize(
    "value",
    [
        "primary.example.test/v1",
        "ftp://host.example.test/v1",
        "https://",
        "http:///path",
        "://host",
        "https://[::1",
    ],
)
def test_malformed_endpoint_urls_raise_naming_the_field_only(field, value):
    with pytest.raises(ValueError) as excinfo:
        parse(**{field: value})
    assert field in str(excinfo.value)
    assert value not in str(excinfo.value)


@pytest.mark.parametrize("field", _OPTIONAL_URL_FIELDS)
def test_optional_endpoint_urls_may_still_be_blank(field):
    """A blank fallback, vision or role endpoint stays disabled, not an error."""
    assert parse(**{field: ""})[field] == ""
    assert parse(**{field: "   "})[field] == ""


def test_blank_fallback_endpoint_still_disables_fallback():
    settings = parse(
        OPENAI_FALLBACK_BASE_URL="", OPENAI_FALLBACK_MODEL="fallback-model"
    )
    assert settings["OPENAI_FALLBACK_BASE_URL"] == ""
    assert settings["OPENAI_FALLBACK_MODEL"] == "fallback-model"


# --- clamping and strict numbers -----------------------------------------


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("OPENAI_MAX_TOKENS", "0", 1),
        ("OPENAI_MAX_TOKENS", "999999", 131072),
        ("OPENAI_MAX_TOKENS", "8192", 8192),
        ("OPENAI_TOP_K", "-3", 0),
        ("OPENAI_TOP_P", "5", 1.0),
        ("OPENAI_TEMPERATURE", "-1", 0.0),
        ("OPENAI_RETRY_ATTEMPTS", "99", 10),
        ("OPENAI_RETRY_ATTEMPTS", "0", 1),
        ("OPENAI_EMPTY_RESPONSE_RETRIES", "9", 5),
    ],
)
def test_numeric_ranges_clamp_the_way_startup_clamps_them(field, value, expected):
    assert parse(**{field: value})[field] == expected


@pytest.mark.parametrize("field", _INT_FIELDS)
@pytest.mark.parametrize("value", ["abc", "1.5", "12x", "0x10"])
def test_non_integer_values_raise_naming_the_field_only(field, value):
    with pytest.raises(ValueError) as excinfo:
        parse(**{field: value})
    assert field in str(excinfo.value)
    assert value not in str(excinfo.value)


@pytest.mark.parametrize("field", _FLOAT_FIELDS)
@pytest.mark.parametrize("value", ["abc", "1.2.3", "--4"])
def test_non_numeric_floats_raise_naming_the_field_only(field, value):
    with pytest.raises(ValueError) as excinfo:
        parse(**{field: value})
    assert field in str(excinfo.value)
    assert value not in str(excinfo.value)


@pytest.mark.parametrize("field", _FLOAT_FIELDS)
@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "Infinity"])
def test_non_finite_floats_raise_naming_the_field_only(field, value):
    with pytest.raises(ValueError) as excinfo:
        parse(**{field: value})
    assert field in str(excinfo.value)


# --- JSON fields ----------------------------------------------------------


@pytest.mark.parametrize("field", _JSON_FIELDS)
def test_malformed_json_raises_naming_the_field_only(field):
    with pytest.raises(ValueError) as excinfo:
        parse(**{field: '{"secret-marker": '})
    assert field in str(excinfo.value)
    assert "secret-marker" not in str(excinfo.value)


@pytest.mark.parametrize("field", _JSON_FIELDS)
@pytest.mark.parametrize("value", ["[]", '"a string"', "3", "null"])
def test_non_object_json_raises_naming_the_field_only(field, value):
    with pytest.raises(ValueError) as excinfo:
        parse(**{field: value})
    assert field in str(excinfo.value)


def test_parsed_json_keeps_nested_request_options():
    raw = '{"reasoning_effort": "high", "provider": {"only": ["deepseek"]}}'
    settings = parse(OPENAI_EXTRA_BODY=raw)
    assert settings["OPENAI_EXTRA_BODY"] == {
        "reasoning_effort": "high",
        "provider": {"only": ["deepseek"]},
    }
    assert settings["OPENAI_EXTRA_HEADERS"] == {}


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_in_request_options_are_rejected(literal):
    """json.loads accepts bare NaN/Infinity literals; a reload must not."""
    with pytest.raises(ValueError) as excinfo:
        parse(OPENAI_EXTRA_BODY='{"temperature": ' + literal + "}")
    assert "OPENAI_EXTRA_BODY" in str(excinfo.value)


def test_nested_non_finite_numbers_are_rejected():
    with pytest.raises(ValueError) as excinfo:
        parse(OPENAI_EXTRA_BODY='{"provider": {"only": [1, NaN]}}')
    assert "OPENAI_EXTRA_BODY" in str(excinfo.value)


def test_finite_nested_numbers_are_accepted():
    settings = parse(OPENAI_EXTRA_BODY='{"provider": {"only": ["a"]}, "n": 1.5}')
    assert settings["OPENAI_EXTRA_BODY"] == {"provider": {"only": ["a"]}, "n": 1.5}


def test_non_string_header_values_raise_naming_the_field_only():
    with pytest.raises(ValueError) as excinfo:
        parse(OPENAI_EXTRA_HEADERS='{"X-Retries": 3}')
    assert "OPENAI_EXTRA_HEADERS" in str(excinfo.value)
    assert "X-Retries" not in str(excinfo.value)


def test_string_header_values_are_kept():
    settings = parse(OPENAI_EXTRA_HEADERS='{"X-Route": "synthetic"}')
    assert settings["OPENAI_EXTRA_HEADERS"] == {"X-Route": "synthetic"}


# --- error hygiene --------------------------------------------------------


def _rendered(error):
    """The traceback text a log would carry, chained context included."""
    return "".join(traceback.format_exception(error))


# The parser catches a real failure from json/int/float/urlsplit here and
# re-raises sanitized, so an original exception exists and must stay suppressed.
# Each entry pairs the input with a distinctive fragment of it that must never
# surface; ``int()``/``float()`` are the ones that actually quote the value.
_CHAINED_ERROR_CASES = [
    ({"OPENAI_EXTRA_BODY": '{"synthetic-secret-marker": '}, "synthetic-secret-marker"),
    (
        {"OPENAI_EXTRA_BODY": '{"n": NaN, "synthetic-secret-marker": 1}'},
        "synthetic-secret-marker",
    ),
    ({"OPENAI_MAX_TOKENS": "synthetic-secret-marker"}, "synthetic-secret-marker"),
    ({"OPENAI_TEMPERATURE": "synthetic-secret-marker"}, "synthetic-secret-marker"),
    (
        {"OPENAI_BASE_URL": "https://[synthetic-secret-marker"},
        "synthetic-secret-marker",
    ),
]

# ``parts.port`` raises from inside the same sanitized handler, and its
# non-numeric message quotes the port back -- the sharpest leak case here.
_PORT_ERROR_CASES = [
    (
        {field: "https://synthetic-secret-marker:synthetic-secret-port/v1"},
        "synthetic-secret-port",
    )
    for field in _URL_FIELDS
] + [
    (
        {field: "https://synthetic-secret-marker:99999/v1"},
        "synthetic-secret-marker",
    )
    for field in _URL_FIELDS
]

_CHAINED_ERROR_CASES += _PORT_ERROR_CASES

# These validate a value that parsed fine and then raise with a plain ``raise``
# (no ``from None``), so ``__suppress_context__`` stays at its False default --
# only the message has to stay field-only.
# ``forbidden`` is None where the input carries no secret worth chasing, because
# a short token like "inf" is a fragile thing to search a traceback for.
_DIRECT_ERROR_CASES = [
    (
        {"OPENAI_EXTRA_HEADERS": '{"synthetic-secret-marker": 3}'},
        "OPENAI_EXTRA_HEADERS",
        "synthetic-secret-marker",
    ),
    ({"OPENAI_TEMPERATURE": "nan"}, "OPENAI_TEMPERATURE", None),
    ({"OPENAI_TEMPERATURE": "inf"}, "OPENAI_TEMPERATURE", None),
    (
        {"OPENAI_FALLBACK_BASE_URL": "ftp://synthetic-secret-marker/v1"},
        "OPENAI_FALLBACK_BASE_URL",
        "synthetic-secret-marker",
    ),
    ({"OPENAI_FALLBACK_BASE_URL": "https://"}, "OPENAI_FALLBACK_BASE_URL", None),
]


@pytest.mark.parametrize("overrides,marker", _CHAINED_ERROR_CASES)
def test_chained_parse_failures_stay_suppressed(overrides, marker):
    """``from None`` keeps the parse failure's own quoted text out of the traceback."""
    with pytest.raises(ValueError) as excinfo:
        parse_provider_settings({**_BASE, **overrides})
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ is True
    assert marker not in _rendered(excinfo.value)


@pytest.mark.parametrize("overrides,field,forbidden", _DIRECT_ERROR_CASES)
def test_direct_validation_failures_name_only_the_field(overrides, field, forbidden):
    """No original exception exists here, so only sanitization is required."""
    with pytest.raises(ValueError) as excinfo:
        parse_provider_settings({**_BASE, **overrides})
    assert field in str(excinfo.value)
    assert excinfo.value.__cause__ is None
    if forbidden is not None:
        assert forbidden not in _rendered(excinfo.value)
