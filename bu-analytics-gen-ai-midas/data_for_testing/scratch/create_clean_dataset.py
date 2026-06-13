"""
Creates a cleaned training dataset from tt3_2gb.csv.
Original file is NEVER modified.
Output: data_for_testing/tt3_2gb_clean.csv

Fixes applied:
  1. Drops columns with >=50% missing values in the sample scan.
  2. Fills remaining missing numeric values with column median.
  3. Balances target classes via undersampling the majority class
     so class 0 : class 1 = 10 : 1  (retains ALL class-1 rows).
  4. Clips extreme outliers to 1st / 99th percentile per column
     (computed on the first 50k rows, then applied to whole file).
  5. Drops the constant target_Variable column issue is moot
     (it is the label — kept as-is, just named correctly).

All decisions are logged to:  data_for_testing/scratch/clean_run.log
"""

import csv
import os
import sys
import math
import random
import logging
from collections import defaultdict

# ── Config ───────────────────────────────────────────────────────────────────
BASE = os.path.join(os.path.dirname(__file__), "..")
INPUT_CSV   = os.path.abspath(os.path.join(BASE, "tt3_2gb.csv"))
OUTPUT_CSV  = os.path.abspath(os.path.join(BASE, "tt3_2gb_clean.csv"))
LOG_FILE    = os.path.abspath(os.path.join(os.path.dirname(__file__), "clean_run.log"))

MISSING_DROP_THRESHOLD = 0.50   # drop column if >50% empty in sample
SAMPLE_ROWS_STATS      = 50_000  # rows used to compute stats
MAJORITY_RATIO         = 10      # keep at most 10 class-0 rows per class-1 row
RANDOM_SEED            = 42

random.seed(RANDOM_SEED)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode="w"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

log.info(f"Input : {INPUT_CSV}")
log.info(f"Output: {OUTPUT_CSV}")
log.info(f"Log   : {LOG_FILE}")

# ── Pass 1: compute column stats on sample ────────────────────────────────────
log.info("Pass 1/3 — computing column stats on first %d rows ...", SAMPLE_ROWS_STATS)

with open(INPUT_CSV, newline="", encoding="utf-8") as fh:
    reader = csv.reader(fh)
    header = next(reader)

n_cols = len(header)
target_idx = header.index("target_Variable")

col_missing = [0] * n_cols
col_vals    = [[] for _ in range(n_cols)]   # numeric values per col

sample_count = 0
with open(INPUT_CSV, newline="", encoding="utf-8") as fh:
    reader = csv.reader(fh)
    next(reader)
    for row in reader:
        if sample_count >= SAMPLE_ROWS_STATS:
            break
        if len(row) != n_cols:
            sample_count += 1
            continue
        for i, v in enumerate(row):
            s = v.strip()
            if s == "":
                col_missing[i] += 1
            else:
                try:
                    f = float(s)
                    if not math.isnan(f) and not math.isinf(f):
                        col_vals[i].append(f)
                except ValueError:
                    pass
        sample_count += 1

log.info("  Sample rows processed: %d", sample_count)

# Decide which columns to DROP (>50% missing in sample)
drop_cols = set()
for i, col in enumerate(header):
    miss_pct = col_missing[i] / sample_count if sample_count else 0
    if miss_pct > MISSING_DROP_THRESHOLD:
        drop_cols.add(i)
        log.info("  DROP column %s  (%.1f%% missing)", col, miss_pct * 100)

log.info("  Columns dropped: %d / %d", len(drop_cols), n_cols)

# Compute median and percentile clips for kept columns
col_median = {}
col_p01    = {}
col_p99    = {}

for i in range(n_cols):
    if i in drop_cols:
        continue
    vals = sorted(col_vals[i])
    if not vals:
        col_median[i] = 0.0
        col_p01[i]    = None
        col_p99[i]    = None
        continue
    n = len(vals)
    col_median[i] = vals[n // 2]
    col_p01[i]    = vals[max(0, int(n * 0.01))]
    col_p99[i]    = vals[min(n - 1, int(n * 0.99))]

# Build kept header
kept_indices = [i for i in range(n_cols) if i not in drop_cols]
out_header   = [header[i] for i in kept_indices]
log.info("  Output columns: %d", len(out_header))

# ── Pass 2: count class-1 rows in full file ───────────────────────────────────
log.info("Pass 2/3 — counting class-1 rows in full file ...")
class1_count = 0
class0_count = 0
with open(INPUT_CSV, newline="", encoding="utf-8") as fh:
    reader = csv.reader(fh)
    next(reader)
    for row in reader:
        if len(row) != n_cols:
            continue
        t = row[target_idx].strip()
        if t == "1":
            class1_count += 1
        else:
            class0_count += 1

log.info("  Class 1 rows: %d", class1_count)
log.info("  Class 0 rows: %d", class0_count)

max_class0 = class1_count * MAJORITY_RATIO
log.info("  Will keep up to %d class-0 rows (%d:1 ratio)", max_class0, MAJORITY_RATIO)

# Probability of keeping each class-0 row (reservoir-style)
keep_prob_class0 = min(1.0, max_class0 / class0_count) if class0_count > 0 else 1.0
log.info("  Class-0 keep probability: %.4f", keep_prob_class0)

# ── Pass 3: write output ──────────────────────────────────────────────────────
log.info("Pass 3/3 — writing cleaned output ...")

written_class0 = 0
written_class1 = 0
skipped_bad    = 0

def clean_val(i, raw):
    """Return a cleaned string value for column i."""
    s = raw.strip()
    if s == "" or s is None:
        # fill with median
        return str(col_median.get(i, 0.0))
    try:
        f = float(s)
        if math.isnan(f) or math.isinf(f):
            return str(col_median.get(i, 0.0))
        # clip to [p01, p99]
        lo = col_p01.get(i)
        hi = col_p99.get(i)
        if lo is not None and f < lo:
            f = lo
        if hi is not None and f > hi:
            f = hi
        # keep as int string if it was originally integer-looking
        if f == int(f) and abs(f) < 1e15:
            return str(int(f))
        return str(f)
    except ValueError:
        return s   # non-numeric: leave as-is

with open(INPUT_CSV, newline="", encoding="utf-8") as fin, \
     open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fout:

    reader = csv.reader(fin)
    writer = csv.writer(fout)

    next(reader)                     # skip original header
    writer.writerow(out_header)      # write new header

    for row in reader:
        if len(row) != n_cols:
            skipped_bad += 1
            continue

        t = row[target_idx].strip()
        is_class1 = (t == "1")

        if not is_class1:
            if random.random() > keep_prob_class0:
                continue             # skip this majority row

        out_row = [clean_val(i, row[i]) for i in kept_indices]
        writer.writerow(out_row)

        if is_class1:
            written_class1 += 1
        else:
            written_class0 += 1

        if (written_class0 + written_class1) % 100_000 == 0:
            log.info("  ... written %d rows so far (c0=%d, c1=%d)",
                     written_class0 + written_class1, written_class0, written_class1)

total_written = written_class0 + written_class1
log.info("Done.")
log.info("  Total rows written : %d", total_written)
log.info("  Class 0 written    : %d", written_class0)
log.info("  Class 1 written    : %d", written_class1)
log.info("  Bad rows skipped   : %d", skipped_bad)
log.info("  Output file        : %s", OUTPUT_CSV)

out_size = os.path.getsize(OUTPUT_CSV) / (1024 ** 2)
log.info("  Output size        : %.1f MB", out_size)

# ── Print change summary to stdout ────────────────────────────────────────────
print()
print("=" * 60)
print("  CLEAN DATASET SUMMARY")
print("=" * 60)
print(f"  Original rows      : {class0_count + class1_count:>10,}")
print(f"  Output rows        : {total_written:>10,}  ({100*total_written/(class0_count+class1_count):.1f}% of original)")
print(f"  Original columns   : {n_cols:>10,}")
print(f"  Output columns     : {len(out_header):>10,}  ({len(drop_cols)} dropped)")
print(f"  Class 0 written    : {written_class0:>10,}")
print(f"  Class 1 written    : {written_class1:>10,}")
actual_ratio = written_class0 / written_class1 if written_class1 else 0
print(f"  Class ratio (0:1)  : {actual_ratio:>10.1f}  : 1")
print(f"  Output file        : {OUTPUT_CSV}")
print(f"  Log file           : {LOG_FILE}")
print("=" * 60)
