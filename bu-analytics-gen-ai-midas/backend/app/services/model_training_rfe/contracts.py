"""
Data contracts for the RFE pipeline.

Pure dataclasses / TypedDicts - no behaviour, no I/O. Shared by every class in the
package so consumers (routes, services, workers) never disagree on shape.

Design intent:
- WorkingFeatureSet: what Step 2 (screener) hands off to Step 3 (RFE).
- RfeJobConfig: everything an RfeService.run(job_id) needs to execute.
- IterationRecord: per-iteration payload written to storage and streamed via SSE.
- RfeFinalResult: the read-payload that Step 4 (feature review) consumes.
- FinalizedFeatureSet: the read-only payload that Step 5 (training config, owned by
  another dev) picks up via GET /rfe/monotone/{dataset_id}.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Literal, Optional


# ---------------------------------------------------------------------------
# Status enums
# ---------------------------------------------------------------------------


class RfeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class StopReason(str, Enum):
    AUC_DEGRADATION = "auc_degradation"
    FLOOR_REACHED = "floor_reached"
    NATURAL_CONVERGENCE = "natural_convergence"
    CANCELLED = "cancelled"


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------


@dataclass
class PrecomputedMetric:
    """
    A metric value pre-computed by an upstream agent (Feature Engineering / Screener).
    `source` lets us log lineage per guide Section 3.4 final paragraph.
    """

    value: float
    source: str = "upstream"  # "upstream" or "local"


@dataclass
class WorkingFeatureSet:
    """
    Output of Step 2 (Screener) = input to Step 3 (RFE).

    - `locked`: variables the modeler marked as must-have (Step 1).
    - `screened`: variables that passed the Step 2 dynamic filters.
    - `precomputed_metrics`: per-variable dict of metric-name -> PrecomputedMetric.
      Any metric missing here is recomputed locally by MetricEngine on the training
      partition (guide Section 3.4).
    """

    locked: List[str]
    screened: List[str]
    precomputed_metrics: Dict[str, Dict[str, PrecomputedMetric]] = field(default_factory=dict)

    @property
    def all_features(self) -> List[str]:
        # Locked first, then screened, de-duplicated while preserving order.
        seen = set()
        out: List[str] = []
        for v in list(self.locked) + list(self.screened):
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out


@dataclass
class RfeJobConfig:
    """
    Persisted payload every worker needs to execute the RFE loop.

    Written to StorageBackend.put_json(job_id, "config.json", ...) at /rfe/start
    so workers in another pod can rehydrate without any in-memory context.
    """

    job_id: str
    dataset_id: str
    target: str
    working_set: WorkingFeatureSet
    weight_col: Optional[str] = None
    problem_type: Literal["binary_classification"] = "binary_classification"
    # The user's identity is captured for audit (Section 11). Optional - local dev may skip.
    user_id: Optional[str] = None
    created_at_epoch: float = 0.0
    # True if the API pod already wrote train.parquet next to this config so workers
    # can skip DataFrameStateManager entirely (Redis-worker mode).
    train_parquet_available: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return _to_plain(self)


# ---------------------------------------------------------------------------
# Per-iteration output
# ---------------------------------------------------------------------------


@dataclass
class FeatureImportance:
    """SHAP mean(|value|) and native XGBoost importance, side-by-side per guide Section 4.5."""

    variable: str
    shap_importance: float
    native_importance: float
    shap_rank: int  # 1-indexed rank within this iteration (lower = more important)


@dataclass
class IterationRecord:
    """
    One row of the iteration table in the Step 3 UI + SSE tick payload.

    Mirrors the columns at model_training_agent_wireframe_v3.html lines 339-351:
    Iter / Feat / Drop / Elim rate / CV AUC / Test AUC / Delta / Status.
    """

    iteration: int
    feature_count: int
    features_in: List[str]
    features_dropped: List[str]
    elimination_band_label: str  # e.g. "Bot 2% (25-49)"
    cv_auc: float
    # ROC AUC of a fresh single-fit on the full (train-partition) feature set
    # scored against the held-out **test** partition when one exists. If the
    # dataset has no test partition this falls back to cv_auc.
    test_auc: float
    relative_delta_from_prev: Optional[float]  # None for iter 0
    importances: List[FeatureImportance]
    locked_zero_importance_flags: List[str] = field(default_factory=list)
    stop_reason: Optional[str] = None
    is_best: bool = False
    timestamp_epoch: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return _to_plain(self)


# ---------------------------------------------------------------------------
# Final result + HITL finalize
# ---------------------------------------------------------------------------


@dataclass
class VariableRow:
    """One row of the Step 4 feature-review table (retained + dropped tabs merged)."""

    variable: str
    locked: bool
    status: Literal["retained", "dropped"]
    drop_iteration: Optional[int]
    iv: Optional[float]
    orig_vif: Optional[float]  # from the full feature set (upstream or local-on-all)
    nvar_vif: Optional[float]  # recomputed on the final retained set; None for dropped
    abs_corr_target: Optional[float]
    shap_importance_best: Optional[float]
    rank_trajectory: List[Optional[int]]  # length = iterations; None after drop
    suggested_monotone: int  # -1, 0, +1 derived from bivariate corr sign
    bivariate_corr: Optional[float]  # signed (used to suggest monotone direction)


@dataclass
class RfeFinalResult:
    """What Step 4 UI reads via GET /rfe/result/{job_id}."""

    job_id: str
    dataset_id: str
    target: str
    starting_feature_count: int
    final_feature_count: int
    best_iteration: int
    total_iterations: int
    stop_reason: StopReason
    best_cv_auc: float
    best_test_auc: float
    iterations: List[IterationRecord]
    rows: List[VariableRow]
    # When the RFE halts on AUC degradation and the best iteration is not the
    # last iteration we ran, we "roll back" to the best one. This field
    # records the iteration index we rolled back *from* (i.e. the last
    # iteration index we actually ran). None otherwise.
    rolled_back_from_iteration: Optional[int] = None


@dataclass
class MonotoneConstraint:
    """Per-variable monotone direction. Applied to XGBoost / LightGBM / CatBoost only."""

    variable: str
    direction: Literal[-1, 0, 1]


@dataclass
class VariableOverride:
    """HITL override from Step 4."""

    include: List[str] = field(default_factory=list)  # re-include dropped
    exclude: List[str] = field(default_factory=list)  # exclude retained


@dataclass
class FinalizedFeatureSet:
    """
    Written to StorageBackend as `final_features.json` + `monotone.json` on /rfe/finalize.
    Read by Step 5 (training config) via GET /rfe/monotone/{dataset_id}.
    """

    job_id: str
    dataset_id: str
    target: str
    features: List[str]
    locked: List[str]
    monotone: List[MonotoneConstraint]
    final_vifs: Dict[str, float]  # N-var VIF recomputed if user changed selection
    finalized_at_epoch: float
    user_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Small helper to dump nested dataclasses to JSON-safe dicts
# ---------------------------------------------------------------------------


def _to_plain(obj: Any) -> Any:
    """
    Recursively convert dataclass/Enum/lists/dicts to plain JSON-serialisable types.
    We deliberately avoid `json.dumps(..., default=str)` so the shape is predictable
    in tests and doesn't silently hide non-serialisable leaves.
    """
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_plain(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, list):
        return [_to_plain(x) for x in obj]
    if isinstance(obj, tuple):
        return [_to_plain(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj
