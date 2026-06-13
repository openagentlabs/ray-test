"""Human-readable reports for Fortify workbook extraction runs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from fortify_workbook_tool.domain import FortifyIssue, WorkbookExtraction


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def issue_csv_field_names() -> tuple[str, ...]:
    """Column names written to CSV / JSON issue rows (matches :class:`FortifyIssue` field order)."""
    return tuple(FortifyIssue.model_fields.keys())


class IssueCsvColumnCatalog(BaseModel):
    """Documents which fields appear as columns in the extracted issues CSV."""

    model_config = ConfigDict(extra="forbid")

    field_names: tuple[str, ...] = Field(
        default_factory=issue_csv_field_names,
        description="Ordered list of CSV column headers for each Fortify issue row.",
    )

    def as_markdown_section(self, title: str = "CSV column headers") -> str:
        lines = [f"### {title}", "", "These fields appear in the output issues table (CSV / JSON / YAML issue objects):", ""]
        for i, name in enumerate(self.field_names, start=1):
            lines.append(f"{i}. `{name}`")
        lines.append("")
        return "\n".join(lines)

    def as_plain_lines(self) -> list[str]:
        """One field name per line (for ``--print-csv-fields``)."""
        return list(self.field_names)


class ExtractionSummaryReport(BaseModel):
    """Short summary of one extraction run (embedded inside :class:`FinalReport` or used alone)."""

    model_config = ConfigDict(extra="forbid")

    total_issues: int = 0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0
    other_priority_count: int = 0
    rows_written: int = 0
    loader_warnings_count: int = 0
    parser_warnings_count: int = 0


class FinalReport(BaseModel):
    """Terminal markdown report for a completed extract. Set properties, then :meth:`write` or :meth:`to_markdown`."""

    model_config = ConfigDict(extra="forbid")

    title: str = "Fortify Developer Workbook — extraction report"
    generated_at_utc: str = Field(default_factory=_utc_timestamp)

    source_pdf: str = ""
    output_path: str = ""
    output_format: str = ""
    formatter_schema_version: str = ""

    summary: ExtractionSummaryReport = Field(default_factory=ExtractionSummaryReport)

    #: Columns present in the serialized issue rows — same order as the CSV header.
    csv_field_names: tuple[str, ...] = Field(
        default_factory=issue_csv_field_names,
        description="Field names written for each issue (shown in this report for operator visibility).",
    )

    status_line: str = "SUCCESS"
    notes: str = ""

    def to_markdown(self) -> str:
        """Render the full report as Markdown."""
        s = self.summary
        lines = [
            f"# {self.title}",
            "",
            f"- **Generated (UTC):** {self.generated_at_utc}",
            f"- **Status:** {self.status_line}",
            "",
            "## Run",
            "",
            f"| Property | Value |",
            f"|----------|-------|",
            f"| Source PDF | `{self.source_pdf}` |",
            f"| Output | `{self.output_path}` |",
            f"| Format | `{self.output_format}` |",
            f"| Formatter schema | `{self.formatter_schema_version}` |",
            "",
            "## Issue counts (Fortify priority)",
            "",
            f"| Priority | Count |",
            f"|----------|-------|",
            f"| Critical | {s.critical_count} |",
            f"| High | {s.high_count} |",
            f"| Medium | {s.medium_count} |",
            f"| Low | {s.low_count} |",
        ]
        if s.other_priority_count:
            lines.extend([f"| Other | {s.other_priority_count} |", ""])
        else:
            lines.append("")
        lines.extend(
            [
                f"**Total issues:** {s.total_issues}  ",
                f"**Rows written:** {s.rows_written}  ",
                "",
                "## Warnings",
                "",
                f"- Loader: {s.loader_warnings_count}",
                f"- Parser: {s.parser_warnings_count}",
                "",
            ]
        )
        cat = IssueCsvColumnCatalog(field_names=self.csv_field_names)
        lines.append(cat.as_markdown_section())
        if self.notes.strip():
            lines.extend(["## Notes", "", self.notes.strip(), ""])
        return "\n".join(lines)

    def write(self, path: Path) -> None:
        """Write UTF-8 Markdown to ``path`` (parent directories created)."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_markdown(), encoding="utf-8")


def build_final_report_from_extraction(
    extraction: WorkbookExtraction,
    output_path: str,
    output_format: str,
    formatter_schema_version: str,
) -> FinalReport:
    """Populate :class:`FinalReport` from a completed :class:`WorkbookExtraction`."""
    from fortify_workbook_tool.aggregation import PriorityAggregator

    summary = PriorityAggregator().summarize(extraction.issues)
    return FinalReport(
        source_pdf=str(extraction.source_pdf),
        output_path=output_path,
        output_format=output_format,
        formatter_schema_version=formatter_schema_version,
        csv_field_names=issue_csv_field_names(),
        summary=ExtractionSummaryReport(
            total_issues=summary.total,
            critical_count=summary.critical,
            high_count=summary.high,
            medium_count=summary.medium,
            low_count=summary.low,
            other_priority_count=summary.other,
            rows_written=len(extraction.issues),
            loader_warnings_count=len(extraction.loader_warnings),
            parser_warnings_count=len(extraction.warnings),
        ),
    )
