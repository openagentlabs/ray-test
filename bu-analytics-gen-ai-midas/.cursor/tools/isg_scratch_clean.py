#!/usr/bin/env python3
"""Delete all files inside .cursor/scratch/analysis_log and .cursor/scratch/extracted_files.

Directories themselves are preserved so subsequent steps can write into them.
Run from the repo root.
"""
from __future__ import annotations

from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / ".git").is_dir():
            return anc
    raise RuntimeError(f"Cannot resolve repo root from {here}")


SCRATCH_DIRS = [
    ".cursor/scratch/analysis_log",
    ".cursor/scratch/extracted_files",
]


def main() -> None:
    repo = _repo_root()
    deleted: list[Path] = []
    missing: list[str] = []

    for rel in SCRATCH_DIRS:
        d = repo / rel
        if not d.exists():
            missing.append(rel)
            print(f"[skip] {rel} — does not exist")
            continue
        files = [f for f in d.iterdir() if f.is_file()]
        if not files:
            print(f"[skip] {rel} — already empty")
            continue
        print(f"[clean] {rel} — {len(files)} file(s):")
        for f in sorted(files):
            print(f"  {f.name}")
        for f in files:
            f.unlink()
            deleted.append(f)

    print(f"\nDeleted {len(deleted)} file(s) across {len(SCRATCH_DIRS) - len(missing)} director(ies).")
    if deleted:
        print("Scratch folders are now empty and ready for a fresh run.")


if __name__ == "__main__":
    main()
