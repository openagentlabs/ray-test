"""Unit tests: Pydantic validation for ``sign_up_user``."""

from __future__ import annotations

from iam.v1 import iam_pb2
from iam_service.core.errors import ErrorCodes
from iam_service.core.results import Failure
from iam_service.validation.sign_up_user import validate_sign_up_user_request


def test_validate_sign_up_user_rejects_invalid_invite_format() -> None:
    req = iam_pb2.SignUpUserRequest(
        email="user@example.com",
        first_name="Ada",
        last_name="Lovelace",
        password="password1",
        password_confirm="password1",
        invite_code="not-a-code",
    )
    out = validate_sign_up_user_request(req)
    assert isinstance(out, Failure)
    err = out.failure()
    assert err.code == ErrorCodes.VALIDATION
    assert "invite_code" in err.message.lower() or "invite" in err.message.lower()
    assert err.detail is not None


def test_validate_sign_up_user_normalizes_invite_code() -> None:
    req = iam_pb2.SignUpUserRequest(
        email="user@example.com",
        first_name="Ada",
        last_name="Lovelace",
        password="password1",
        password_confirm="password1",
        invite_code="ab12cd34ef",
    )
    out = validate_sign_up_user_request(req)
    assert not isinstance(out, Failure)
    assert out.unwrap().invite_code == "AB12-CD-34EF"
