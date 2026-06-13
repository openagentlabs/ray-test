from contextvars import ContextVar
from typing import Dict, Optional

LlmSelection = Dict[str, str]

_current_selection: ContextVar[Optional[LlmSelection]] = ContextVar("llm_selection", default=None)
_session_selections: Dict[str, LlmSelection] = {}


def set_current_selection(selection: Optional[LlmSelection]) -> None:
    _current_selection.set(selection)


def get_current_selection() -> Optional[LlmSelection]:
    return _current_selection.get()


def update_session_selection(token: str, selection: LlmSelection) -> None:
    if not token:
        return
    _session_selections[token] = dict(selection)


def get_session_selection(token: str) -> Optional[LlmSelection]:
    if not token:
        return None
    return _session_selections.get(token)
