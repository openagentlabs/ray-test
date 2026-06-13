"""Validate ISG/Fortify Developer Workbook PDF inputs before extraction."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Sequence, Tuple

if TYPE_CHECKING:
    from fortify_workbook_tool.feedback import ColoredFeedback


class ScanReportValidationError(ValueError):
    """Raised when the input file fails validation."""

    def __init__(self, errors: Sequence[str]) -> None:
        self.errors: Tuple[str, ...] = tuple(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    errors: Tuple[str, ...]


class ScanReportInputValidator:
    """
    Validates expected Developer Workbook PDF shape.

    Checks path, ``.pdf`` suffix, PDF magic bytes, readable pages, encryption.
    """

    _PDF_MAGIC = b"%PDF"

    def validate(self, pdf_path: Path, feedback: Optional["ColoredFeedback"] = None) -> ValidationResult:
        errors: list[str] = []
        path = pdf_path.expanduser().resolve()

        if not path.exists():
            errors.append(f"Path does not exist: {path}")
        elif not path.is_file():
            errors.append(f"Not a regular file: {path}")
        elif path.suffix.lower() != ".pdf":
            errors.append(f"Expected a .pdf file, got suffix {path.suffix!r}")

        if errors:
            self._emit(feedback, errors)
            return ValidationResult(False, tuple(errors))

        try:
            header = path.open("rb").read(8)
        except OSError as exc:
            errors.append(f"Cannot read file: {exc}")
            self._emit(feedback, errors)
            return ValidationResult(False, tuple(errors))

        if not header.startswith(self._PDF_MAGIC):
            errors.append("Not a PDF (file does not start with %PDF magic bytes).")
            self._emit(feedback, errors)
            return ValidationResult(False, tuple(errors))

        try:
            from pypdf import PdfReader
            from pypdf.errors import PdfReadError
        except ImportError:
            errors.append("pypdf is not available (bootstrap/install failed).")
            self._emit(feedback, errors)
            return ValidationResult(False, tuple(errors))

        try:
            reader = PdfReader(str(path))
        except PdfReadError as exc:
            errors.append(f"PDF is unreadable or corrupt: {exc}")
            self._emit(feedback, errors)
            return ValidationResult(False, tuple(errors))

        if getattr(reader, "is_encrypted", False):
            errors.append("PDF is encrypted; decrypt before extracting.")

        n_pages = len(reader.pages)
        if n_pages == 0:
            errors.append("PDF contains zero pages.")

        if errors:
            self._emit(feedback, errors)
            return ValidationResult(False, tuple(errors))

        if feedback:
            feedback.ok(f"Input valid: PDF with {n_pages} page(s).")
        return ValidationResult(True, ())

    @staticmethod
    def _emit(feedback: Optional["ColoredFeedback"], errors: Sequence[str]) -> None:
        if feedback is None:
            return
        for err in errors:
            feedback.error(err)


class FortifyStructureValidator:
    """
    Validates that a PDF is a genuine Fortify Developer Workbook by checking
    for known structural markers in the extracted text.

    Designed to be called after ``ScanReportInputValidator`` confirms the file
    is a readable, unencrypted PDF with at least one page.
    """

    MARK_RESULTS_OUTLINE: str = "Results Outline"
    MARK_KINGDOM: str = "Kingdom:"

    def validate_text(self, pdf_text: str) -> ValidationResult:
        """
        Validate ``pdf_text`` (all pages concatenated) against Fortify structure markers.

        Returns a :class:`ValidationResult`; does not raise.
        """
        errors: list[str] = []

        if self.MARK_RESULTS_OUTLINE not in pdf_text:
            errors.append(
                f'This PDF is not a Fortify Developer Workbook. '
                f'Expected a "{self.MARK_RESULTS_OUTLINE}" section (not found). '
                "Provide the PDF exported from the Fortify scan portal."
            )
        elif self.MARK_KINGDOM not in pdf_text:
            errors.append(
                f'PDF has a "{self.MARK_RESULTS_OUTLINE}" section but contains no '
                f'issue blocks ("{self.MARK_KINGDOM}" marker not found). '
                "The workbook may be empty or from a scan with zero findings."
            )

        if errors:
            return ValidationResult(False, tuple(errors))
        return ValidationResult(True, ())

    def validate_reader(self, reader: object) -> ValidationResult:  # type: ignore[override]
        """
        Convenience wrapper: extract text from a ``pypdf.PdfReader`` and validate.
        """
        parts: list[str] = []
        pages = getattr(reader, "pages", [])
        for page in pages:
            try:
                text = page.extract_text() or ""
                parts.append(text)
            except Exception:  # noqa: BLE001
                continue
        return self.validate_text("\n".join(parts))
