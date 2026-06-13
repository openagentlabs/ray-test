"""
isg-pdf-validate — validate a PDF is a genuine Fortify ISG Developer Workbook.

Exit codes:
  0  PDF is a valid Fortify Developer Workbook (pass)
  1  Validation failed (fail — specific reason printed to stderr)
  2  Usage / argument error
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# ── Fortify structure markers ──────────────────────────────────────────────────
MARK_RESULTS_OUTLINE = "Results Outline"
MARK_KINGDOM = "Kingdom:"
PDF_MAGIC = b"%PDF"


# ── helpers ───────────────────────────────────────────────────────────────────

def _fail(message: str) -> None:
    print(f"[FAIL] {message}", file=sys.stderr)
    sys.exit(1)


def _pass(message: str) -> None:
    print(f"[PASS] {message}")


# ── validators ────────────────────────────────────────────────────────────────

def _validate_file_exists(path: Path) -> None:
    if not path.exists():
        _fail(f"File not found: {path}")
    if not path.is_file():
        _fail(f"Path is not a file: {path}")


def _validate_pdf_format(path: Path) -> None:
    if path.suffix.lower() != ".pdf":
        _fail(
            "Not a PDF file — expected .pdf extension and %PDF header. "
            f"Got extension: '{path.suffix}'"
        )
    with path.open("rb") as fh:
        header = fh.read(8)
    if not header.startswith(PDF_MAGIC):
        _fail(
            f"Not a PDF file — expected %PDF header but got: {header!r}. "
            "Provide the PDF exported from the Fortify scan portal."
        )


def _validate_not_encrypted(reader) -> None:  # type: ignore[no-untyped-def]
    if reader.is_encrypted:
        _fail(
            "PDF is password-protected. Decrypt it before uploading. "
            "Use the password from your ISG/Fortify portal to unlock the document."
        )


def _validate_has_pages(reader) -> None:  # type: ignore[no-untyped-def]
    page_count = len(reader.pages)
    if page_count == 0:
        _fail(
            "PDF has no pages. The file may be corrupt. "
            "Re-export it from the Fortify scan portal."
        )


def _extract_text(reader) -> str:  # type: ignore[no-untyped-def]
    """Concatenate text from all pages (best-effort)."""
    parts: list[str] = []
    for page in reader.pages:
        try:
            text = page.extract_text() or ""
            parts.append(text)
        except Exception:  # noqa: BLE001
            continue
    return "\n".join(parts)


def _validate_fortify_structure(pdf_text: str) -> None:
    if MARK_RESULTS_OUTLINE not in pdf_text:
        _fail(
            'This PDF is not a Fortify Developer Workbook. '
            f'Expected a "{MARK_RESULTS_OUTLINE}" section (not found). '
            "Provide the PDF exported from the Fortify scan portal."
        )
    if MARK_KINGDOM not in pdf_text:
        _fail(
            f'PDF has a "{MARK_RESULTS_OUTLINE}" section but contains no issue blocks '
            f'("{MARK_KINGDOM}" marker not found). '
            "The workbook may be empty or from a scan with zero findings."
        )


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="isg-pdf-validate",
        description="Validate a PDF is a genuine Fortify ISG Developer Workbook",
    )
    parser.add_argument(
        "pdf",
        metavar="PDF_PATH",
        help="Path to the PDF file to validate",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit structured JSON result instead of human-readable text",
    )
    args = parser.parse_args()

    path = Path(args.pdf).expanduser().resolve()

    # Step 1 — file exists and is a file
    _validate_file_exists(path)

    # Step 2 — PDF format check (extension + magic bytes)
    _validate_pdf_format(path)

    # Step 3 — open with pypdf
    try:
        import pypdf  # noqa: PLC0415
        reader = pypdf.PdfReader(str(path))
    except Exception as exc:  # noqa: BLE001
        _fail(f"Could not open PDF: {exc}")

    # Step 4 — not encrypted
    _validate_not_encrypted(reader)  # type: ignore[possibly-undefined]

    # Step 5 — has pages
    _validate_has_pages(reader)  # type: ignore[possibly-undefined]

    # Step 6 — Fortify structure
    pdf_text = _extract_text(reader)  # type: ignore[possibly-undefined]
    _validate_fortify_structure(pdf_text)

    page_count = len(reader.pages)  # type: ignore[possibly-undefined]
    if args.json:
        import json  # noqa: PLC0415
        print(json.dumps({"status": "pass", "pages": page_count, "path": str(path)}))
    else:
        _pass(
            f"Valid Fortify Developer Workbook — {page_count} page(s): {path.name}"
        )
