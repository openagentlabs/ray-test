"""Abstract base for AWS connection identity objects."""

from __future__ import annotations

from abc import ABC, abstractmethod


class ConnectionInfoBase(ABC):
    """Base type for read-only AWS CLI connection descriptors."""

    @property
    @abstractmethod
    def profile(self) -> str:
        """Read-only AWS CLI profile name."""

    @property
    @abstractmethod
    def region(self) -> str:
        """Read-only AWS region id."""

    @property
    def connection_key(self) -> str:
        """Stable registry key combining profile and region."""
        return f"{self.profile}@{self.region}"
