"""Abstractions for secret retrieval (DIP: callers depend on ISecretsReader, not boto3)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict


class ISecretsReader(ABC):
    """Strategy for reading a secret payload by id (ARN, name, or partial ARN)."""

    @abstractmethod
    def get_secret_json(self, secret_id: str) -> Dict[str, Any]:
        """Return parsed JSON object from SecretString. Raises if missing or invalid."""
