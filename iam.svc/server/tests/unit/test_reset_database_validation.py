"""Unit tests: ``validate_reset_database_request``."""

from __future__ import annotations

from iam.v1 import iam_pb2
from iam_service.core.results import Failure, Success
from iam_service.validation.reset_database import (
    names_from_username,
    validate_reset_database_request,
)


def test_names_from_username_splits_email_local_part() -> None:
    assert names_from_username("keith.tobin@gmail.com") == ("Keith", "Tobin")
    assert names_from_username("admin@example.com") == ("Admin", "User")


def test_validate_reset_database_request_accepts_credentials() -> None:
    out = validate_reset_database_request(
        iam_pb2.ResetDatabaseRequest(
            username="keith.tobin@gmail.com",
            password="Tippertobin12@",
        ),
    )
    assert isinstance(out, Success)
    credentials, first_name, last_name = out.unwrap()
    assert credentials.username == "keith.tobin@gmail.com"
    assert credentials.password == "Tippertobin12@"
    assert first_name == "Keith"
    assert last_name == "Tobin"


def test_validate_reset_database_request_rejects_empty_password() -> None:
    out = validate_reset_database_request(
        iam_pb2.ResetDatabaseRequest(username="a@b.co", password=""),
    )
    assert isinstance(out, Failure)
