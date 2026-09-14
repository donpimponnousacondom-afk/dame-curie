import pytest

from bot import (
    _sanitize_visible_reply,
    _should_skip_plaintext_after_send,
    _tool_results_need_followup,
)


CDN = "https://cdn.discordapp.com/attachments/100/200/generated_image.png"


@pytest.mark.parametrize("text,expected", [
    (CDN, CDN),
    (f"[generated_image.png]({CDN})", f"[generated_image.png]({CDN})"),
    ("[article](https://example.com/article)", "[article](https://example.com/article)"),
    ("[TOOL_CALL:web_search]answer[/web_search]", "answer"),
    ("[tool]answer[/tool]", "answer"),
    ("[tool foo=bar]answer[/tool]", "answer"),
    (f"[tool][shot]({CDN})[/tool]", f"[shot]({CDN})"),
    (f"[shot]({CDN})[tool]done[/tool]", f"[shot]({CDN})done"),
    (f"[first]({CDN}) [second](https://example.com/page)", f"[first]({CDN}) [second](https://example.com/page)"),
    ('[tool]{"payload": "hidden"}[/tool]answer', "answer"),
    ("__IMAGE_SENT____CAPTION_SENT__", ""),
])
def test_visible_reply_keeps_image_previews_and_removes_protocol_markers(text, expected):
    assert _sanitize_visible_reply(text) == expected


@pytest.mark.parametrize("name", ["image_generator", "hd_image"])
def test_image_delivery_mode_controls_followup_and_duplicate_plaintext(name):
    deferred = f"Tool {name}: Image generated, NOT sent\nPermanent URL: {CDN}"
    sent = f"Tool {name}: __IMAGE_SENT__\nImage sent\nImage URL: {CDN}"
    assert _tool_results_need_followup([deferred])
    assert not _should_skip_plaintext_after_send([deferred], [deferred], False, "Comment")
    assert not _tool_results_need_followup([sent])
    assert _should_skip_plaintext_after_send([sent], [sent], False, "Duplicate")
    assert _tool_results_need_followup([sent, "Tool web_search: useful result"])
    assert _tool_results_need_followup([sent, "Error: another tool failed"])
    assert _tool_results_need_followup([f"Tool {name}: Error: could not upload"])
    assert not _should_skip_plaintext_after_send([], [sent], True, "Actual subsequent result")


@pytest.mark.parametrize("name,marker", [("send_file", "__FILE_SENT__"), ("send_media", "__MEDIA_SENT__")])
def test_delivered_caption_suppresses_only_redundant_plaintext(name, marker):
    sent = f"Tool {name}: {marker} attachment\n__CAPTION_SENT__"
    assert not _tool_results_need_followup([sent])
    assert _should_skip_plaintext_after_send([sent], [sent], False, "Duplicate caption")
    assert not _should_skip_plaintext_after_send([], [sent], True, "Later answer")
    assert _tool_results_need_followup([sent, "Tool web_search: result"])


def test_unrelated_results_cannot_claim_image_delivery():
    result = "Tool web_search: __IMAGE_SENT__\n__CAPTION_SENT__"
    assert _tool_results_need_followup([result])
    assert not _should_skip_plaintext_after_send([result], [result], False, "Actual answer")
