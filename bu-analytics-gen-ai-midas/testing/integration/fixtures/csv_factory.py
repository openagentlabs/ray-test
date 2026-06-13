"""Builds a small in-memory CSV for use in upload fixtures."""

from __future__ import annotations

import csv
import io


def build_tiny_csv(rows: int = 20) -> bytes:
    """Return UTF-8 encoded CSV bytes with age, income, target_flag columns."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=["age", "income", "target_flag"])
    writer.writeheader()
    for i in range(rows):
        writer.writerow(
            {
                "age": 25 + i,
                "income": 30000 + i * 500,
                "target_flag": i % 2,
            }
        )
    return buf.getvalue().encode("utf-8")
