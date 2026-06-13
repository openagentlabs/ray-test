"""Aggregate statistics from extracted issues."""

from __future__ import annotations

from collections import Counter
from typing import Sequence

from fortify_workbook_tool.domain import FortifyIssue, PrioritySummary


class PriorityAggregator:
    """Builds :class:`PrioritySummary` from parsed Fortify issues."""

    def summarize(self, issues: Sequence[FortifyIssue]) -> PrioritySummary:
        c = Counter((r.fortify_priority or "").strip() for r in issues)
        total = len(issues)
        critical = c.get("Critical", 0)
        high = c.get("High", 0)
        medium = c.get("Medium", 0)
        low = c.get("Low", 0)
        known = critical + high + medium + low
        other = total - known
        return PrioritySummary(
            total=total,
            critical=critical,
            high=high,
            medium=medium,
            low=low,
            other=other,
        )
