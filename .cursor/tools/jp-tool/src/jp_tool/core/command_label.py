"""CLI argv helpers."""

from __future__ import annotations

import shlex
import sys


def argv_command_label(*, default: str = "jp-tool") -> str:
    """Return a shell-safe label for the current invocation."""
    if len(sys.argv) <= 1:
        return default
    return "jp-tool " + " ".join(shlex.quote(arg) for arg in sys.argv[1:])
