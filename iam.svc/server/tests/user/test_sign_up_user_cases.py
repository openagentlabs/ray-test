"""User-case tests for sign-up validation — all input options, not only happy path."""

from __future__ import annotations

import pytest

from iam.v1 import iam_pb2
from iam_service.core.results import Failure, Success
from iam_service.validation.sign_up_user import validate_sign_up_user_request


def _req(
    *,
    email: str = "user@example.com",
    first_name: str = "Ada",
    last_name: str = "Lovelace",
    password: str = "password1",
    password_confirm: str = "password1",
    invite_code: str = "AB12-CD-34EF",
) -> iam_pb2.SignUpUserRequest:
    return iam_pb2.SignUpUserRequest(
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
        password_confirm=password_confirm,
        invite_code=invite_code,
    )


@pytest.mark.parametrize(
    ("field", "value", "expect_ok"),
    [
        ("email", "", False),
        ("email", "not-an-email", False),
        ("password", "", False),
        ("password_confirm", "mismatch", False),
        ("invite_code", "", False),
        ("invite_code", "bad-format", False),
        ("first_name", "", False),
    ],
)
def test_sign_up_user_rejects_invalid_fields(
    field: str,
    value: str,
    *,
    expect_ok: bool,
) -> None:
    """User case: each required field rejects invalid values."""
    kwargs = {
        "email": "user@example.com",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "password": "password1",
        "password_confirm": "password1",
        "invite_code": "AB12-CD-34EF",
    }
    kwargs[field] = value
    outcome = validate_sign_up_user_request(_req(**kwargs))
    if expect_ok:
        assert isinstance(outcome, Success)
    else:
        assert isinstance(outcome, Failure)


def test_sign_up_user_accepts_valid_payload() -> None:
    """User case: complete valid sign-up passes validation."""
    outcome = validate_sign_up_user_request(_req())
    assert isinstance(outcome, Success)
