"""DynamoDB pagination token helpers."""

from __future__ import annotations

from iam_service.database.pagination import decode_exclusive_start_key, encode_exclusive_start_key


def test_encode_decode_round_trip() -> None:
    key = {"id": "abc", "sort": "1"}
    token = encode_exclusive_start_key(key)
    assert token != ""
    decoded = decode_exclusive_start_key(token)
    assert decoded == key


def test_empty_token_decodes_to_none() -> None:
    assert decode_exclusive_start_key("") is None
    assert decode_exclusive_start_key("   ") is None


def test_invalid_token_decodes_to_none() -> None:
    assert decode_exclusive_start_key("not-valid-base64!!!") is None
