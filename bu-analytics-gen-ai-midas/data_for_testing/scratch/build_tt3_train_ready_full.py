"""
Build a full-size (~4M row) train-ready CSV from tt3_2gb.csv.

- Keeps every valid row (same row count as source minus malformed lines).
- Keeps all 174 columns (same header / schema as tt3_2gb.csv).
- Does NOT modify tt3_2gb.csv.

Cleaning (realistic ML preprocessing, single pass over full data after sample stats):
  - Rows with wrong column count are skipped (logged).
  - Numeric columns: empty / NaN / inf filled with sample median; values winsorized
    to sample p01–p99 (from first SAMPLE_ROWS valid rows).
  - Non-numeric columns (e.g. CAMPAIGN_SEQUENCE_NUMBER): preserved; empty filled with
    column mode from sample or a deterministic synthetic placeholder.
  - target_Variable coerced to 0 or 1 only.

Output: data_for_testing/tt3_2gb_train_ready.csv
Log:     data_for_testing/scratch/train_ready_full.log
"""

from __future__ import annotations

import csv
import logging
import math
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
SOURCE = BASE / "tt3_2gb.csv"
OUTPUT = BASE / "tt3_2gb_train_ready.csv"
LOG_PATH = Path(__file__).resolve().parent / "train_ready_full.log"

SAMPLE_ROWS = 150_000
TARGET_COL = "target_Variable"
CAMPAIGN_COL = "CAMPAIGN_SEQUENCE_NUMBER"

# Never parse these as floats — Python accepts underscores in numeric literals and would
# corrupt IDs like "1_1365838000" into the wrong number.
FORCE_STRING_COLUMNS = frozenset({CAMPAIGN_COL})


def _configure_logging() -> logging.Logger:
    """Configure file + stdout logging."""
    log = logging.getLogger("train_ready_full")
    log.setLevel(logging.INFO)
    log.handlers.clear()
    fh = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s"))
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s"))
    log.addHandler(fh)
    log.addHandler(sh)
    return log


def _percentile_sorted(sorted_vals: list[float], q: float) -> float | None:
    """Return q percentile (q in [0,1]) from a non-empty sorted list."""
    if not sorted_vals:
        return None
    n = len(sorted_vals)
    idx = min(n - 1, max(0, int(q * (n - 1))))
    return sorted_vals[idx]


def main() -> None:
    """Sample stats from SOURCE, then stream-clean into OUTPUT."""
    log = _configure_logging()
    if not SOURCE.is_file():
        log.error("Missing source: %s", SOURCE)
        sys.exit(1)

    log.info("Source: %s", SOURCE)
    log.info("Output: %s", OUTPUT)
    log.info("Sample rows for stats: %s", SAMPLE_ROWS)

    with SOURCE.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)

    n_cols = len(header)
    try:
        target_idx = header.index(TARGET_COL)
    except ValueError:
        log.error("Missing column %r", TARGET_COL)
        sys.exit(1)
    try:
        campaign_idx = header.index(CAMPAIGN_COL)
    except ValueError:
        campaign_idx = -1

    col_vals: list[list[float]] = [[] for _ in range(n_cols)]
    col_nonempty = [0] * n_cols
    col_missing = [0] * n_cols
    col_mode_str: list[str] = ["" for _ in range(n_cols)]
    string_counters: list[Counter[str]] = [Counter() for _ in range(n_cols)]

    sample_seen = 0
    with SOURCE.open(newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader)
        for row in reader:
            if sample_seen >= SAMPLE_ROWS:
                break
            if len(row) != n_cols:
                continue
            sample_seen += 1
            for i, raw in enumerate(row):
                s = raw.strip()
                if s == "":
                    col_missing[i] += 1
                    continue
                col_nonempty[i] += 1
                if header[i] in FORCE_STRING_COLUMNS:
                    string_counters[i][s] += 1
                    continue
                try:
                    f = float(s)
                    if math.isnan(f) or math.isinf(f):
                        col_missing[i] += 1
                        continue
                    col_vals[i].append(f)
                except ValueError:
                    string_counters[i][s] += 1

    is_numeric = [False] * n_cols
    col_median: list[float] = [0.0] * n_cols
    col_p01: list[float | None] = [None] * n_cols
    col_p99: list[float | None] = [None] * n_cols

    for i in range(n_cols):
        if header[i] in FORCE_STRING_COLUMNS:
            is_numeric[i] = False
            mode_tup = string_counters[i].most_common(1)
            col_mode_str[i] = mode_tup[0][0] if mode_tup else ""
            continue
        nv = len(col_vals[i])
        nn = col_nonempty[i]
        # Numeric if we have enough parsed numbers vs non-empty strings in sample
        if nv >= 50 and (nn == 0 or nv >= 0.85 * max(nn, 1)):
            is_numeric[i] = True
            sv = sorted(col_vals[i])
            col_median[i] = sv[len(sv) // 2]
            col_p01[i] = _percentile_sorted(sv, 0.01)
            col_p99[i] = _percentile_sorted(sv, 0.99)
        else:
            mode_tup = string_counters[i].most_common(1)
            col_mode_str[i] = mode_tup[0][0] if mode_tup else ""

    numeric_count = sum(is_numeric)
    log.info(
        "Sample processed valid rows: %s — numeric cols: %s / %s",
        sample_seen,
        numeric_count,
        n_cols,
    )

    def clean_cell(col_index: int, raw: str, row_num: int) -> str:
        """Return one cleaned cell string."""
        s = raw.strip()
        if header[col_index] in FORCE_STRING_COLUMNS:
            if s != "":
                return s
            if col_index == campaign_idx:
                return f"synthetic_{row_num}"
            return col_mode_str[col_index] if col_mode_str[col_index] else "unknown"

        if is_numeric[col_index]:
            if s == "":
                m = col_median[col_index]
                return str(int(m)) if m == int(m) and abs(m) < 1e15 else str(m)
            try:
                f = float(s)
                if math.isnan(f) or math.isinf(f):
                    m = col_median[col_index]
                    return str(int(m)) if m == int(m) and abs(m) < 1e15 else str(m)
                lo, hi = col_p01[col_index], col_p99[col_index]
                if lo is not None and f < lo:
                    f = lo
                if hi is not None and f > hi:
                    f = hi
                if f == int(f) and abs(f) < 1e15:
                    return str(int(f))
                return str(f)
            except ValueError:
                # Rare mixed column: fall back to mode/median as string
                fallback = col_mode_str[col_index] or str(col_median[col_index])
                return fallback if fallback else "0"

        # Non-numeric / ID columns
        if s != "":
            return raw.strip()
        if col_index == campaign_idx:
            return f"synthetic_{row_num}"
        return col_mode_str[col_index] if col_mode_str[col_index] else "unknown"

    skipped_bad = 0
    written = 0
    targets = Counter()

    with SOURCE.open(newline="", encoding="utf-8") as fin, OUTPUT.open(
        "w", newline="", encoding="utf-8"
    ) as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout, lineterminator="\n")
        writer.writerow(header)
        next(reader)

        for row_num, row in enumerate(reader, start=1):
            if len(row) != n_cols:
                skipped_bad += 1
                continue

            out: list[str] = []
            for i in range(n_cols):
                if i == target_idx:
                    t = row[i].strip()
                    if t == "1":
                        out.append("1")
                        targets["1"] += 1
                    elif t == "0":
                        out.append("0")
                        targets["0"] += 1
                    else:
                        try:
                            v = int(float(t))
                            tv = "1" if v == 1 else "0"
                        except ValueError:
                            tv = "0"
                        out.append(tv)
                        targets[tv] += 1
                else:
                    out.append(clean_cell(i, row[i], row_num))

            writer.writerow(out)
            written += 1

            if written % 400_000 == 0:
                log.info("Written %s rows ...", f"{written:,}")

    log.info("Done. Written rows: %s", f"{written:,}")
    log.info("Skipped (bad width): %s", f"{skipped_bad:,}")
    log.info("Target counts: %s", dict(targets))
    size_mb = OUTPUT.stat().st_size / (1024**2)
    log.info("Output size: %.1f MB", size_mb)

    print()
    print("=" * 60)
    print("  TRAIN-READY FULL FILE")
    print("=" * 60)
    print(f"  Output        : {OUTPUT}")
    print(f"  Data rows     : {written:,}")
    print(f"  Skipped rows  : {skipped_bad:,}")
    print(f"  Columns       : {n_cols}")
    print(f"  Target dist   : {dict(targets)}")
    print(f"  Size          : {size_mb:.1f} MB")
    print(f"  Log           : {LOG_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
