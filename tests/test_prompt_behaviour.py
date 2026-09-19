"""Prompt contracts for proactive work, reply pacing and verified results."""

from bot import LEAN_TOOL_PROTOCOL, TOOL_PROTOCOL


def test_full_protocol_asks_for_proactive_work():
    text = TOOL_PROTOCOL.lower()
    assert "be proactive" in text
    assert "do the whole job" in text
    assert "finishing is the job" in text


def test_full_protocol_discourages_needless_questions():
    text = TOOL_PROTOCOL.lower()
    assert "only ask a question when you genuinely cannot proceed" in text


def test_lean_protocol_also_asks_for_proactive_work():
    """Ordinary chat turns carry the lean block, so it needs this too."""
    assert "be proactive" in LEAN_TOOL_PROTOCOL.lower()


def test_protocols_forbid_burst_replies():
    for text in (TOOL_PROTOCOL.lower(), LEAN_TOOL_PROTOCOL.lower()):
        assert "one send_message" in text
        assert "spam" in text


def test_protocols_offer_silence_as_the_alternative():
    for text in (TOOL_PROTOCOL.lower(), LEAN_TOOL_PROTOCOL.lower()):
        assert "no_response" in text


def test_full_protocol_forbids_claiming_unverified_work():
    text = TOOL_PROTOCOL.lower()
    assert "never claim something is done" in text
    assert "unless a tool result" in text


def test_full_protocol_still_rejects_ack_only_turns():
    text = TOOL_PROTOCOL.lower()
    assert "announcing an action is not performing it" in text
    assert "on it" in text
    assert "do not pair send_message" in text
    assert "acknowledgement" not in text
    assert "put the helper tool" not in text


def test_protocols_do_not_ask_for_a_placeholder_send():
    for text in (TOOL_PROTOCOL.lower(), LEAN_TOOL_PROTOCOL.lower()):
        assert "same batch as the acknowledgement" not in text
        assert "content='on it" not in text
        assert "more_tools" not in text


def test_lean_protocol_forbids_claiming_unverified_work():
    assert "never say you have done something you have not" in (
        LEAN_TOOL_PROTOCOL.lower()
    )


def test_protocol_tells_him_to_pick_his_own_chess_moves():
    text = TOOL_PROTOCOL.lower()
    assert "you play your own moves" in text
    assert "nothing plays for you" in text
