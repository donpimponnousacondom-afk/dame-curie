from types import SimpleNamespace

from bot import MaxwellBot
from bot_tools import _taint_gate_blocks


class _Tool:
    def __init__(self, bot):
        self.bot = bot


def _tainted_bot(**cfg):
    return SimpleNamespace(
        config=SimpleNamespace(**cfg),
        is_message_tainted=lambda m: True,
    )


def test_a_tainted_turn_is_blocked():
    assert _taint_gate_blocks(_Tool(_tainted_bot()), object(), {}) is True


def test_an_out_of_band_confirm_unblocks_it():
    tool = _Tool(_tainted_bot())
    assert _taint_gate_blocks(tool, object(), {"_confirmed": True}) is False


def test_disable_taint_gate_actually_disables_the_gate():
    """The .env switch used to be read only by the dispatcher.

    Every per-tool copy kept refusing, so setting it looked broken for
    shell.
    """
    tool = _Tool(_tainted_bot(DISABLE_TAINT_GATE=True))
    assert _taint_gate_blocks(tool, object(), {}) is False


def test_a_clean_turn_is_not_blocked():
    bot = SimpleNamespace(config=SimpleNamespace(), is_message_tainted=lambda m: False)
    assert _taint_gate_blocks(_Tool(bot), object(), {}) is False


def test_ordinary_chat_still_travels_light():
    assert not MaxwellBot._ACTION_TOOL_HINT_RE.search("lol yeah exactly")
