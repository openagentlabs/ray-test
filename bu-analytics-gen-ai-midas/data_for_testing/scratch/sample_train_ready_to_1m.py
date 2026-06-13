"""
Sample exactly N data rows from tt3_2gb_train_ready.csv without loading it all.

Uses a sorted uniform random index sample (reproducible seed). Preserves header.
Does not modify the source file.

Examples:
  python3 sample_train_ready_to_1m.py --rows 1000000   # -> tt3_2gb_train_ready_1m.csv
  python3 sample_train_ready_to_1m.py --rows 2000000   # -> tt3_2gb_train_ready_2m.csv
  python3 sample_train_ready_to_1m.py --rows 3000000 --output /path/out.csv
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SOURCE = BASE / "tt3_2gb_train_ready.csv"
DEFAULT_SEED = 42


def default_output_path(rows: int) -> Path:
    """Pick a conventional filename when --output is omitted."""
    if rows >= 1_000_000 and rows % 1_000_000 == 0:
        return BASE / f"tt3_2gb_train_ready_{rows // 1_000_000}m.csv"
    return BASE / f"tt3_2gb_train_ready_{rows}_rows.csv"


def main() -> None:
    """Write a random subset of SOURCE to OUTPUT."""
    parser = argparse.ArgumentParser(
        description="Random sample of rows from tt3_2gb_train_ready.csv",
    )
    parser.add_argument(
        "--rows",
        type=int,
        default=1_000_000,
        help="Number of data rows to sample (default: 1_000_000)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output CSV path (default: tt3_2gb_train_ready_<N>m.csv under data_for_testing/)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed (default: {DEFAULT_SEED})",
    )
    args = parser.parse_args()

    target_rows = args.rows
    if target_rows < 1:
        print("[ERROR] --rows must be >= 1", file=sys.stderr)
        sys.exit(1)

    output = Path(args.output) if args.output else default_output_path(target_rows)

    if not SOURCE.is_file():
        print(f"[ERROR] Missing source: {SOURCE}", file=sys.stderr)
        sys.exit(1)

    with SOURCE.open(newline="", encoding="utf-8") as fh:
        total_data = sum(1 for _ in fh) - 1

    if total_data <= 0:
        print("[ERROR] Source has no data rows.", file=sys.stderr)
        sys.exit(1)

    k = min(target_rows, total_data)
    rng = random.Random(args.seed)
    chosen = sorted(rng.sample(range(total_data), k))

    written = 0
    si = 0
    with SOURCE.open(newline="", encoding="utf-8") as fin, output.open(
        "w", newline="", encoding="utf-8"
    ) as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout, lineterminator="\n")
        header = next(reader)
        writer.writerow(header)

        for row_idx, row in enumerate(reader):
            if si >= len(chosen):
                break
            while si < len(chosen) and chosen[si] < row_idx:
                si += 1
            if si < len(chosen) and chosen[si] == row_idx:
                writer.writerow(row)
                written += 1
                si += 1

    print(f"Source data rows : {total_data:,}")
    print(f"Requested sample : {target_rows:,}")
    print(f"Written rows     : {written:,}")
    print(f"Output           : {output}")


if __name__ == "__main__":
    main()
