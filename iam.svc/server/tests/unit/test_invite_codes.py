"""Unit tests for invite code helpers."""

from __future__ import annotations

from iam_service.core.invite_codes import (
    generate_random_invite_code,
    is_valid_invite_code,
    normalize_invite_code,
)


def test_normalize_inserts_hyphens_for_ten_alnum() -> None:
    assert normalize_invite_code("  ab12cd34ef  ") == "AB12-CD-34EF"


def test_normalize_reformats_mixed_separators() -> None:
    assert normalize_invite_code("aa11-bb-cc22") == "AA11-BB-CC22"


def test_is_valid_invite_code() -> None:
    assert is_valid_invite_code("A1B2-C3-D4E5") is True
    assert is_valid_invite_code("a1b2-c3-d4e5") is False
    assert is_valid_invite_code("AB12-CDE-FG34") is False


def test_generate_random_invite_code_shape() -> None:
    code = generate_random_invite_code()
    assert is_valid_invite_code(code) is True
