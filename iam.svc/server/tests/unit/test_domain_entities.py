"""Domain entity aliases match persistence records."""

from __future__ import annotations

from iam_service.database.models.records import UserRecord
from iam_service.domain.entities import User


def test_user_alias_is_user_record() -> None:
    """``User`` domain type is the canonical ``UserRecord`` shape."""
    assert User is UserRecord
