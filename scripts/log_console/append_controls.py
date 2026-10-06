from .append_render import LEVELS
from .append_state import AppendState, Filters
from .scopes import SCOPE_KEYS


def filter_key(state: AppendState, key: str) -> None:
    """Change future selections without mutating an existing frozen candidate set."""
    controls = state.filters
    if key in "+=-":
        controls.minimum = max(0, min(len(LEVELS) - 1, controls.minimum + (1 if key == "-" else -1)))
    elif key in SCOPE_KEYS:
        controls.scopes.symmetric_difference_update({SCOPE_KEYS[key]})
    elif key == "o":
        controls.ollama = not controls.ollama
    state.flush_repeats(force=True)
    state.notice(f"filters: minimum={LEVELS[controls.minimum]} scopes={','.join(sorted(controls.scopes))} Ollama={controls.ollama}")


def detail_key(state: AppendState, key: str) -> None:
    """Replay changed detail explicitly; ordinary follow stays follow."""
    if key == "f":
        state.flush_repeats(force=True)
        state.filters.folded = not state.filters.folded
        state.replay(f"folded={state.filters.folded}", count=5, freeze=False)
    else:
        scope = "tool" if key == "T" else "provider"
        current = state.filters.tool_depth if key == "T" else state.filters.provider_depth
        depth = (current + 1) % 3
        if key == "T":
            state.filters.tool_depth = depth
        else:
            state.filters.provider_depth = depth
        state.replay(f"{scope} depth={depth}: summary/JSON/retained evidence", count=1, scope=scope)


def dispatch(state: AppendState, key: str) -> None:
    """All commands are local; no branch can signal an application/container."""
    if key in {"q", "\x03", "\x04"}:
        state.terminal.stop = "requested quit"
    elif key in SCOPE_KEYS or key in {"+", "=", "-", "o"}:
        filter_key(state, key)
    elif key in {"f", "T", "P"}:
        detail_key(state, key)
    elif key in {"r", "e"}:
        state.pause()
        state.replay("warnings/errors/recognized failures UNFILTERED" if key == "e" else "recent matching", errors=key == "e")
    elif key in {"[", "]", "L", "l"}:
        state.navigate(-1 if key in {"[", "L"} else 1)
    elif key in {"\r", "\n"}:
        state.inspect()
    elif key in {"n", "N"}:
        state.pause()
        state.show_page(state.page_number + (1 if key == "n" else -1))
    elif key == " ":
        if state.paused:
            state.resume()
        else:
            state.pause()
            state.notice("display paused; ingestion continues; Space resumes")
    elif key == "0":
        state.filters = Filters()
        state.candidates, state.selected, state.snapshot = (), None, None
        state.flush_repeats(force=True)
        state.resume()
        state.notice("display controls reset; retained history unchanged")
    elif key in {"?", "h"}:
        state.help()
    elif key == "i":
        state.inspector()
