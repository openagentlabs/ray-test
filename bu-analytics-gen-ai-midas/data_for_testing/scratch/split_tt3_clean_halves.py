"""
Split tt3_2gb_clean.csv into two new datasets of roughly equal size.

Uses a stratified split on target_Variable so each half keeps a similar
class-0 / class-1 ratio. Original clean file is not modified.

Outputs (same folder as the clean source):
  tt3_2gb_clean_half_a.csv
  tt3_2gb_clean_half_b.csv
"""

from __future__ import annotations

import csv
import random
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SOURCE = BASE / "tt3_2gb_clean.csv"
OUT_A = BASE / "tt3_2gb_clean_half_a.csv"
OUT_B = BASE / "tt3_2gb_clean_half_b.csv"

TARGET_COL = "target_Variable"
RANDOM_SEED = 42


def main() -> None:
    """Read clean CSV, stratify-split rows 50/50, write two output files."""
    if not SOURCE.is_file():
        print(f"[ERROR] Missing source file: {SOURCE}", file=sys.stderr)
        sys.exit(1)

    random.seed(RANDOM_SEED)

    with SOURCE.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        try:
            target_idx = header.index(TARGET_COL)
        except ValueError:
            print(f"[ERROR] Column {TARGET_COL!r} not found in header.", file=sys.stderr)
            sys.exit(1)

        rows_by_target: dict[str, list[list[str]]] = {"0": [], "1": []}
        bad_target = 0
        for row in reader:
            if len(row) != len(header):
                continue
            key = row[target_idx].strip()
            if key not in rows_by_target:
                bad_target += 1
                continue
            rows_by_target[key].append(row)

    rng = random.Random(RANDOM_SEED)
    half_a: list[list[str]] = []
    half_b: list[list[str]] = []

    for target_key in sorted(rows_by_target.keys()):
        bucket = rows_by_target[target_key][:]
        rng.shuffle(bucket)
        mid = len(bucket) // 2
        half_a.extend(bucket[:mid])
        half_b.extend(bucket[mid:])

    rng.shuffle(half_a)
    rng.shuffle(half_b)

    for path, rows in ((OUT_A, half_a), (OUT_B, half_b)):
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            writer.writerows(rows)

    n0_a = sum(1 for r in half_a if r[target_idx].strip() == "0")
    n1_a = len(half_a) - n0_a
    n0_b = sum(1 for r in half_b if r[target_idx].strip() == "0")
    n1_b = len(half_b) - n0_b

    print(f"Source : {SOURCE}")
    print(f"Half A : {OUT_A}  ({len(half_a):,} rows)")
    print(f"         class 0={n0_a:,}  class 1={n1_a:,}")
    print(f"Half B : {OUT_B}  ({len(half_b):,} rows)")
    print(f"         class 0={n0_b:,}  class 1={n1_b:,}")
    if bad_target:
        print(f"[WARN] Skipped {bad_target} rows with unexpected target value.")


if __name__ == "__main__":
    main()
