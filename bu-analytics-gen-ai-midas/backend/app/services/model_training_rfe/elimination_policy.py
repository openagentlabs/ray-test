"""
AdaptiveEliminationPolicy - guide Section 4.2 + 4.4.

Band schedule (guide Table 4):
  100+ features -> eliminate 5% per iteration
  50-99         -> 3%
  25-49         -> 2%
  <25           -> 1% (floor 1)

Stop rules (guide Section 4.4):
  - Hard floor: stop when feature count would drop below `min_features` (default 6).
  - AUC degradation: stop when iteration CV AUC drops > `auc_drop_threshold`
    (default 0.003) vs the best-so-far and hasn't recovered within
    `patience` iterations.
  - Locked vars never dropped - filtered out of candidate pool before picking
    bottom-X.

Returns:
  - `select_to_drop(importances, locked)` -> list of variable names to drop next.
  - `should_stop(history)` -> (stop: bool, reason: Optional[str]).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple


@dataclass
class EliminationBand:
    lower: int  # inclusive
    upper: int  # inclusive; math.inf for open-ended
    rate: float
    label: str


_BANDS: List[EliminationBand] = [
    EliminationBand(lower=100, upper=10_000_000, rate=0.05, label="Top 5% (100+)"),
    EliminationBand(lower=50, upper=99, rate=0.03, label="Mid 3% (50-99)"),
    EliminationBand(lower=25, upper=49, rate=0.02, label="Bot 2% (25-49)"),
    EliminationBand(lower=1, upper=24, rate=0.01, label="Fin 1% (<25)"),
]


class AdaptiveEliminationPolicy:
    def __init__(
        self,
        *,
        min_features: int = 6,
        auc_drop_threshold: float = 0.003,
        patience: int = 2,
    ) -> None:
        self.min_features = max(1, int(min_features))
        self.auc_drop_threshold = float(auc_drop_threshold)
        self.patience = max(1, int(patience))

    def band_for(self, feature_count: int) -> EliminationBand:
        for b in _BANDS:
            if b.lower <= feature_count <= b.upper:
                return b
        # Fallback (should not hit): slowest rate
        return _BANDS[-1]

    def drop_count(self, feature_count: int) -> int:
        band = self.band_for(feature_count)
        n_drop = max(1, math.floor(feature_count * band.rate))
        # Don't drop below the floor
        if feature_count - n_drop < self.min_features:
            n_drop = max(0, feature_count - self.min_features)
        return n_drop

    def select_to_drop(
        self,
        *,
        shap_ordered: Sequence[Tuple[str, float, float]],
        locked: Sequence[str],
    ) -> List[str]:
        """
        shap_ordered: (name, mean_abs_shap, native_importance) descending.
        locked: variables that must remain regardless of importance.

        Returns bottom-X candidates excluding locked.
        """
        locked_set = set(locked)
        feature_count = len(shap_ordered)
        n_drop = self.drop_count(feature_count)
        if n_drop <= 0:
            return []
        # bottom of the list = lowest importance
        candidates = [name for name, *_ in reversed(shap_ordered) if name not in locked_set]
        return candidates[:n_drop]

    def should_stop(
        self,
        *,
        cv_auc_history: Sequence[float],
        feature_count_after_drop: int,
    ) -> Tuple[bool, Optional[str]]:
        """
        Decide whether to stop after the current iteration completed.
        """
        if feature_count_after_drop < self.min_features:
            return True, "floor_reached"
        if not cv_auc_history:
            return False, None
        best = max(cv_auc_history)
        # Natural convergence: 3 consecutive iterations with negligible (< 1e-5) change.
        if len(cv_auc_history) >= 3:
            last3 = cv_auc_history[-3:]
            if max(last3) - min(last3) < 1e-5:
                return True, "natural_convergence"
        # AUC degradation check (patience-aware).
        if len(cv_auc_history) > self.patience:
            recent = cv_auc_history[-self.patience :]
            if all(best - a > self.auc_drop_threshold for a in recent):
                return True, "auc_degradation"
        return False, None
