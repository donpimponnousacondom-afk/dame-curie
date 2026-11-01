"""Regression tests for send_message vs leftover plaintext.

2026-08-02: a "checking…" placeholder via send_message dropped the later
follow-up answer. 2026-08-14: leftover assistant content on the SAME
generation as send_message posted a second Discord reply ping.
"""

import json

import pytest

from bot import (
    _beside_text_is_early_update,
    _should_skip_plaintext_after_send,
    _tool_results_need_followup,
)


def _native_call(name, args, call_id="call_1"):
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)},
    }


def test_same_generation_leftover_does_not_post_second_reply():
    last = ["Tool send_message: __MESSAGE_SENT__\nquick research dump: ..."]
    all_results = [
        "Tool web_search: found 3 results",
        last[0],
    ]
    assert (
        _should_skip_plaintext_after_send(
            last,
            all_results,
            followup_turn_ran=True,
            response="The Yotta article is slightly stale...",
        )
        is True
    )


def test_message_sent_followup_response_is_not_silently_dropped():
    last = []  # follow-up turn had no new send_message
    all_results = [
        "Tool web_search: found 3 results for 'Mat Dickie'",
        "Tool send_message: __MESSAGE_SENT__\nchecking…",
    ]
    assert (
        _should_skip_plaintext_after_send(
            last,
            all_results,
            followup_turn_ran=True,
            response="yeah, Mat Dickie (MDickie) is the indie wrestling game dev...",
        )
        is False
    )


def test_message_sent_without_followup_still_returns_early():
    last = ["Tool send_message: __MESSAGE_SENT__\nhere's your summary"]
    assert (
        _should_skip_plaintext_after_send(
            last, last, followup_turn_ran=False, response=""
        )
        is True
    )


def test_message_sent_followup_with_empty_response_still_returns_early():
    last = []
    all_results = ["Tool send_message: __MESSAGE_SENT__\ndone"]
    assert (
        _should_skip_plaintext_after_send(
            last, all_results, followup_turn_ran=True, response=""
        )
        is True
    )


def test_no_message_sent_falls_through_normally():
    last = ["Tool web_search: found 5 results"]
    assert (
        _should_skip_plaintext_after_send(
            last,
            last,
            followup_turn_ran=True,
            response="search results summarized…",
        )
        is False
    )


# ---------------------------------------------------------------------------
# Root, 1 November 2026: the bot reads no intent from the words of a reply.
# A word regex once took "a man checking whether..." in a finished reply for
# an "on it" promise, called the model again and posted the reply twice.
# send_message ends the turn. A progress update is text beside tool calls.
# ---------------------------------------------------------------------------

HELLO_REPLY = (
    'Present, Sir. You called "hello" like a man checking whether the '
    "machine is still plugged in."
)


@pytest.mark.parametrize(
    "text",
    [
        HELLO_REPLY,
        "on it...",
        "working on it…",
        "checking that now",
        "one sec",
        "i'll build that for you",
        "looking into it",
        "yeah",
        "done - live at https://x.dev",
    ],
)
def test_send_message_ends_the_turn_whatever_its_words(text):
    assert _tool_results_need_followup([f"Tool send_message: __MESSAGE_SENT__\n{text}"]) is False


@pytest.mark.parametrize(
    ("names", "text", "is_update"),
    [
        (["web_search"], "Looking it up.", True),
        (["shell", "fetch_url"], "Pulling the logs.", True),
        (["react"], "nice", True),
        # A final or pausing call in the response: the text is no update.
        (["web_search", "send_message"], "Looking it up.", False),
        (["send_message"], "Here you go.", False),
        (["no_response"], "I will stay quiet.", False),
        (["wait"], "brb", False),
        (["sleep"], "night", False),
        # A media delivery is the reply; its text keeps the after-call rule.
        (["image_generator"], "Here is your image.", False),
        (["send_file"], "Here is the file.", False),
        (["web_search", "send_media"], "Here it is.", False),
        # No text, or no tool calls: nothing to post as an update.
        (["web_search"], "  ", False),
        ([], "plain answer", False),
    ],
)
def test_beside_text_posts_early_only_next_to_working_calls(names, text, is_update):
    calls = [_native_call(name, {}, f"c{index}") for index, name in enumerate(names)]
    assert _beside_text_is_early_update(calls, text) is is_update


def test_ack_plus_real_tool_still_loops_for_the_result():
    results = [
        "Tool send_message: __MESSAGE_SENT__\non it...",
        "Tool shell: harness output",
    ]
    assert _tool_results_need_followup(results) is True


def test_no_response_stays_terminal():
    results = ["Tool no_response: __NO_RESPONSE__"]
    assert _tool_results_need_followup(results) is False


def test_error_still_forces_followup():
    for error in (
        "Tool shell: Error - boom",
        "Tool hd_image: Error - unknown tool 'hd_image'",
        "Tool react: Error - permission actor is not authorized for this tool",
        "Tool no_response: Error - unavailable",
    ):
        assert _tool_results_need_followup([error]) is True
        assert _tool_results_need_followup(
            ["Tool send_message: __MESSAGE_SENT__\ndone", error]
        ) is True
