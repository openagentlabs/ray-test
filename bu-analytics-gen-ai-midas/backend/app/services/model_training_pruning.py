"""
Model training — feature pruning (codebook reference)

This module documents the pruning workflow exposed in the MIDAS UI (Model Training
step 7, Model pruning panel). The browser runs a deterministic *simulation* for
human-in-the-loop review; production pruning would reuse the same constraints:

- **Performance floor**: pruned test metric must stay within ``max_drop_pct`` of the
  baseline test score.
- **Feature budget**: retain at most ``max_keep`` non-zero / important features.
- **Search**: Bayesian-style trials per iteration (UI parameter) explore drop order.
- **Locked features**: high-importance or policy-marked variables are never dropped
  until lower-ranked candidates are exhausted (see ``locked`` in surviving-feature rows).

Integration points with the rest of the stack
----------------------------------------------
- Training payloads: ``model_training_manual_configuration`` / segment variants persist
  ``metrics``, ``iteration_history``, ``used_features``, ``feature_importance_count``.
- Screener: pruned candidates can be appended as synthetic rows (see frontend
  ``appendPrunedScreenerQueue``).

The UI codebook is served via ``GET /api/v1/chat/get-codebook/pruning/pruning`` which
returns this file as ``source_code`` for download as ``.py`` / ``.ipynb``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple


@dataclass
class PruningConstraintResult:
    ok: bool
    test_metric: float
    train_metric: float
    feature_count: int
    message: str


def evaluate_pruning_step(
    baseline_test: float,
    candidate_test: float,
    max_drop_pct: float,
    *,
    min_features: int = 1,
    current_feature_count: int = 0,
) -> PruningConstraintResult:
    """
    Return whether a candidate model still satisfies the performance floor.

    ``max_drop_pct`` is a *relative* allowed drop from baseline (e.g. 5 => 5%).
    """
    floor = baseline_test * (1.0 - max_drop_pct / 100.0)
    ok = candidate_test >= floor and current_feature_count >= min_features
    msg = "pass" if ok else "below floor or too few features"
    return PruningConstraintResult(
        ok=ok,
        test_metric=candidate_test,
        train_metric=0.0,
        feature_count=current_feature_count,
        message=msg,
    )


def rank_features_for_pruning(
    feature_names: Sequence[str],
    importance_scores: Sequence[float],
    locked_mask: Sequence[bool],
) -> List[Tuple[str, float, bool]]:
    """
    Pair names with scores; ``locked_mask`` parallel array — locked rows sort to the
    head so they survive until the budget forces otherwise.
    """
    rows = list(zip(feature_names, importance_scores, locked_mask))
    rows.sort(key=lambda r: (-r[2], -r[1], r[0]))  # locked first, then importance
    return rows


def build_pruning_trace_payload(
    model_id: str,
    steps: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Shape used by the UI export / audit log (JSON)."""
    return {"model_id": model_id, "pruning_steps": steps, "schema_version": 1}


# --- Placeholder for a future server-side pruner ---------------------------------
class ModelPruningService:
    """Reserved: orchestrate Optuna / CV drops against persisted artifacts."""

    def __init__(self) -> None:
        pass

    def prune(self, request: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Server-side pruning is not wired; UI uses simulation.")
