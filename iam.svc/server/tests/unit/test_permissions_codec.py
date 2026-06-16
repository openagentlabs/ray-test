"""Unit tests for permission string codec."""

from __future__ import annotations

import pytest

from iam_service.auth.permissions_codec import (
    PermissionGrantSet,
    ServicePermissionGrant,
    decode_permissions,
    encode_permissions,
    validate_permission_string,
)
from iam_service.core.results import Failure, Success


def test_encode_decode_round_trip() -> None:
    grants = PermissionGrantSet(
        grants=(
            ServicePermissionGrant(
                service_id="iam-svc",
                function_ids=("readProf", "writeUsr"),
            ),
            ServicePermissionGrant(
                service_id="stor-svc",
                function_ids=("getFile", "putFile"),
            ),
        ),
    )
    encoded = encode_permissions(grants)
    assert isinstance(encoded, Success)
    perm = encoded.unwrap()
    assert perm == "iam-svc:readProf,writeUsr>stor-svc:getFile,putFile"
    decoded = decode_permissions(perm)
    assert isinstance(decoded, Success)
    assert decoded.unwrap() == grants


@pytest.mark.parametrize(
    "bad_value",
    [
        "",
        "abc:fn12345",
        "iam-svc:",
        "iam-svc:fn",
        "iam-svc:fn1|stor-svc:fn2",
        "iam-svc:fn1,fn2;stor-svc:fn3",
    ],
)
def test_decode_rejects_invalid(bad_value: str) -> None:
    result = decode_permissions(bad_value)
    assert isinstance(result, Failure)


def test_validate_permission_string_ok() -> None:
    result = validate_permission_string("iam-svc:readProf,writeUsr")
    assert isinstance(result, Success)
