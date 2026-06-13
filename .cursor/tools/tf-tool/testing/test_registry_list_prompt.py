"""Unit tests for registry list interactive prompts."""

from __future__ import annotations

from tf_tool.actions.registry_search.list_prompt import (
    ListPromptAction,
    _parse_key,
)


def test_parse_key_esc_exits() -> None:
    result = _parse_key("\x1b")
    assert result is not None
    assert result.action == ListPromptAction.EXIT


def test_parse_key_up_is_previous_page() -> None:
    result = _parse_key("\x1b[A")
    assert result is not None
    assert result.action == ListPromptAction.PREV_PAGE


def test_parse_key_down_is_next_page() -> None:
    result = _parse_key("\x1b[B")
    assert result is not None
    assert result.action == ListPromptAction.NEXT_PAGE


def test_parse_key_enter_exits() -> None:
    result = _parse_key("\n")
    assert result is not None
    assert result.action == ListPromptAction.EXIT
