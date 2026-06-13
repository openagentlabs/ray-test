#!/usr/bin/env python3
"""
Write a small CSV that satisfies ec2-mt-test/pipeline.py:
  - target_Variable (binary classification)
  - CAMPAIGN_SEQUENCE_NUMBER
  - at least 20 numeric feature columns (feat_00 .. feat_24)
Uses only the Python standard library (no pandas on the jumpbox required).
"""
from __future__ import annotations

import argparse
import csv
import os
import random


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate smoke CSV for run_batch.py")
    parser.add_argument(
        "--out",
        default="data/smoke_ml.csv",
        help="Output path (parent directories are created)",
    )
    parser.add_argument("--rows", type=int, default=800, help="Number of data rows")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    random.seed(args.seed)

    out_path = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    feature_names = [f"feat_{i:02d}" for i in range(25)]
    fieldnames = ["CAMPAIGN_SEQUENCE_NUMBER", *feature_names, "target_Variable"]

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for i in range(1, args.rows + 1):
            row = {"CAMPAIGN_SEQUENCE_NUMBER": i}
            for name in feature_names:
                row[name] = f"{random.gauss(0, 1):.8f}"
            # Weakly separable label from first few features
            z = sum(float(row[f"feat_{j:02d}"]) for j in range(3))
            row["target_Variable"] = 1 if z > 0 else 0
            w.writerow(row)

    print(f"Wrote {args.rows} rows to {out_path}")


if __name__ == "__main__":
    main()
