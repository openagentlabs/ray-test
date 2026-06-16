"""Pytest plugin: traffic-light result table for agent-readable test feedback."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from _pytest.reports import TestReport


@dataclass(slots=True)
class TestRow:
    """One row in the agent feedback table."""

    index: int
    name: str
    description: str
    comment: str
    status: str  # green | amber | red


@dataclass
class ResultTable:
    """Collects per-test outcomes for end-of-run summary."""

    rows: list[TestRow] = field(default_factory=list)

    def add(self, *, index: int, name: str, description: str, comment: str, status: str) -> None:
        self.rows.append(
            TestRow(
                index=index,
                name=name,
                description=description,
                comment=comment,
                status=status,
            ),
        )

    def render_markdown(self) -> str:
        """Render the mandatory agent feedback table."""
        if not self.rows:
            return "| # | Test | Description | Comment | Status |\n|---:|---|---|---|---|"
        lines = ["| # | Test | Description | Comment | Status |", "|---:|---|---|---|---|"]
        for row in self.rows:
            icon = {"green": "🟢", "amber": "🟡", "red": "🔴"}.get(row.status, row.status)
            lines.append(
                f"| {row.index} | {row.name} | {row.description} | {row.comment} | {icon} |",
            )
        return "\n".join(lines)


_table = ResultTable()
_counter = 0


def _doc_first_line(nodeid: str, doc: str | None) -> str:
    if doc and doc.strip():
        return doc.strip().splitlines()[0]
    return nodeid.split("::")[-1]


def pytest_runtest_logreport(report: TestReport) -> None:
    """Record each test phase outcome (call only) into the shared table."""
    global _counter
    if report.when != "call":
        return
    _counter += 1
    doc = getattr(report, "description", None) or report.nodeid
    name = report.nodeid.split("::")[-1]
    description = _doc_first_line(report.nodeid, doc if isinstance(doc, str) else None)
    if report.passed:
        status, comment = "green", "passed"
    elif report.failed:
        status, comment = "red", (report.longreprtext or "failed")[:120]
    elif report.skipped:
        status, comment = "amber", "skipped"
    else:
        status, comment = "amber", report.outcome
    _table.add(
        index=_counter,
        name=name,
        description=description,
        comment=comment,
        status=status,
    )


def pytest_sessionfinish() -> None:
    """Print table summary when pytest exits (visible in CI logs)."""
    rendered = _table.render_markdown()
    if _table.rows:
        print("\n--- Test result table (agent feedback) ---\n")
        print(rendered)


def get_result_table() -> ResultTable:
    """Access collected rows from tests (e.g. assert table non-empty)."""
    return _table


def reset_result_table_for_tests() -> None:
    """Clear table between isolated test runs."""
    global _counter
    _table.rows.clear()
    _counter = 0
