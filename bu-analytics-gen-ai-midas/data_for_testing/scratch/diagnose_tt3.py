"""
Diagnostic script for tt3_2gb.csv training data.
Identifies common ML training data issues:
  - Column count mismatches (broken rows)
  - Missing values per column
  - Duplicate rows
  - Target variable distribution
  - Non-numeric data in numeric columns
  - Constant / near-zero-variance columns
  - Extreme outliers (IQR method)
  - Infinite values
"""

import csv
import sys
import os
import math
import json
from collections import Counter, defaultdict

CSV_PATH = os.path.join(os.path.dirname(__file__), "..", "tt3_2gb.csv")
SAMPLE_ROWS = 50_000   # rows to load for heavy checks (full file for row-count checks)
TARGET_COL = "target_Variable"

print(f"=== tt3_2gb.csv Diagnostic ===")
print(f"File: {os.path.abspath(CSV_PATH)}")
print()

# ── 1. Quick row / column count (stream full file) ──────────────────────────
print("[ 1/8 ] Streaming full file for row count and column-mismatch check ...")
expected_cols = None
header = None
row_count = 0
bad_rows = []          # (line_number, actual_col_count)
target_values = Counter()
seen_ids = set()
dupe_ids = 0

with open(CSV_PATH, newline="", encoding="utf-8") as fh:
    reader = csv.reader(fh)
    for lineno, row in enumerate(reader, start=1):
        if lineno == 1:
            header = row
            expected_cols = len(row)
            try:
                target_idx = header.index(TARGET_COL)
                id_idx = header.index("CAMPAIGN_SEQUENCE_NUMBER")
            except ValueError as e:
                print(f"  [WARN] Column not found: {e}")
                target_idx = 0
                id_idx = 1
            continue

        row_count += 1
        if len(row) != expected_cols:
            if len(bad_rows) < 20:          # keep first 20 examples
                bad_rows.append((lineno, len(row)))

        if row_count <= SAMPLE_ROWS:
            target_values[row[target_idx].strip()] += 1
            uid = row[id_idx].strip()
            if uid in seen_ids:
                dupe_ids += 1
            seen_ids.add(uid)

print(f"  Rows (excl. header): {row_count:,}")
print(f"  Columns:             {expected_cols}")
print(f"  Bad-column-count rows: {len(bad_rows):,}" + (" (showing first 20)" if bad_rows else ""))
for ln, cnt in bad_rows[:10]:
    print(f"    line {ln}: {cnt} columns (expected {expected_cols})")

# ── 2. Target variable distribution ─────────────────────────────────────────
print()
print(f"[ 2/8 ] Target variable distribution (first {SAMPLE_ROWS:,} rows) ...")
total_targets = sum(target_values.values())
for val, cnt in sorted(target_values.items()):
    pct = 100.0 * cnt / total_targets if total_targets else 0
    print(f"  target={val!r:>4}  count={cnt:>8,}  ({pct:.1f}%)")

# ── 3. Duplicate IDs ─────────────────────────────────────────────────────────
print()
print(f"[ 3/8 ] Duplicate CAMPAIGN_SEQUENCE_NUMBER (first {SAMPLE_ROWS:,} rows) ...")
print(f"  Duplicate IDs: {dupe_ids:,}")

# ── 4. Per-column missing + numeric check (sample) ──────────────────────────
print()
print(f"[ 4/8 ] Per-column analysis (first {SAMPLE_ROWS:,} rows) ...")

col_missing  = defaultdict(int)
col_non_num  = defaultdict(int)
col_values   = defaultdict(list)   # for variance / outlier check
col_infinite = defaultdict(int)

sample_count = 0
with open(CSV_PATH, newline="", encoding="utf-8") as fh:
    reader = csv.reader(fh)
    next(reader)  # skip header
    for row in reader:
        if sample_count >= SAMPLE_ROWS:
            break
        if len(row) != expected_cols:
            sample_count += 1
            continue
        for i, val in enumerate(row):
            v = val.strip()
            if v == "" or v is None:
                col_missing[i] += 1
            else:
                try:
                    f = float(v)
                    if math.isinf(f):
                        col_infinite[i] += 1
                    elif not math.isnan(f):
                        col_values[i].append(f)
                except ValueError:
                    col_non_num[i] += 1
        sample_count += 1

# ── 5. Summarise per-column findings ────────────────────────────────────────
high_missing     = []
non_numeric_cols = []
constant_cols    = []
extreme_outlier_cols = []

for i, col in enumerate(header):
    miss = col_missing[i]
    miss_pct = 100.0 * miss / sample_count if sample_count else 0
    non_num = col_non_num[i]
    inf_cnt = col_infinite[i]
    vals = col_values[i]

    if miss_pct >= 5:
        high_missing.append((col, miss, miss_pct))

    if non_num > 0:
        non_numeric_cols.append((col, non_num))

    if vals:
        mn = min(vals)
        mx = max(vals)
        if mn == mx:
            constant_cols.append(col)
        else:
            # IQR-based outlier check
            sv = sorted(vals)
            q1 = sv[len(sv) // 4]
            q3 = sv[(3 * len(sv)) // 4]
            iqr = q3 - q1
            fence_lo = q1 - 3 * iqr
            fence_hi = q3 + 3 * iqr
            n_out = sum(1 for v in vals if v < fence_lo or v > fence_hi)
            out_pct = 100.0 * n_out / len(vals)
            if out_pct >= 5:
                extreme_outlier_cols.append((col, n_out, out_pct))

print(f"  Sample rows analysed: {sample_count:,}")

# ── 6. Missing values ────────────────────────────────────────────────────────
print()
print(f"[ 5/8 ] Columns with ≥5 % missing values ({len(high_missing)} found) ...")
if high_missing:
    high_missing.sort(key=lambda x: -x[2])
    for col, cnt, pct in high_missing[:30]:
        print(f"  {col:<30}  {cnt:>7,} missing  ({pct:.1f}%)")
    if len(high_missing) > 30:
        print(f"  ... and {len(high_missing)-30} more columns")
else:
    print("  None above threshold.")

# ── 7. Non-numeric columns ───────────────────────────────────────────────────
print()
print(f"[ 6/8 ] Columns with non-numeric values ({len(non_numeric_cols)} found) ...")
if non_numeric_cols:
    for col, cnt in non_numeric_cols[:20]:
        print(f"  {col:<30}  {cnt:>7,} non-numeric values")
else:
    print("  None found.")

# ── 8. Constant columns ──────────────────────────────────────────────────────
print()
print(f"[ 7/8 ] Constant columns (zero variance in sample) — {len(constant_cols)} found ...")
for col in constant_cols[:20]:
    print(f"  {col}")

# ── 9. Extreme outlier columns ───────────────────────────────────────────────
print()
print(f"[ 8/8 ] Columns with ≥5 % extreme outliers (3×IQR) — {len(extreme_outlier_cols)} found ...")
if extreme_outlier_cols:
    extreme_outlier_cols.sort(key=lambda x: -x[2])
    for col, cnt, pct in extreme_outlier_cols[:20]:
        print(f"  {col:<30}  {cnt:>6,} outliers  ({pct:.1f}%)")
else:
    print("  None above threshold.")

# ── Summary ──────────────────────────────────────────────────────────────────
print()
print("=== SUMMARY ===")
issues = []
if bad_rows:
    issues.append(f"  ❌ {len(bad_rows):,} rows have wrong column count (row-parse error — major)")
if dupe_ids:
    issues.append(f"  ⚠️  {dupe_ids:,} duplicate CAMPAIGN_SEQUENCE_NUMBER in first {SAMPLE_ROWS:,} rows")
if high_missing:
    worst = high_missing[0]
    issues.append(f"  ⚠️  {len(high_missing)} columns have ≥5% missing (worst: {worst[0]} at {worst[2]:.0f}%)")
if non_numeric_cols:
    issues.append(f"  ⚠️  {len(non_numeric_cols)} columns contain non-numeric text values")
if constant_cols:
    issues.append(f"  ⚠️  {len(constant_cols)} constant columns (no information)")
if extreme_outlier_cols:
    issues.append(f"  ⚠️  {len(extreme_outlier_cols)} columns with ≥5% extreme outliers")

if issues:
    print("Issues found:")
    for iss in issues:
        print(iss)
else:
    print("  No critical issues detected in sample.")

print()
print("Done.")
