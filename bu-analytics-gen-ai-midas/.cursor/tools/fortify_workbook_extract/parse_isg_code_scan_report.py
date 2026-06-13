#!/usr/bin/env python3
"""Backward-compatible shim. Canonical CLI: :file:`parse_isg_code_scan_report_tool.py`."""
from __future__ import annotations

if __name__ == "__main__":
    import runpy
    from pathlib import Path

    runpy.run_path(
        str(Path(__file__).resolve().parent / "parse_isg_code_scan_report_tool.py"),
        run_name="__main__",
    )
