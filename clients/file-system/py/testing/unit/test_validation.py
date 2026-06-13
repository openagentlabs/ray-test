"""Unit tests for ingress validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from returns.result import Success

from file_system.domain.enums import TextEncoding
from file_system.validation.paths import (
    validate_bytes_write,
    validate_path,
    validate_text_write,
)


def test_validate_path_accepts_str_and_path() -> None:
    for raw in ("config/app.json", Path("config/app.json")):
        outcome = validate_path(raw)
        assert isinstance(outcome, Success)
        assert outcome.unwrap().path == Path(raw)


def test_validate_text_write_defaults_to_utf8() -> None:
    outcome = validate_text_write("out.txt", "payload", TextEncoding.UTF8)
    assert isinstance(outcome, Success)
    request = outcome.unwrap()
    assert request.text == "payload"
    assert request.encoding == TextEncoding.UTF8


def test_validate_bytes_write_accepts_empty_payload() -> None:
    outcome = validate_bytes_write("empty.bin", b"")
    assert isinstance(outcome, Success)
    assert outcome.unwrap().data == b""


def test_validate_path_propagates_unexpected_type_error() -> None:
    with pytest.raises(TypeError):
        validate_path(None)  # type: ignore[arg-type]
