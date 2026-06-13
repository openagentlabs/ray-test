"""Load raw text from Fortify Developer Workbook PDFs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, List, Optional, Tuple

try:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
except ImportError as exc:  # pragma: no cover
    raise ImportError("Install pypdf: pip install -r requirements-workbook-tools.txt") from exc

from fortify_workbook_tool.constants import MARK_RESULTS_OUTLINE

if TYPE_CHECKING:
    from fortify_workbook_tool.feedback import ColoredFeedback


class WorkbookPdfLoader:
    """Extracts plain text from the workbook PDF — first stage of the pipeline."""

    def load(self, pdf_path: Path, feedback: Optional["ColoredFeedback"] = None) -> Tuple[str, List[str]]:
        warnings: List[str] = []
        path = pdf_path.expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"PDF not found or not a file: {path}")

        try:
            reader = PdfReader(str(path))
        except PdfReadError as exc:
            raise ValueError(f"Cannot read PDF (corrupt or unsupported): {path}") from exc

        if getattr(reader, "is_encrypted", False):
            raise ValueError(f"PDF is encrypted; decrypt before extracting: {path}")

        n_pages = len(reader.pages)
        if feedback:
            feedback.step(f"Extracting text from {n_pages} page(s)…")

        parts: List[str] = []
        for idx, page in enumerate(reader.pages):
            try:
                parts.append(page.extract_text() or "")
            except Exception as exc:  # pragma: no cover
                warnings.append(f"Page {idx + 1}: text extraction failed ({exc!s}); placeholder empty.")
                parts.append("")

        text = "\n".join(parts)
        if feedback:
            feedback.ok(f"PDF text extracted ({len(text)} characters).")

        if len(text.strip()) < 500:
            warnings.append(
                "Extracted text is very short; parsing may fail (wrong file or broken extraction)."
            )
        if MARK_RESULTS_OUTLINE not in text:
            warnings.append(
                f"Anchor {MARK_RESULTS_OUTLINE!r} not found; this may not be a Fortify Developer Workbook."
            )

        return text, warnings
