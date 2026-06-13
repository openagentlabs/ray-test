"""Tests for user-facing error formatting."""

from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError

from tf_tool.core.error_format import format_validation_detail


class _Sample(BaseModel):
    name: str = Field(..., min_length=1)


def test_format_validation_detail_strips_value_error_prefix() -> None:
    try:
        _Sample.model_validate({"name": ""})
    except ValidationError as exc:
        detail = format_validation_detail(exc)
    else:
        msg = "Expected validation to fail"
        raise AssertionError(msg)
    assert "Value error" not in detail
    assert "name:" in detail
