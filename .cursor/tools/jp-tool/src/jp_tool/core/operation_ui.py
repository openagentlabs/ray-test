"""Terminal operation progress: spinner, colored replay, and summary table."""

from __future__ import annotations

import contextvars
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, TypeVar

from rich.console import Console
from rich.live import Live
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text

T = TypeVar("T")

_PLAIN_ENV: Final[str] = "JP_TOOL_PLAIN"
_FORCE_UI_ENV: Final[str] = "JP_TOOL_UI"

_WARNING_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(warn(?:ing)?|deprecated)\b",
    re.IGNORECASE,
)
_ERROR_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(error|failed|failure|fatal)\b",
    re.IGNORECASE,
)
_DEBUG_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(debug|trace)\b",
    re.IGNORECASE,
)


@dataclass
class MessageCounts:
    """Aggregated message levels for the session summary."""

    ordinary: int = 0
    result: int = 0
    warning: int = 0
    error: int = 0
    info: int = 0
    debug: int = 0

    @property
    def total(self) -> int:
        return self.ordinary + self.result + self.warning + self.error + self.info + self.debug


class OperationSession:
    """Spinner-led operation log; UI writes to stderr, stdout stays clean for JSON."""

    def __init__(self) -> None:
        self.console = Console(stderr=True, highlight=False)
        self.counts = MessageCounts()
        self.commands: list[str] = []

    @staticmethod
    def start() -> OperationSession:
        """Create and register the active session."""
        session = OperationSession()
        _session_var.set(session)
        return session

    @staticmethod
    def current() -> OperationSession | None:
        return _session_var.get()

    def run_operation(
        self,
        operation: str,
        command: str,
        fn: Callable[[], T],
    ) -> T:
        """Show spinner during ``fn``; caller replays output when ready."""
        self.commands.append(command)
        self.counts.ordinary += 1
        label = Text.assemble(
            (operation, "blue"),
            ("  ", ""),
            (command, "dim"),
        )
        spinner = Spinner("dots", text=label, style="blue")
        with Live(spinner, console=self.console, refresh_per_second=12, transient=False):
            return fn()

    def replay_success(self, text: str) -> None:
        """Replay successful captured output in green."""
        self.replay_text(text, kind="result")

    def replay_text(
        self,
        text: str,
        *,
        kind: str = "result",
        command: str | None = None,
    ) -> None:
        """Print captured output under the last spinner."""
        if command:
            self.commands.append(command)
        self._emit_block(text, kind=kind)

    def record_failure(self, message: str, *, command: str | None = None) -> None:
        if command:
            self.commands.append(command)
        self.counts.error += 1
        self.console.print(Text(message, style="red"))

    def finish_summary(self) -> None:
        """Render the color-coded totals table under all prior output."""
        table = Table(title="jp-tool session summary", show_header=True, header_style="bold")
        table.add_column("Level", style="bold")
        table.add_column("Count", justify="right")

        rows: list[tuple[str, int, str]] = [
            ("ordinary", self.counts.ordinary, "blue"),
            ("result", self.counts.result, "green"),
            ("warning", self.counts.warning, "yellow"),
            ("error", self.counts.error, "red"),
            ("info", self.counts.info, "cyan"),
            ("debug", self.counts.debug, "dim"),
            ("total", self.counts.total, "bold white"),
        ]
        for level, count, style in rows:
            table.add_row(Text(level, style=style), str(count))
        self.console.print()
        self.console.print(table)
        if self.commands:
            self.console.print(Text(f"Commands run: {len(self.commands)}", style="dim"))

    def _emit_block(self, text: str, *, kind: str) -> None:
        if not text.strip():
            return
        for line in text.splitlines():
            level = _classify_line(line, default=kind)
            self._bump(level)
            self.console.print(Text(line, style=_kind_style(level)))
        if not text.endswith("\n"):
            self.console.print()

    def _bump(self, level: str) -> None:
        if level == "warning":
            self.counts.warning += 1
        elif level == "error":
            self.counts.error += 1
        elif level == "debug":
            self.counts.debug += 1
        elif level == "info":
            self.counts.info += 1
        elif level == "result":
            self.counts.result += 1
        else:
            self.counts.ordinary += 1


_session_var: contextvars.ContextVar[OperationSession | None] = contextvars.ContextVar(
    "jp_tool_operation_session",
    default=None,
)


def ui_enabled() -> bool:
    """True when interactive operation UI should run (stderr TTY)."""
    if os.environ.get(_PLAIN_ENV) == "1":
        return False
    if os.environ.get(_FORCE_UI_ENV) == "1":
        return True
    return sys.stderr.isatty()


def get_session() -> OperationSession | None:
    return OperationSession.current()


def run_if_session[T](
    operation: str,
    command: str,
    fn: Callable[[], T],
) -> T:
    """Run with spinner when a session is active; otherwise call ``fn`` directly."""
    session = get_session()
    if session is None:
        return fn()
    return session.run_operation(operation, command, fn)


def _kind_style(kind: str) -> str:
    return {
        "ordinary": "blue",
        "result": "green",
        "warning": "yellow",
        "error": "red",
        "info": "cyan",
        "debug": "dim",
    }.get(kind, "blue")


def _classify_line(line: str, *, default: str) -> str:
    if _ERROR_PATTERN.search(line):
        return "error"
    if _WARNING_PATTERN.search(line):
        return "warning"
    if _DEBUG_PATTERN.search(line):
        return "debug"
    if default in {"result", "error", "warning"}:
        return default
    return "info" if line.strip() else default
