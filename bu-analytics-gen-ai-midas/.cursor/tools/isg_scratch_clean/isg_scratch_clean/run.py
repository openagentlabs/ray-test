"""CLI entry point: delete all files in .cursor/scratch sub-folders.

Directories are preserved so subsequent pipeline steps can write into them
immediately without re-running mkdir.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRATCH_DIRS = [
    ".cursor/scratch/analysis_log",
    ".cursor/scratch/extracted_files",
]


def _repo_root() -> Path:
    """Walk up from __file__ to find the git repo root."""
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / ".git").is_dir():
            return anc
    raise RuntimeError(f"Cannot resolve repo root from {here}")


def clean(repo: Path, dry_run: bool = False) -> int:
    """Delete all files in every SCRATCH_DIR under *repo*.

    Args:
        repo: Absolute path to the repo root.
        dry_run: When True, print what would be deleted but do not delete.

    Returns:
        Total number of files deleted (or that would be deleted in dry-run).
    """
    deleted: list[Path] = []

    for rel in SCRATCH_DIRS:
        d = repo / rel
        if not d.exists():
            print(f"[skip] {rel} — does not exist")
            continue
        files = sorted(f for f in d.iterdir() if f.is_file())
        if not files:
            print(f"[skip] {rel} — already empty")
            continue
        tag = "[dry-run]" if dry_run else "[clean]"
        print(f"{tag} {rel} — {len(files)} file(s):")
        for f in files:
            print(f"  {f.name}")
            if not dry_run:
                f.unlink()
        deleted.extend(files)

    verb = "Would delete" if dry_run else "Deleted"
    print(f"\n{verb} {len(deleted)} file(s).")
    if deleted and not dry_run:
        print("Scratch folders are now empty and ready for a fresh run.")
    return len(deleted)


def main() -> None:
    """CLI entry point for isg-scratch-clean."""
    parser = argparse.ArgumentParser(
        description="Delete all files in .cursor/scratch/analysis_log and "
                    ".cursor/scratch/extracted_files (directories preserved).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be deleted without deleting anything.",
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="Repo root path (default: auto-detected from .git).",
    )
    args = parser.parse_args()

    repo = Path(args.repo).resolve() if args.repo else _repo_root()
    try:
        clean(repo, dry_run=args.dry_run)
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
