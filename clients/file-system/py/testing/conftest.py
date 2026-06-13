"""Shared pytest fixtures for file-system-client."""

from __future__ import annotations

import pytest


@pytest.fixture
def sample_text() -> str:
    return "hello world"


@pytest.fixture
def sample_bytes() -> bytes:
    return b"\x00\x01binary payload"
