import ast
import os
import traceback
from pathlib import Path

import pytest

import provider_settings
from provider_settings import PROVIDER_FIELDS, parse_provider_settings

_BASE = {"OPENAI_BASE_URL": "https://primary.example.test/v1", "OPENAI_MODEL": "primary-model"}
_EXPECTED_FIELDS = frozenset({
    "OPENAI_BASE_URL", "OPENAI_MODEL", "OPENAI_API_KEY", "OPENAI_COMPAT_API_KEY",
    "OPENAI_MAX_TOKENS", "OPENAI_TEMPERATURE", "OPENAI_TOP_P", "OPENAI_TOP_K",
    "OPENAI_EXTRA_HEADERS", "OPENAI_EXTRA_BODY", "OPENAI_RETRY_ATTEMPTS",
    "OPENAI_EMPTY_RESPONSE_RETRIES", "AUTONOMY_BASE_URL",
    "AUTONOMY_API_KEY", "AUTONOMY_MODEL", "AUX_BASE_URL", "AUX_API_KEY", "AUX_MODEL",
})
_INT_FIELDS = ("OPENAI_MAX_TOKENS", "OPENAI_TOP_K", "OPENAI_RETRY_ATTEMPTS", "OPENAI_EMPTY_RESPONSE_RETRIES")
_FLOAT_FIELDS = ("OPENAI_TEMPERATURE", "OPENAI_TOP_P")
_JSON_FIELDS = ("OPENAI_EXTRA_HEADERS", "OPENAI_EXTRA_BODY")
_URL_FIELDS = ("OPENAI_BASE_URL", "AUTONOMY_BASE_URL", "AUX_BASE_URL")
_OPTIONAL_URL_FIELDS = _URL_FIELDS[1:]


def parse(**overrides):
    return parse_provider_settings({**_BASE, **overrides})


def test_returns_exactly_the_provider_field_set():
    assert set(parse()) == _EXPECTED_FIELDS


def test_provider_fields_matches_the_parsed_names_and_order():
    assert isinstance(PROVIDER_FIELDS, tuple)
    assert tuple(parse()) == PROVIDER_FIELDS
    assert set(PROVIDER_FIELDS) == _EXPECTED_FIELDS
    assert len(PROVIDER_FIELDS) == len(set(PROVIDER_FIELDS))


def test_feature_switches_are_not_reload_fields():
    assert set(parse(ENABLE_AUDIO_INPUT="false", ENABLE_RAG="false")) == _EXPECTED_FIELDS


def test_storable_endpoint_and_model_are_required():
    for field in ("OPENAI_BASE_URL", "OPENAI_MODEL"):
        for blank in ("", "   "):
            with pytest.raises(ValueError, match=field):
                parse(**{field: blank})


def test_parser_reads_only_the_mapping_it_is_given(monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "process-model")
    monkeypatch.setenv("OPENAI_TEMPERATURE", "0.6")
    settings = parse(OPENAI_MODEL="mapping-model")
    assert settings["OPENAI_MODEL"] == "mapping-model"
    assert settings["OPENAI_TEMPERATURE"] is None


def test_parser_does_not_mutate_the_process_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "https://before.example/v1")
    before = dict(os.environ)
    parse(OPENAI_EXTRA_BODY='{"provider":{"only":["declared"],"allow_fallbacks":false}}')
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


def test_absent_optional_fields_take_the_startup_defaults():
    settings = parse()
    for name in ("OPENAI_MAX_TOKENS", "OPENAI_TEMPERATURE", "OPENAI_TOP_P", "OPENAI_TOP_K"):
        assert settings[name] is None
    assert settings["OPENAI_RETRY_ATTEMPTS"] == 5
    assert settings["OPENAI_EMPTY_RESPONSE_RETRIES"] == 2
    assert settings["OPENAI_EXTRA_BODY"] == {}
    assert settings["OPENAI_EXTRA_HEADERS"] == {}


@pytest.mark.parametrize("field", _INT_FIELDS + _FLOAT_FIELDS)
@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_numeric_fields_read_as_unset(field, blank):
    with pytest.raises(ValueError, match=field):
        parse(**{field: blank})


def test_blank_auth_is_valid_for_a_local_compatible_endpoint():
    settings = parse(OPENAI_BASE_URL="http://127.0.0.1:8080/v1", OPENAI_API_KEY="")
    assert settings["OPENAI_API_KEY"] == ""
    assert settings["OPENAI_COMPAT_API_KEY"] == ""


def test_absent_primary_key_cascades_to_the_shared_key():
    settings = parse(OPENAI_COMPAT_API_KEY=" shared-key ")
    assert settings["OPENAI_API_KEY"] == " shared-key "
    assert settings["OPENAI_COMPAT_API_KEY"] == " shared-key "


def test_explicitly_blank_primary_key_does_not_cascade():
    assert parse(OPENAI_API_KEY="", OPENAI_COMPAT_API_KEY="shared-key")["OPENAI_API_KEY"] == ""


def test_role_keys_cascade_to_the_shared_key_and_are_independent():
    settings = parse(OPENAI_COMPAT_API_KEY="shared-key", AUTONOMY_API_KEY="shared-key")
    assert settings["AUTONOMY_API_KEY"] == "shared-key"
    assert settings["AUX_API_KEY"] is None


def test_explicitly_blank_role_key_does_not_cascade():
    assert parse(OPENAI_API_KEY="  ", AUX_API_KEY="  ")["AUX_API_KEY"] == "  "
    assert parse(AUX_API_KEY="")["AUX_API_KEY"] == ""
    assert parse(AUX_MODEL="other")["AUX_API_KEY"] is None


@pytest.mark.parametrize("value", ["", " rem-model "])
def test_rem_model_derives_from_the_primary_model(value):
    assert "OPENAI_REM_MODEL" not in parse()
    with pytest.raises(ValueError, match="OPENAI_REM_MODEL"):
        parse(OPENAI_REM_MODEL=value)


def test_provider_free_text_fields_are_stripped():
    settings = parse(OPENAI_MODEL="  primary-model  ", OPENAI_API_KEY=" key ")
    assert settings["OPENAI_MODEL"] == "  primary-model  "
    assert settings["OPENAI_API_KEY"] == " key "
    with pytest.raises(ValueError, match="OPENAI_BASE_URL"):
        parse(OPENAI_BASE_URL=" https://primary.example/v1 ")


@pytest.mark.parametrize("value", ["1", "true", "YES", " On "])
def test_true_words_enable_a_boolean_field(value):
    with pytest.raises(ValueError, match="OPENAI_DISABLE_REASONING"):
        parse(OPENAI_DISABLE_REASONING=value)


@pytest.mark.parametrize("value", ["0", "false", "NO", "off", ""])
def test_false_words_disable_a_boolean_field(value):
    with pytest.raises(ValueError, match="OPENAI_FALLBACK_DISABLE_REASONING"):
        parse(OPENAI_FALLBACK_DISABLE_REASONING=value)


def test_garbage_boolean_reads_as_false_like_startup():
    with pytest.raises(ValueError, match="OPENAI_DISABLE_REASONING"):
        parse(OPENAI_DISABLE_REASONING="maybe")


@pytest.mark.parametrize("value", [
    "https://primary.example.test/v1", "http://127.0.0.1:8080/v1", "https://host.example.test",
    "HTTPS://Upper.Example.Test/v1", "http://[::1]:11434/v1", "https://primary.example.test:443/v1/",
    "https://host.test/v1?route=other", "https://host.test/v1#fragment",
    "https://host.test/v1/?opaque=a%2Fb#fragment?literal", "https://host.test/v1?#",
])
def test_well_formed_endpoint_urls_are_accepted(value):
    assert parse(OPENAI_BASE_URL=value)["OPENAI_BASE_URL"] == value


@pytest.mark.parametrize("field", _URL_FIELDS)
@pytest.mark.parametrize("value", [
    "primary.example.test/v1", "ftp://host.example.test/v1", "https://", "http:///path",
    "://host", "https://[::1",
])
def test_malformed_endpoint_urls_raise_naming_the_field_only(field, value):
    with pytest.raises(ValueError) as error:
        parse(**{field: value})
    assert field in str(error.value)
    assert value not in str(error.value)


@pytest.mark.parametrize("field", _OPTIONAL_URL_FIELDS)
def test_optional_endpoint_urls_may_still_be_blank(field):
    assert parse(**{field: ""})[field] == ""
    with pytest.raises(ValueError, match=field):
        parse(**{field: "   "})


@pytest.mark.parametrize("field", ["OPENAI_FALLBACK_BASE_URL", "OPENAI_VISION_MODEL", "OPENAI_ENDPOINT_COOLDOWN_SECONDS"])
def test_blank_fallback_endpoint_still_disables_fallback(field):
    with pytest.raises(ValueError, match=field):
        parse(**{field: ""})


@pytest.mark.parametrize("field,value,expected", [
    ("OPENAI_MAX_TOKENS", "64000", 64000), ("OPENAI_MAX_TOKENS", "999999", 999999),
    ("OPENAI_TOP_K", "-3", -3), ("OPENAI_TOP_P", "5", 5.0),
    ("OPENAI_TEMPERATURE", "-1", -1.0), ("OPENAI_RETRY_ATTEMPTS", "99", 99),
    ("OPENAI_EMPTY_RESPONSE_RETRIES", "9", 9),
])
def test_numeric_ranges_clamp_the_way_startup_clamps_them(field, value, expected):
    assert parse(**{field: value})[field] == expected


@pytest.mark.parametrize("field", _INT_FIELDS)
@pytest.mark.parametrize("value", ["abc", "1.5", "12x", "0x10"])
def test_non_integer_values_raise_naming_the_field_only(field, value):
    with pytest.raises(ValueError) as error:
        parse(**{field: value})
    assert field in str(error.value)
    assert value not in str(error.value)


@pytest.mark.parametrize("field", _FLOAT_FIELDS)
@pytest.mark.parametrize("value", ["abc", "1.2.3", "--4"])
def test_non_numeric_floats_raise_naming_the_field_only(field, value):
    with pytest.raises(ValueError) as error:
        parse(**{field: value})
    assert field in str(error.value)
    assert value not in str(error.value)


@pytest.mark.parametrize("field", _FLOAT_FIELDS)
@pytest.mark.parametrize("value", ["nan", "inf", "-inf", "Infinity"])
def test_non_finite_floats_raise_naming_the_field_only(field, value):
    with pytest.raises(ValueError, match=field):
        parse(**{field: value})


@pytest.mark.parametrize("field", _JSON_FIELDS)
def test_malformed_json_raises_naming_the_field_only(field):
    with pytest.raises(ValueError, match=field) as error:
        parse(**{field: '{"secret-marker": '})
    assert "secret-marker" not in str(error.value)


@pytest.mark.parametrize("field", _JSON_FIELDS)
@pytest.mark.parametrize("value", ["[]", '"a string"', "3", "null"])
def test_non_object_json_raises_naming_the_field_only(field, value):
    with pytest.raises(ValueError, match=field):
        parse(**{field: value})


def test_parsed_json_keeps_nested_request_options():
    body = '{"reasoning_effort":"high","provider":{"only":["declared"],"allow_fallbacks":false}}'
    assert parse(OPENAI_EXTRA_BODY=body)["OPENAI_EXTRA_BODY"] == {
        "reasoning_effort": "high", "provider": {"only": ["declared"], "allow_fallbacks": False},
    }


@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_non_finite_numbers_in_request_options_are_rejected(literal):
    with pytest.raises(ValueError, match="OPENAI_EXTRA_BODY"):
        parse(OPENAI_EXTRA_BODY='{"temperature":' + literal + "}")


def test_nested_non_finite_numbers_are_rejected():
    with pytest.raises(ValueError, match="OPENAI_EXTRA_BODY"):
        parse(OPENAI_EXTRA_BODY='{"provider":{"only":[1,NaN]}}')


def test_finite_nested_numbers_are_accepted():
    assert parse(OPENAI_EXTRA_BODY='{"custom":{"values":[1,1.5]}}')["OPENAI_EXTRA_BODY"] == {
        "custom": {"values": [1, 1.5]},
    }


def test_non_string_header_values_raise_naming_the_field_only():
    with pytest.raises(ValueError, match="OPENAI_EXTRA_HEADERS") as error:
        parse(OPENAI_EXTRA_HEADERS='{"X-Retries":3}')
    assert "X-Retries" not in str(error.value)


def test_string_header_values_are_kept():
    assert parse(OPENAI_EXTRA_HEADERS='{"X-Route":" synthetic "}')["OPENAI_EXTRA_HEADERS"] == {
        "X-Route": " synthetic ",
    }


def _rendered(error):
    return "".join(traceback.format_exception(error))


@pytest.mark.parametrize("overrides,marker", [
    ({"OPENAI_EXTRA_BODY": '{"synthetic-secret-marker":'}, "synthetic-secret-marker"),
    ({"OPENAI_MAX_TOKENS": "synthetic-secret-marker"}, "synthetic-secret-marker"),
    ({"OPENAI_TEMPERATURE": "synthetic-secret-marker"}, "synthetic-secret-marker"),
    ({"OPENAI_BASE_URL": "https://[synthetic-secret-marker"}, "synthetic-secret-marker"),
    ({"AUX_BASE_URL": "https://host:synthetic-secret-port/v1"}, "synthetic-secret-port"),
])
def test_chained_parse_failures_stay_suppressed(overrides, marker):
    with pytest.raises(ValueError) as error:
        parse(**overrides)
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True
    assert marker not in _rendered(error.value)


@pytest.mark.parametrize("overrides,field,forbidden", [
    ({"OPENAI_EXTRA_HEADERS": '{"synthetic-secret-marker":3}'}, "OPENAI_EXTRA_HEADERS", "synthetic-secret-marker"),
    ({"OPENAI_TEMPERATURE": "nan"}, "OPENAI_TEMPERATURE", None),
    ({"OPENAI_MAX_TOKENS": "0"}, "OPENAI_MAX_TOKENS", None),
    ({"OPENAI_RETRY_ATTEMPTS": "0"}, "OPENAI_RETRY_ATTEMPTS", None),
    ({"OPENAI_EXTRA_BODY": '{"model":"secret-other"}'}, "OPENAI_EXTRA_BODY", "secret-other"),
    ({"OPENAI_EXTRA_BODY": '{"messages":[]}'}, "OPENAI_EXTRA_BODY", None),
    ({"OPENAI_API_KEY": "secret-key", "OPENAI_EXTRA_HEADERS": '{"authorization":"secret-auth"}'}, "OPENAI_API_KEY", "secret-auth"),
    ({"OPENAI_EXTRA_HEADERS": '{"X-Test":"a","x-test":"b"}'}, "OPENAI_EXTRA_HEADERS", None),
    ({"AUX_BASE_URL": "https://secret-role/v1"}, "AUX_BASE_URL", "secret-role"),
    ({"AUX_MODEL": "other", "AUX_API_KEY": "", "OPENAI_API_KEY": "secret-key"}, "AUX_API_KEY", "secret-key"),
])
def test_direct_validation_failures_name_only_the_field(overrides, field, forbidden):
    with pytest.raises(ValueError) as error:
        parse(**overrides)
    assert field in str(error.value)
    assert error.value.__cause__ is None
    if forbidden is not None:
        assert forbidden not in _rendered(error.value)
