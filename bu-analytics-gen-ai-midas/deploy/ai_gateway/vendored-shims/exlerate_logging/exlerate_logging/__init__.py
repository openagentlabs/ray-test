"""MIDAS shim for exlerate_logging — stdlib-backed `get_logger`.

The upstream corporate package `exlerate-logging` (published to JFrog) provides
a small convenience wrapper around Python's stdlib logging. The c1-api source
tree (`ai_gateway/src/aigtw_c1_api/`) uses it *only* for the `get_logger(name)`
call — nothing else is imported. This shim supplies exactly that symbol, backed
by `logging.getLogger`, so the MIDAS build chain never needs to pull the real
package from corporate Artifactory.

If the upstream package ever starts to be used for something richer (structured
JSON logs, OTLP exporters, etc.), extend this module rather than pulling in the
JFrog dependency.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

_DEFAULT_FORMAT = (
    "%(asctime)s %(levelname)s [%(name)s] %(message)s"
)

_configured = False


def _configure_root_once() -> None:
    """Attach one stream handler to the root logger on first use.

    Mirrors the upstream package's behaviour of configuring a basicConfig-like
    output to stdout at a level driven by `LOG_LEVEL` / `LOGGING_LEVEL`.
    """
    global _configured
    if _configured:
        return

    level_name = os.getenv("LOG_LEVEL") or os.getenv("LOGGING_LEVEL") or "INFO"
    level = getattr(logging, level_name.upper(), logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    if not root.handlers:
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.setFormatter(logging.Formatter(_DEFAULT_FORMAT))
        root.addHandler(handler)

    _configured = True


def get_logger(name: str, **_kwargs: Any) -> logging.Logger:
    """Return a stdlib logger for `name`.

    Accepts (and ignores) arbitrary keyword arguments so we tolerate any future
    extension callers may hand us — the real corporate package occasionally
    grows kwargs like `tags=...` or `extra_fields=...`.
    """
    _configure_root_once()
    return logging.getLogger(name)


__all__ = ["get_logger"]
