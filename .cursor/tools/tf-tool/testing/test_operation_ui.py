"""Tests for operation UI session."""

from __future__ import annotations

import pytest

from tf_tool.core.operation_ui import MessageCounts, OperationSession, _classify_line, ui_enabled


def test_message_counts_total() -> None:
    counts = MessageCounts(ordinary=1, result=2, warning=1, error=0, info=1, debug=0)
    assert counts.total == 5


def test_classify_line_error_and_warning() -> None:
    assert _classify_line("build failed", default="result") == "error"
    assert _classify_line("deprecated API", default="result") == "warning"


def test_run_operation_invokes_fn() -> None:
    session = OperationSession.start()
    seen: list[int] = []

    def fn() -> int:
        seen.append(1)
        return 42

    assert session.run_operation("Test op", "tf-tool test", fn) == 42
    assert seen == [1]


def test_ui_enabled_respects_plain_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TF_TOOL_PLAIN", "1")
    assert ui_enabled() is False
