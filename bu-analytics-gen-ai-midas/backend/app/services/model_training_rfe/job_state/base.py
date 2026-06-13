"""
JobStateStore ABC.

Responsibility: live, low-cardinality fields needed to render the Step 3 UI and
cancel in-flight jobs. Big payloads (iteration records, SHAP matrices) live in
StorageBackend, not here.

Fields we keep hot:
  - status (pending|running|completed|failed|cancelled|interrupted)
  - current_iteration, total_features, best_iteration
  - cancel_flag (set by /rfe/cancel, read by RfeService between iterations)
  - heartbeat_at (worker updates every N seconds; API-side reaper can detect stale)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class JobStateRow:
    job_id: str
    status: str = "pending"
    message: str = ""
    dataset_id: Optional[str] = None
    user_id: Optional[str] = None
    current_iteration: int = 0
    total_features: int = 0
    best_iteration: int = -1
    latest_cv_auc: Optional[float] = None
    cancel_flag: bool = False
    heartbeat_at: float = 0.0
    created_at: float = 0.0
    updated_at: float = 0.0
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class JobStateStore(ABC):
    @abstractmethod
    def create(self, row: JobStateRow) -> None: ...

    @abstractmethod
    def get(self, job_id: str) -> Optional[JobStateRow]: ...

    @abstractmethod
    def update(self, job_id: str, **fields: Any) -> None: ...

    @abstractmethod
    def request_cancel(self, job_id: str) -> bool: ...

    @abstractmethod
    def list_active(self) -> List[JobStateRow]: ...

    @abstractmethod
    def delete(self, job_id: str) -> None: ...
