"""Parse Fortify Results Outline plain text into :class:`FortifyIssue` rows."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import DefaultDict, List, Optional, Sequence, Tuple

from fortify_workbook_tool.constants import (
    MARK_EXPLANATION,
    MARK_ISSUE_BREAKDOWN,
    MARK_ISSUE_SUMMARY,
    MARK_RECOMMENDATION,
    MARK_RESULTS_OUTLINE,
    PRIORITIES,
    PRIORITY_HEADER_MAX_LEN,
    DetailSection,
    NarrativeSection,
)

from fortify_workbook_tool.domain import FortifyIssue
from fortify_workbook_tool.normalization import TextNormalizer

class FortifyWorkbookParser:
    """
    Stateful line parser for Fortify ``Results Outline`` text.

    Consumes text produced by :class:`WorkbookPdfLoader` and emits canonical
    :class:`FortifyIssue` instances (one per ``Kingdom:`` block).
    """

    def __init__(self) -> None:
        self._warnings: List[str] = []

    def parse(self, text: str) -> Tuple[Tuple[FortifyIssue, ...], Tuple[str, ...]]:
        """Returns ``(issues, parser_warnings)``."""
        self._warnings = []
        norm_lines = TextNormalizer.join_split_issue_count_lines(
            [TextNormalizer.norm_line(x) for x in text.splitlines()]
        )
        issues = self._parse_lines(norm_lines)
        if not issues:
            self._warnings.append("No issues parsed; check PDF text extraction or workbook format.")
        self._validate_category_counts(issues)
        self._validate_priorities(issues)
        return tuple(issues), tuple(self._warnings)

    def _parse_lines(self, lines: List[str]) -> List[FortifyIssue]:
        in_results_outline = False
        category_title = ""
        category_issue_count = ""
        abstract_buf: List[str] = []
        explanation_buf: List[str] = []
        recommendation_buf: List[str] = []
        narrative_section: Optional[NarrativeSection] = None

        pending_title_lines: List[str] = []
        issues: List[FortifyIssue] = []

        instances_active = False
        last_package = ""
        last_priority = ""
        pending_ref = ""

        i = 0
        while i < len(lines):
            line = lines[i]

            if line == MARK_RESULTS_OUTLINE:
                in_results_outline = True
                i += 1
                continue

            if not in_results_outline:
                i += 1
                continue

            mhdr = TextNormalizer.issues_header_match(line)
            if mhdr and MARK_ISSUE_BREAKDOWN not in line:
                title_parts = pending_title_lines + [line]
                pending_title_lines.clear()
                merged = TextNormalizer.clean_spaces(" ".join(title_parts))
                merged = TextNormalizer.strip_issues_header(merged)
                category_title = merged
                category_issue_count = mhdr.group(1)
                narrative_section = "abstract"
                instances_active = False
                last_package = ""
                last_priority = ""
                abstract_buf.clear()
                explanation_buf.clear()
                recommendation_buf.clear()
                i += 1
                continue

            if (
                line
                and narrative_section is None
                and not instances_active
                and i + 1 < len(lines)
                and TextNormalizer.issues_header_match(lines[i + 1])
            ):
                pending_title_lines.append(line)
                i += 1
                continue

            if narrative_section == "abstract":
                if line == MARK_EXPLANATION:
                    narrative_section = "explanation"
                    i += 1
                    continue
                if line:
                    abstract_buf.append(line)
                i += 1
                continue

            if narrative_section == "explanation":
                if line == MARK_RECOMMENDATION:
                    narrative_section = "recommendation"
                    i += 1
                    continue
                if line == MARK_ISSUE_SUMMARY:
                    narrative_section = None
                    instances_active = True
                    i += 1
                    continue
                if line:
                    explanation_buf.append(line)
                i += 1
                continue

            if narrative_section == "recommendation":
                if line == MARK_ISSUE_SUMMARY:
                    narrative_section = None
                    instances_active = True
                    i += 1
                    continue
                if line:
                    recommendation_buf.append(line)
                i += 1
                continue

            cat_part, prio = TextNormalizer.split_priority(line)
            if instances_active and prio and cat_part:
                if len(line) <= PRIORITY_HEADER_MAX_LEN or ":" in cat_part:
                    last_priority = prio
                i += 1
                continue

            if line.startswith("Package:"):
                if instances_active:
                    last_package = line.split(":", 1)[1].strip()
                i += 1
                continue

            if instances_active and ", line " in line and TextNormalizer.ref_line_matches(line):
                pending_ref = line
                i += 1
                continue

            if line.startswith("Kingdom:"):
                kingdom_val = line.split(":", 1)[1].strip()
                if not kingdom_val:
                    self._warnings.append(f"Line {i + 1}: empty Kingdom value; row still emitted.")

                row = FortifyIssue(
                    category=category_title,
                    category_issue_count=category_issue_count,
                    package=last_package,
                    reference_line=pending_ref,
                    kingdom=kingdom_val,
                    fortify_priority=last_priority,
                    abstract=TextNormalizer.clean_spaces(" ".join(abstract_buf)),
                    explanation=TextNormalizer.clean_spaces(" ".join(explanation_buf)),
                    recommendation=TextNormalizer.clean_spaces(" ".join(recommendation_buf)),
                )

                i = self._consume_issue_detail_block(lines, i + 1, row)
                issues.append(row)
                pending_ref = ""
                continue

            i += 1

        return issues

    def _consume_issue_detail_block(self, lines: List[str], start: int, row: FortifyIssue) -> int:
        i = start
        section: Optional[DetailSection] = None
        max_steps = len(lines) - start + 16
        steps = 0

        while i < len(lines) and steps < max_steps:
            steps += 1
            ln = lines[i]
            ls = TextNormalizer.norm_line(ln)

            if TextNormalizer.issues_header_match(ls):
                break
            if ls.startswith("Kingdom:"):
                break

            if ls.startswith("Scan Engine:"):
                row.scan_engine = ls.split(":", 1)[1].strip()
                i += 1
                continue

            if ls == "Source Details":
                section = "source"
                i += 1
                continue
            if ls == "Sink Details":
                section = "sink"
                i += 1
                continue

            if ls.startswith("Source:") and section == "source":
                row.source_kind = ls.split(":", 1)[1].strip()
                i += 1
                continue
            if ls.startswith("From:") and section == "source":
                row.source_detail = ls.split(":", 1)[1].strip()
                i += 1
                continue

            if ls.startswith("Sink:") and section == "sink":
                row.sink_kind = ls.split(":", 1)[1].strip()
                i += 1
                continue
            if ls.startswith("Enclosing Method:"):
                if section == "sink":
                    row.sink_detail = (row.sink_detail + " | " if row.sink_detail else "") + ls
                elif section == "source":
                    row.source_detail = (row.source_detail + " | " if row.source_detail else "") + ls
                i += 1
                continue

            m_file = TextNormalizer.file_line_match(ls)
            if m_file:
                path, lineno = TextNormalizer.parse_file_location(m_file.group(1))
                if section == "source":
                    row.source_file = path
                    row.source_line = lineno
                elif section == "sink":
                    row.sink_file = path
                    row.sink_line = lineno
                else:
                    row.sink_file = path
                    row.sink_line = lineno
                i += 1
                continue

            if ls.startswith("Taint Flags:"):
                row.taint_flags = ls.split(":", 1)[1].strip()
                i += 1
                continue

            if ", line " in ls and TextNormalizer.ref_line_matches(ls):
                break
            if ls.startswith("Package:"):
                break
            _, prb = TextNormalizer.split_priority(ls)
            if prb and ls == TextNormalizer.norm_line(ln) and len(ls) <= PRIORITY_HEADER_MAX_LEN:
                break

            i += 1

        if steps >= max_steps - 1:
            return min(start + 1, len(lines))

        return i

    def _validate_category_counts(self, issues: Sequence[FortifyIssue]) -> None:
        by_cat: DefaultDict[str, List[FortifyIssue]] = defaultdict(list)
        for r in issues:
            key = r.category or "(blank category)"
            by_cat[key].append(r)

        for cat, grp in by_cat.items():
            counts = {x.category_issue_count for x in grp if x.category_issue_count}
            if len(counts) > 1:
                self._warnings.append(
                    f"Category {cat!r}: inconsistent category_issue_count values: {sorted(counts)}"
                )
            if not counts:
                continue
            expected_s = next(iter(counts))
            try:
                expected_n = int(expected_s)
            except ValueError:
                continue
            if len(grp) != expected_n:
                self._warnings.append(
                    f"Category {cat!r}: parsed {len(grp)} rows but header declared ({expected_n} issues)."
                )

    def _validate_priorities(self, issues: Sequence[FortifyIssue]) -> None:
        blank = sum(1 for r in issues if not (r.fortify_priority or "").strip())
        if blank:
            self._warnings.append(
                f"{blank} issue row(s) have empty fortify_priority (instance header not matched)."
            )
        unknown: Counter[str] = Counter()
        for r in issues:
            p = (r.fortify_priority or "").strip()
            if p and p not in PRIORITIES:
                unknown[p] += 1
        if unknown:
            self._warnings.append(f"Unknown priority labels (check parser): {dict(unknown)}")
