"""IAM DynamoDB item models (Pydantic)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from iam_service.database.models.records import LoginRecord, UserRecord, UserTypeRecord


def test_user_record_ignores_legacy_password_field() -> None:
    rec = UserRecord.model_validate(
        {
            "id": "u1",
            "created_at": "t",
            "updated_at": "t",
            "password": "legacy",
            "first_name": "Ada",
            "last_name": "Lovelace",
        },
    )
    assert rec.first_name == "Ada"
    assert not hasattr(rec, "password") or "password" not in rec.model_dump()


def test_user_type_record_forbids_extra_keys() -> None:
    with pytest.raises(ValidationError):
        UserTypeRecord.model_validate(
            {
                "id": "t1",
                "created_at": "t",
                "updated_at": "t",
                "code": "admin",
                "display_name": "Admin",
                "unexpected": True,
            },
        )


def test_login_record_round_trip() -> None:
    rec = LoginRecord(
        id="l1",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        user_id="u1",
        login_type_id="lt1",
        name="ada@example.com",
        password="secret",
    )
    again = LoginRecord.model_validate(rec.model_dump())
    assert again.name == rec.name
