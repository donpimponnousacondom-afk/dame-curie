"""Repetition in what the bot says.

Inside a single reply, repetition reaches Discord as the model wrote it.
Root, 1 November 2026: the scrubbers that collapsed laugh runs, doubled
words and echo loops are removed; a loop in Discord is a signal to fix the
cause. Across replies, the same phrase opening six messages running is a
pattern no single message is wrong for, so the model is told about it.
"""

from types import SimpleNamespace

import pytest

from bot import DameCurieBot, _sanitize_visible_reply


# ─── within one reply ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "jajajajajaja qué bueno",
        "(ja)(ja)(ja)(ja) listo",
        "y y de de acuerdo",
        "bye bye, it had had enough",
        "Esto funciona. Esto funciona.",
        "the same thing " * 40,
        "```py\n" + "print(1)\n" * 40 + "```",
        "here is the deploy plan, it should take about ten minutes",
        "literal \\n stays",
        "see [1] and [spoiler] and [laughs]",
        "[Dame Curie] hi",
        "Called react with {} -> Tool react: Reacted with 👍",
        "hi __NO_RESPONSE__ __TTS_SENT__ __SHELL_SENT__ __MEME_SENT__",
        "__MEDIA_SENT__ __FILE_SENT__ __MESSAGE_SENT__ __IMAGE_SENT__",
        "__CAPTION_SENT__ __REASONING_RECORDED__",
        "[RESPOND TO THIS] alice(456): hi",
        "alice(123456789012345678): hi\nthe real answer",
        "Mentioned users in latest message: Bob\nok",
        "Images available to inspect:\n1. IMG_1588.jpg (image/jpeg, new)\nok",
        "see <<https://example.com/a>>",
        "[x]\n{\"k\": 1}\n[/x] after",
        "SirRooT(1482143139828596916) said hi",
        "no preview: <https://example.com/page>",
    ],
)
def test_ordinary_text_is_left_alone(text):
    # A regression guard: each of these was rewritten or removed before.
    assert _sanitize_visible_reply(text) == text.strip()


# ─── across replies ──────────────────────────────────────────────────────


def _bot(control=None, self_id=1):
    return SimpleNamespace(
        _control=control if control is not None else {},
        user=SimpleNamespace(id=self_id),
    )


def _mine(*contents):
    return [{"author_is_bot": True, "content": c} for c in contents]


def test_a_repeated_opener_is_named_back_at_him():
    note = DameCurieBot._self_repetition_note(
        _bot(),
        _mine(
            "jajaja bro that is wild",
            "jajajaja man ok",
            "sure thing",
            "jaja yeah",
            "ok cool",
        ),
    )
    # Naming the phrase is the point - "vary your language" changes nothing.
    assert "jaja" in note
    assert "3 of your last 5" in note


def test_laugh_runs_of_different_lengths_count_as_one_tic():
    # "jajaja" and "jajajajaja" are the same habit; an exact-match check on the
    # opener would see two different strings and stay quiet.
    note = DameCurieBot._self_repetition_note(
        _bot(), _mine("jajaja a", "jajajajaja b", "jaja c")
    )
    assert note


def test_varied_openers_say_nothing():
    note = DameCurieBot._self_repetition_note(
        _bot(), _mine("hi", "there you go", "what is up", "ok then")
    )
    assert note == ""


def test_other_peoples_messages_are_not_his_habit():
    others = [
        {"author_is_bot": False, "author_id": "9", "content": "jajaja hey"}
        for _ in range(6)
    ]
    assert DameCurieBot._self_repetition_note(_bot(), others) == ""


def test_tool_rows_are_not_speech():
    rows = [
        {"author_is_bot": True, "is_tool": True, "content": "Called x with {}"}
        for _ in range(6)
    ]
    assert DameCurieBot._self_repetition_note(_bot(), rows) == ""


def test_an_empty_or_short_history_says_nothing():
    assert DameCurieBot._self_repetition_note(_bot(), []) == ""
    assert DameCurieBot._self_repetition_note(_bot(), None) == ""
    assert DameCurieBot._self_repetition_note(_bot(), _mine("jaja a", "jaja b")) == ""


def test_the_nudge_can_be_switched_off():
    note = DameCurieBot._self_repetition_note(
        _bot({"self_repetition_note_enabled": False}),
        _mine("jaja a", "jaja b", "jaja c"),
    )
    assert note == ""


def test_messages_attributed_by_id_count_too():
    # Not every stored row carries author_is_bot; some only have the id.
    rows = [
        {"author_id": "1", "content": c} for c in ("jaja a", "jaja b", "jaja c")
    ]
    assert DameCurieBot._self_repetition_note(_bot(self_id=1), rows)
