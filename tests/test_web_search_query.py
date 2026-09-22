import asyncio
from types import SimpleNamespace

from bot import TOOL_PROTOCOL, MaxwellBot
from bot_tools import (
    FetchUrlTool,
    WebSearchTool,
    _format_web_hits,
    _normalize_web_hit,
    _sanitize_web_query,
)
from tool_schemas import RESULT_TOOL_NAMES, build_openai_tools


GLUED = (
    "How much usage would I get with this on ollama cloud 20$ plan\n"
    "[Latest message replies to you/Maxwell(1382894657624866889): they don't "
    "publish a number. **ol"
)


def test_plain_user_text_strips_reply_glue():
    assert "Maxwell" not in MaxwellBot._plain_user_text(GLUED)
    assert "ollama cloud" in MaxwellBot._plain_user_text(GLUED).lower()


def test_extract_search_query_does_not_include_reply_blob():
    q = MaxwellBot._extract_search_query(GLUED)
    assert "Latest message replies" not in q
    assert "1382894657624866889" not in q
    assert "ollama" in q.lower()


def test_extract_search_query_strips_lookup_prefix():
    q = MaxwellBot._extract_search_query("look this up: mat dickie")
    assert "look this up" not in q.lower()
    assert "mat dickie" in q.lower()


def test_needs_up_to_date_ignores_glued_maxwell_reply():
    casual = (
        "lol\n[Latest message replies to you/Maxwell(1): glm 5.3 just released "
        "new model today]"
    )
    assert MaxwellBot._needs_up_to_date_info(casual) is False


def test_needs_up_to_date_skips_banter():
    for line in ("lol", "lmao", "wyd", "gm", "yeah", "how's it going"):
        assert MaxwellBot._needs_up_to_date_info(line) is False, line


def test_needs_up_to_date_explicit_lookup():
    assert MaxwellBot._needs_up_to_date_info("look this up") is True
    assert MaxwellBot._needs_up_to_date_info("search for ollama cloud pricing") is True
    assert MaxwellBot._needs_up_to_date_info("google that") is True
    assert MaxwellBot._needs_up_to_date_info("can you find out who that is") is True


def test_needs_up_to_date_current_events():
    assert MaxwellBot._needs_up_to_date_info("who won last night") is True
    assert MaxwellBot._needs_up_to_date_info("what's the weather in nyc") is True
    assert MaxwellBot._needs_up_to_date_info("what's the latest grok model") is True
    assert MaxwellBot._needs_up_to_date_info("new model drop today") is True


def test_needs_up_to_date_stable_trivia_is_not_auto_search():
    # The model should still *choose* to search; auto-search is only a backup
    # for current/lookup turns, not every factoid.
    assert MaxwellBot._needs_up_to_date_info("what is the capital of france") is False


# The harness notice header mirrors smoke_protocol.compose_notice (the smoke
# lane's module, not present in this worktree). Keep it in step with that
# template; it deliberately carries no model/recency word of its own.
SMOKE_HEADER = (
    "\N{WARNING SIGN} HARNESS SMOKE TEST <@1504398705539944560>\n"
    "No human typed this. Root authorized it while AFK.\n"
    "Permission actor: root (1482143139828596916), separate from the author of this text.\n"
    "Task follows.\n"
)
SMOKE_TASK = (
    "THIS IS A SMOKE TEST from the operator harness. "
    "Correction to my earlier status request: source exposes spawn_background plus the "
    "human !job command, not a native job-status tool. "
    "That was my imprecise request, not proof of a missing feature. "
    "The earlier diagnostic turn timed out after real shell/search work; do not relabel "
    "it successful. "
    "For this separate rerun, use shell once to read /state/data/background_jobs.json and "
    "print only id/status/channel_id/thread_id/thread_error/provider/model for jobs "
    "c927c30f and 0df54176. "
    "No Discord search, no other tools, no new jobs, no writes. "
    "Then give a short observed status report and flag any anomaly; do not speculate "
    "about unobserved provider internals."
)


def test_needs_up_to_date_ignores_the_wrapped_harness_status_request():
    """The real notice text must not be read as a question about a new model.

    Its only AI-topic hit is the "model" column the task asks to print, and its
    only recency hit is "no new jobs"; they sit in different clauses.
    """
    assert MaxwellBot._needs_up_to_date_info(SMOKE_HEADER) is False
    assert MaxwellBot._needs_up_to_date_info(SMOKE_HEADER + SMOKE_TASK) is False


def test_needs_up_to_date_separates_model_and_recency_clauses():
    assert (
        MaxwellBot._needs_up_to_date_info(
            "print the provider/model field for these jobs. there is nothing new here."
        )
        is False
    )
    assert (
        MaxwellBot._needs_up_to_date_info(
            "the model column is stale; no new jobs were queued"
        )
        is False
    )


def test_needs_up_to_date_same_sentence_ai_recency_still_fires():
    assert MaxwellBot._needs_up_to_date_info("is there a new deepseek model out?") is True
    assert MaxwellBot._needs_up_to_date_info("any recent mistral benchmarks?") is True


def test_needs_up_to_date_keeps_lookup_and_current_event_positives():
    for line in (
        "look this up",
        "search for ollama cloud pricing",
        "google that",
        "can you find out who that is",
        "who won last night",
        "what's the weather in nyc",
        "what's the latest grok model",
        "new model drop today",
    ):
        assert MaxwellBot._needs_up_to_date_info(line) is True, line


def test_sanitize_web_query_truncates_unclosed_bracket():
    q = _sanitize_web_query(GLUED)
    assert "Latest message" not in q
    assert q.startswith("How much usage")


def test_web_search_description_encourages_lookup():
    desc = WebSearchTool(SimpleNamespace()).get_description().lower()
    assert "don't search" not in desc
    assert "only if" not in desc
    assert "casual conversation" not in desc
    assert "unsure" in desc or "guess" in desc
    stamped = build_openai_tools({"web_search": WebSearchTool(SimpleNamespace())})[0][
        "function"
    ]["description"].lower()
    assert "returns output" in stamped
    assert "don't search" not in stamped


def test_fetch_url_description_is_for_reading_pages():
    desc = FetchUrlTool(SimpleNamespace()).get_description().lower()
    assert "only if" not in desc
    assert "page" in desc
    assert "web_search" in desc


def test_tool_protocol_says_look_things_up():
    blob = TOOL_PROTOCOL.lower()
    assert "web_search" in blob
    assert "fetch_url" in blob
    assert "guess" in blob
    assert "training data" in blob


def test_native_tool_prompt_includes_lookup_contract():
    bot = SimpleNamespace(
        tools={
            "web_search": WebSearchTool(SimpleNamespace()),
            "fetch_url": FetchUrlTool(SimpleNamespace()),
            "send_message": SimpleNamespace(get_description=lambda: "send"),
        },
        _control={
            "tools_enabled": True,
            "disabled_tools": [],
            "native_tool_calls": True,
        },
    )
    bot._compatible_tool_names = MaxwellBot._compatible_tool_names.__get__(bot)
    prompt = MaxwellBot._tool_system_prompt(bot, "discord")
    assert "XML text tags only" not in prompt
    assert "Look things up" in prompt
    assert "web_search" in prompt
    assert "training data" in prompt
    assert TOOL_PROTOCOL in prompt


def test_lookup_tools_return_output_to_the_model():
    assert "web_search" in RESULT_TOOL_NAMES
    assert "fetch_url" in RESULT_TOOL_NAMES


def test_normalize_web_hit_accepts_url_and_excerpt():
    hit = _normalize_web_hit(
        {"title": "T", "url": "https://ex.com/a", "excerpt": "hello body"}
    )
    assert hit["href"] == "https://ex.com/a"
    assert hit["body"] == "hello body"
    formatted = _format_web_hits([hit])
    assert "https://ex.com/a" in formatted
    assert "hello body" in formatted


def _search_bot():
    return SimpleNamespace(
        mark_message_tainted=lambda *_a, **_k: None,
        config=SimpleNamespace(RAG_WEB_STORE_ENABLED=False),
        memory=None,
    )


def test_web_search_formats_url_keyed_hits(monkeypatch):
    class FakeDDGS:
        def __init__(self, *a, **k):
            pass

        def text(self, query, **k):
            return [
                {
                    "title": "Example",
                    "url": "https://ex.com/page",
                    "excerpt": "A" * 80,
                }
            ]

    monkeypatch.setattr("bot_tools._DDGS", FakeDDGS)
    monkeypatch.setattr("bot_tools._DDGS_AVAILABLE", True)
    tool = WebSearchTool(_search_bot())
    result = asyncio.run(tool.execute(SimpleNamespace(guild=None), query="mat dickie"))
    assert not result.lower().startswith("error")
    assert "https://ex.com/page" in result
    assert "Example" in result
    assert "A" * 80 in result


def test_web_search_empty_ddgs_exception_is_not_an_error(monkeypatch):
    class FakeDDGS:
        def __init__(self, *a, **k):
            pass

        def text(self, query, **k):
            raise RuntimeError("No results found.")

    monkeypatch.setattr("bot_tools._DDGS", FakeDDGS)
    monkeypatch.setattr("bot_tools._DDGS_AVAILABLE", True)
    tool = WebSearchTool(_search_bot())
    result = asyncio.run(tool.execute(SimpleNamespace(guild=None), query="xyzzy"))
    assert result.startswith("No results found")
    assert not result.lower().startswith("error")


def test_web_search_taints_the_turn(monkeypatch):
    tainted = {}

    class FakeDDGS:
        def __init__(self, *a, **k):
            pass

        def text(self, query, **k):
            return [{"title": "T", "href": "https://ex.com", "body": "b"}]

    monkeypatch.setattr("bot_tools._DDGS", FakeDDGS)
    monkeypatch.setattr("bot_tools._DDGS_AVAILABLE", True)
    bot = _search_bot()
    bot.mark_message_tainted = lambda msg: tainted.setdefault("ok", True)
    msg = SimpleNamespace(id=9, guild=None)
    asyncio.run(WebSearchTool(bot).execute(msg, query="hi"))
    assert tainted.get("ok") is True
