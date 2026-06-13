"""Output formatters: internal :class:`WorkbookExtraction` → CSV / JSON / YAML text."""

from __future__ import annotations

import csv
import io
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Literal, Optional, Sequence

from fortify_workbook_tool.aggregation import PriorityAggregator
from fortify_workbook_tool.domain import FormatterOptions, FortifyIssue, WorkbookExtraction


class AbstractIssueSinkFormatter(ABC):
    """Strategy interface — converts extraction into serialized text."""

    @abstractmethod
    def format_text(self, extraction: WorkbookExtraction, options: FormatterOptions) -> str:
        """Return UTF-8 encoded textual representation."""

    def write(self, extraction: WorkbookExtraction, output_path: Path, options: FormatterOptions) -> None:
        """Write ``format_text`` result to ``output_path`` (parent dirs created)."""
        text = self.format_text(extraction, options)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")


class CsvIssueSinkFormatter(AbstractIssueSinkFormatter):
    """RFC4180-style CSV with Fortify field columns."""

    def format_text(self, extraction: WorkbookExtraction, options: FormatterOptions) -> str:
        if options.issue_field_subset is not None:
            raise ValueError("CSV output does not support issue_field_subset; use JSON or YAML.")
        buf = io.StringIO()
        fieldnames = list(FortifyIssue.model_fields.keys())
        writer = csv.DictWriter(
            buf,
            fieldnames=fieldnames,
            extrasaction="ignore",
            quoting=csv.QUOTE_MINIMAL,
        )
        writer.writeheader()
        for issue in extraction.issues:
            writer.writerow(issue.as_flat_strings(options.normalize_paths, options.strip_prefixes))
        return buf.getvalue()


class JsonIssueSinkFormatter(AbstractIssueSinkFormatter):
    """Structured JSON report including optional priority summary and field projection."""

    def __init__(self, aggregator: PriorityAggregator | None = None) -> None:
        self._aggregator = aggregator or PriorityAggregator()

    def format_text(self, extraction: WorkbookExtraction, options: FormatterOptions) -> str:
        subset_list: Optional[List[str]] = (
            list(options.issue_field_subset) if options.issue_field_subset is not None else None
        )
        issues_out: List[object] = []
        for issue in extraction.issues:
            issues_out.append(issue.projected_dict(subset_list))

        summary = None
        if options.include_priority_summary:
            summary = self._aggregator.summarize(extraction.issues).model_dump()

        payload = {
            "schema_version": options.schema_version,
            "format": "fortify_workbook_extraction",
            "source_pdf": str(extraction.source_pdf),
            "warnings": list(extraction.all_warnings()),
            "priority_summary": summary,
            "issues": issues_out,
        }
        return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


class YamlIssueSinkFormatter(AbstractIssueSinkFormatter):
    """YAML encoding of the same logical payload as JSON."""

    def __init__(self, aggregator: PriorityAggregator | None = None) -> None:
        self._aggregator = aggregator or PriorityAggregator()

    def format_text(self, extraction: WorkbookExtraction, options: FormatterOptions) -> str:
        try:
            import yaml
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "Install PyYAML for YAML output: pip install -r requirements-workbook-tools.txt"
            ) from exc

        subset_list: Optional[List[str]] = (
            list(options.issue_field_subset) if options.issue_field_subset is not None else None
        )
        issues_out = [issue.projected_dict(subset_list) for issue in extraction.issues]

        summary = None
        if options.include_priority_summary:
            summary = self._aggregator.summarize(extraction.issues).model_dump()

        payload = {
            "schema_version": options.schema_version,
            "format": "fortify_workbook_extraction",
            "source_pdf": str(extraction.source_pdf),
            "warnings": list(extraction.all_warnings()),
            "priority_summary": summary,
            "issues": issues_out,
        }
        return yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )


def get_formatter(kind: Literal["csv", "json", "yaml"]) -> AbstractIssueSinkFormatter:
    """Factory for formatter implementations."""
    if kind == "csv":
        return CsvIssueSinkFormatter()
    if kind == "json":
        return JsonIssueSinkFormatter()
    if kind == "yaml":
        return YamlIssueSinkFormatter()
    raise ValueError(f"Unknown output format: {kind}")
