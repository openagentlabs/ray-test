"""
Model-training RFE package.

Exposes the job manager facade for API routes and the RfeService class for the
worker process. Factory + ABCs live one level down for easy substitution in
tests or alternate cloud configurations.
"""

from .contracts import (
    FeatureImportance,
    FinalizedFeatureSet,
    IterationRecord,
    MonotoneConstraint,
    RfeFinalResult,
    RfeJobConfig,
    RfeStatus,
    StopReason,
    VariableOverride,
    VariableRow,
    WorkingFeatureSet,
)
from .job_manager import RfeJobManager, get_job_manager
from .rfe_service import RfeService

__all__ = [
    "FeatureImportance",
    "FinalizedFeatureSet",
    "IterationRecord",
    "MonotoneConstraint",
    "RfeFinalResult",
    "RfeJobConfig",
    "RfeStatus",
    "RfeJobManager",
    "RfeService",
    "StopReason",
    "VariableOverride",
    "VariableRow",
    "WorkingFeatureSet",
    "get_job_manager",
]
