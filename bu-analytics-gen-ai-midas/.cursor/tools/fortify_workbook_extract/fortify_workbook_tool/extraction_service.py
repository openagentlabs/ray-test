"""Orchestrates validate → PDF load → parse → :class:`WorkbookExtraction`."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from fortify_workbook_tool.domain import FortifyIssue, WorkbookExtraction
from fortify_workbook_tool.pdf_loader import WorkbookPdfLoader
from fortify_workbook_tool.validators import ScanReportInputValidator, ScanReportValidationError
from fortify_workbook_tool.workbook_parser import FortifyWorkbookParser

if TYPE_CHECKING:
    from fortify_workbook_tool.feedback import ColoredFeedback


class WorkbookExtractionService:
    """Facade: validate input, then loader + parser → domain model."""

    def __init__(self, feedback: Optional["ColoredFeedback"] = None) -> None:
        self._feedback = feedback
        self._loader = WorkbookPdfLoader()
        self._parser = FortifyWorkbookParser()
        self._validator = ScanReportInputValidator()

    def extract(self, pdf_path: Path) -> WorkbookExtraction:
        path = pdf_path.expanduser().resolve()
        fb = self._feedback

        vr = self._validator.validate(path, fb)
        if not vr.ok:
            raise ScanReportValidationError(list(vr.errors))

        text, loader_warnings = self._loader.load(path, fb)

        if fb:
            fb.step("Parsing Fortify Results Outline…")

        issues, parse_warnings = self._parser.parse(text)

        if fb:
            fb.ok(f"Parsed {len(issues)} issue row(s).")

        issues = self._assign_obv_ids(issues)

        return WorkbookExtraction(
            source_pdf=path,
            issues=issues,
            warnings=parse_warnings,
            loader_warnings=tuple(loader_warnings),
        )

    @staticmethod
    def _assign_obv_ids(issues: list[FortifyIssue]) -> tuple[FortifyIssue, ...]:
        """First CSV column: ``OBV0001``, ``OBV0002``, … in emission order."""
        numbered: list[FortifyIssue] = []
        for i, issue in enumerate(issues, start=1):
            numbered.append(issue.model_copy(update={"obv_id": f"OBV{i:04d}"}))
        return tuple(numbered)
