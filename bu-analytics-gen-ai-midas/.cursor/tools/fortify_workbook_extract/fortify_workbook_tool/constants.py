"""Shared literals for Fortify workbook parsing."""

from typing import Final, Literal, Tuple

PRIORITIES: Final[Tuple[str, ...]] = ("Critical", "High", "Medium", "Low")
PRIORITY_HEADER_MAX_LEN: Final[int] = 320

MARK_RESULTS_OUTLINE: Final[str] = "Results Outline"
MARK_ISSUE_SUMMARY: Final[str] = "Issue Summary"
MARK_EXPLANATION: Final[str] = "Explanation"
MARK_RECOMMENDATION: Final[str] = "Recommendation"
MARK_ISSUE_BREAKDOWN: Final[str] = "Issue Breakdown by Fortify Categories"

NarrativeSection = Literal["abstract", "explanation", "recommendation"]
DetailSection = Literal["source", "sink"]

DEFAULT_STRIP_PREFIXES: Final[Tuple[str, ...]] = (
    "Downloads/bu-analytics-gen-ai-midas-deployment-dev-jenkins/",
    "bu-analytics-gen-ai-midas-deployment-dev-jenkins/",
)

# Default CSV ``issue_state`` when no remediation workflow has started (PDF extract placeholders).
DEFAULT_ISSUE_STATE: Final[str] = "OPEN"
