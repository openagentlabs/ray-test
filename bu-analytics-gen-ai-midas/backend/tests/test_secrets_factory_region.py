"""Tests for Secrets Manager client region coercion (bad SM / env values)."""

from app.core.secrets.factory import _MIDAS_DEFAULT_AWS_REGION, _coerce_secrets_manager_region


def test_coerce_accepts_us_east_1() -> None:
    assert _coerce_secrets_manager_region("us-east-1") == "us-east-1"


def test_coerce_decodes_base64_encoded_region() -> None:
    # base64 of "us-east-1" — common accidental paste into SM JSON
    assert _coerce_secrets_manager_region("dXMtZWFzdC0x") == "us-east-1"


def test_coerce_empty_returns_none() -> None:
    assert _coerce_secrets_manager_region("") is None
    assert _coerce_secrets_manager_region(None) is None


def test_coerce_garbage_falls_back_to_midas_default() -> None:
    assert _coerce_secrets_manager_region("not-a-region-!!!") == _MIDAS_DEFAULT_AWS_REGION
