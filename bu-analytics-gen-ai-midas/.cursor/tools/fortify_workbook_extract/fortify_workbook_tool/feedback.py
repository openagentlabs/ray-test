"""Concise ANSI-colored operator feedback (respects NO_COLOR, non-TTY)."""

from __future__ import annotations

import os
import sys
from typing import Optional, TextIO


class ColoredFeedback:
    """
    Short, meaningful messages for CLI runs.

    Operational lines use **stderr** so they stay ordered vs subprocess/pip output.
    Disabled when ``NO_COLOR`` is set, output is not a TTY, or ``force_plain=True``.
    """

    _RESET = "\033[0m"
    _RED = "\033[91m"
    _GREEN = "\033[92m"
    _YELLOW = "\033[93m"
    _BLUE = "\033[94m"
    _CYAN = "\033[96m"
    _DIM = "\033[2m"

    def __init__(
        self,
        *,
        diag_stream: TextIO = sys.stderr,
        stdout: TextIO = sys.stdout,
        force_plain: bool = False,
    ) -> None:
        self._diag = diag_stream
        self._out = stdout
        self._force_plain = force_plain
        self._no_color = force_plain or os.environ.get("NO_COLOR", "").strip() != ""

    def configure(self, *, no_color: bool = False) -> None:
        """Call after argparse (e.g. ``--no-color``)."""
        self._no_color = bool(no_color) or os.environ.get("NO_COLOR", "").strip() != ""

    def _use_color(self, stream: TextIO) -> bool:
        return bool(stream.isatty()) and not self._no_color and not self._force_plain

    def _say(self, stream: TextIO, color: str, prefix: str, msg: str) -> None:
        if self._use_color(stream):
            stream.write(f"{color}{prefix}{self._RESET} {msg}\n")
        else:
            stream.write(f"{prefix} {msg}\n")

    def step(self, msg: str) -> None:
        """In-progress step (cyan •)."""
        self._say(self._diag, self._CYAN, "•", msg)

    def ok(self, msg: str) -> None:
        """Success line (green ✓)."""
        self._say(self._diag, self._GREEN, "✓", msg)

    def info(self, msg: str) -> None:
        """Neutral info (blue …)."""
        self._say(self._diag, self._BLUE, "…", msg)

    def warn(self, msg: str) -> None:
        """Warning (yellow !)."""
        self._say(self._diag, self._YELLOW, "!", msg)

    def error(self, msg: str) -> None:
        """Error (red ×)."""
        self._say(self._diag, self._RED, "×", msg)

    def dim(self, msg: str, *, stream: Optional[TextIO] = None) -> None:
        """Secondary detail line (stderr unless ``stream`` set)."""
        fh = stream or self._diag
        if self._use_color(fh):
            fh.write(f"{self._DIM}{msg}{self._RESET}\n")
        else:
            fh.write(f"{msg}\n")
