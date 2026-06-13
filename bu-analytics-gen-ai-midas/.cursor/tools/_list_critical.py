#!/usr/bin/env python3
import csv
from pathlib import Path

def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / ".git").is_dir():
            return anc
    raise RuntimeError(f"Cannot resolve repo root from {here}")


p = _repo_root() / ".cursor/scratch/extracted_files/workbook_issues.csv"
with p.open(newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))
crit = [r for r in rows if (r.get("fortify_priority") or "").strip() == "Critical"]
high = [r for r in rows if (r.get("fortify_priority") or "").strip() == "High"]
print("total", len(rows), "critical", len(crit), "high", len(high))
for r in crit:
    print(r["obv_id"], "|", (r.get("sink_file") or "")[:100])
