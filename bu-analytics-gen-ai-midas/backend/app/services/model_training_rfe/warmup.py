"""
RFE warmup - pre-load the heavy scientific libraries that RFE needs.

On a cold Python process, the **first** `import shap` triggers matplotlib's
font cache build which blocks for 20-45 seconds. Because SHAP is only needed
during an RFE iteration, that one-time cost lands inside the RFE worker
thread where the user sees no output, making the whole app look frozen.

This module ships two helpers:

* ``ensure_mpl_config_dir()`` - pin matplotlib's cache to a persistent,
  writable directory (defaults to ``~/.midas/matplotlib`` or the RFE
  artifacts dir if set) so subsequent process restarts do **not** rebuild
  the cache.

* ``start_rfe_warmup(background=True)`` - triggers the imports of
  ``matplotlib``, ``xgboost``, and ``shap`` on a dedicated daemon thread.
  Logs when the warmup finishes. Safe to call multiple times (idempotent).

Call these from ``main.py`` at startup. After that, every RFE iteration is
fast because the imports, OpenMP runtime, and font cache are already hot.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Optional

from app.core.logging_config import get_logger

_logger = get_logger(__name__)

_warmup_thread: Optional[threading.Thread] = None
_warmup_started_at: Optional[float] = None
_warmup_completed: bool = False
_warmup_lock = threading.Lock()


def ensure_mpl_config_dir() -> str:
    """
    Pin matplotlib cache directory to a persistent, writable location.

    Priority:
      1. ``MPLCONFIGDIR`` env var if already set and writable.
      2. ``RFE_ARTIFACTS_DIR/matplotlib`` if the RFE artifacts dir is set.
      3. ``~/.midas/matplotlib`` as the universal fallback.

    Returns the resolved path (also exported as ``MPLCONFIGDIR``).
    """
    candidates = []
    existing = os.environ.get("MPLCONFIGDIR")
    if existing:
        candidates.append(Path(existing))
    artifacts = os.environ.get("RFE_ARTIFACTS_DIR")
    if artifacts:
        candidates.append(Path(artifacts) / "matplotlib")
    candidates.append(Path.home() / ".midas" / "matplotlib")
    candidates.append(Path("/tmp/midas-matplotlib"))

    for p in candidates:
        try:
            p.mkdir(parents=True, exist_ok=True)
            probe = p / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
            resolved = str(p.resolve())
            os.environ["MPLCONFIGDIR"] = resolved
            _logger.info("matplotlib cache pinned to %s", resolved)
            return resolved
        except Exception as exc:
            _logger.debug("MPLCONFIGDIR candidate %s unusable: %s", p, exc)
            continue

    _logger.warning("No writable MPLCONFIGDIR found - matplotlib may rebuild its font cache on every process start")
    return os.environ.get("MPLCONFIGDIR", "")


def _warmup_impl() -> None:
    """Actual import work - runs on a background daemon thread."""
    global _warmup_completed
    t0 = time.time()
    stages: list[tuple[str, float]] = []

    try:
        import matplotlib  # noqa: F401 - triggers font cache build on first run
        stages.append(("matplotlib", time.time() - t0))
    except Exception as exc:
        _logger.warning("RFE warmup: matplotlib import failed: %s", exc)

    try:
        t = time.time()
        import matplotlib.pyplot  # noqa: F401
        stages.append(("matplotlib.pyplot", time.time() - t))
    except Exception as exc:
        _logger.debug("RFE warmup: matplotlib.pyplot unavailable: %s", exc)

    try:
        t = time.time()
        import xgboost  # noqa: F401
        stages.append(("xgboost", time.time() - t))
    except Exception as exc:
        _logger.info(
            "RFE warmup: xgboost import failed (Step 3 will surface a friendly error "
            "when the user tries to run RFE): %s",
            exc,
        )

    try:
        t = time.time()
        import shap  # noqa: F401
        stages.append(("shap", time.time() - t))
    except Exception as exc:
        _logger.info(
            "RFE warmup: shap import failed (Step 3 will fall back to native XGBoost "
            "importance): %s",
            exc,
        )

    total = time.time() - t0
    _warmup_completed = True
    _logger.info(
        "RFE warmup completed in %.2fs (%s)",
        total,
        ", ".join(f"{name}={secs:.2f}s" for name, secs in stages) or "no stages ran",
    )


def start_rfe_warmup(background: bool = True) -> None:
    """
    Trigger the heavy imports (matplotlib, xgboost, shap).

    ``background=True`` (default) runs warmup on a daemon thread so FastAPI
    startup is not blocked. The first RFE iteration will wait for the warmup
    to finish only if it kicks off before the thread completes (see
    ``wait_for_warmup``); subsequent iterations are instant.
    """
    global _warmup_thread, _warmup_started_at
    with _warmup_lock:
        if _warmup_thread is not None and _warmup_thread.is_alive():
            _logger.debug("RFE warmup already running")
            return
        if _warmup_completed:
            return
        _warmup_started_at = time.time()
        if not background:
            _warmup_impl()
            return
        _warmup_thread = threading.Thread(
            target=_warmup_impl, name="rfe-warmup", daemon=True
        )
        _warmup_thread.start()
        _logger.info("RFE warmup started in background (imports: matplotlib, xgboost, shap)")


def wait_for_warmup(timeout: float = 60.0) -> bool:
    """Block until background warmup finishes (or timeout). Used by RfeService."""
    with _warmup_lock:
        thread = _warmup_thread
    if thread is None or not thread.is_alive():
        return _warmup_completed
    thread.join(timeout=timeout)
    return _warmup_completed
