"""Interactive prompts for registry list commands."""

from __future__ import annotations

import sys
import termios
import tty
from dataclasses import dataclass
from enum import Enum


class ListPromptAction(Enum):
    """Outcome of an interactive list prompt."""

    EXIT = "exit"
    NEXT_PAGE = "next_page"
    PREV_PAGE = "prev_page"
    SELECT = "select"


@dataclass(frozen=True)
class ListPromptResult:
    """Parsed user input from the list prompt."""

    action: ListPromptAction
    row: int | None = None


_PROMPT_TEMPLATE = (
    "\nPage {page} — Enter row number to download (↑ previous page, ↓ next page, Esc to exit): "
)


def _read_key() -> str:
    """Read one key or escape sequence from stdin (cbreak mode)."""
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        first = sys.stdin.read(1)
        if first != "\x1b":
            return first

        second = sys.stdin.read(1)
        if not second:
            return "\x1b"
        if second != "[":
            return first + second

        third = sys.stdin.read(1)
        if not third:
            return first + second
        return first + second + third
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _parse_key(key: str) -> ListPromptResult | None:
    """Map a raw key / escape sequence to a prompt result."""
    if key == "\x1b":
        sys.stdout.write("\n")
        return ListPromptResult(action=ListPromptAction.EXIT)
    if key == "\x1b[A":
        return ListPromptResult(action=ListPromptAction.PREV_PAGE)
    if key == "\x1b[B":
        return ListPromptResult(action=ListPromptAction.NEXT_PAGE)
    if key in ("\r", "\n"):
        sys.stdout.write("\n")
        return ListPromptResult(action=ListPromptAction.EXIT)
    return None


def read_list_prompt(*, first_row: int, last_row: int, page: int) -> ListPromptResult:
    """Read row selection or page navigation; exit on Esc / empty line."""
    if first_row > last_row or not sys.stdin.isatty():
        return ListPromptResult(action=ListPromptAction.EXIT)

    sys.stdout.write(_PROMPT_TEMPLATE.format(page=page))
    sys.stdout.flush()

    key = _read_key()
    parsed = _parse_key(key)
    if parsed is not None:
        return parsed

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        remainder = sys.stdin.readline()
        raw = (key + remainder).strip()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    if not raw:
        return ListPromptResult(action=ListPromptAction.EXIT)

    try:
        selection = int(raw)
    except ValueError:
        print("Enter a number from the list, or use ↑/↓ to change page.", file=sys.stderr)
        return ListPromptResult(action=ListPromptAction.EXIT)

    if selection < first_row or selection > last_row:
        print(
            f"Choose a row between {first_row} and {last_row}, or use ↑/↓ to change page.",
            file=sys.stderr,
        )
        return ListPromptResult(action=ListPromptAction.EXIT)

    return ListPromptResult(action=ListPromptAction.SELECT, row=selection)


def read_row_selection(*, max_rows: int) -> int | None:
    """Read a 1-based row number, or ``None`` when the user exits (Esc / empty line)."""
    result = read_list_prompt(first_row=1, last_row=max_rows, page=1)
    if result.action == ListPromptAction.SELECT:
        return result.row
    return None
