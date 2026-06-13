#!/usr/bin/env python3
"""One-off: fill Phase-2 placeholder columns for fortify_priority=Critical rows. Run from repo root."""
from __future__ import annotations

import csv
import uuid
from pathlib import Path

def _repo_root() -> Path:
    """Resolve MIDAS repo root (directory containing `.git`)."""
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / ".git").is_dir():
            return anc
    raise RuntimeError(f"Cannot resolve repo root from {here}")


REPO = _repo_root()
CSV_IN = REPO / ".cursor/scratch/extracted_files/workbook_issues.csv"
LOG_DIR = REPO / ".cursor/scratch/analysis_log"
RUN_LOG = REPO / ".cursor/scratch/extracted_files/_phase2_critical_run.log"


def _scope(cat: str, sink: str) -> str:
    return f"{cat.split(':')[0][:60]}; primary path `{sink or 'n/a'}`."


def _fill(row: dict[str, str]) -> tuple[dict[str, str], str]:
    aid = str(uuid.uuid4())
    cat = row.get("category") or ""
    sink = (row.get("sink_file") or "").lower()
    obv = row.get("obv_id") or ""

    row["analysis_id"] = aid
    row["analysis_log_file"] = f".cursor/scratch/analysis_log/{aid}.md"
    row["issue_state"] = "ANALYZED"
    row["issue_resolve_progress"] = "Initial agent triage; placeholders filled from repo context."
    row["working_log"] = f".cursor/scratch/analysis_log/{aid}.md"
    row["resolved_date"] = ""
    row["issue_scope_summary"] = _scope(cat, row.get("sink_file") or "")

    # Defaults
    owner = "AI_AGENT"
    complexity = "HIGH"
    human_h, cursor_h, hybrid_h = "2", "1", "3"

    rc: list[str] = []
    plan: list[str] = []
    val: list[str] = []
    accept: list[str] = []

    if "token.txt" in sink or "Hardcoded API" in cat:
        owner = "AI_AGENT"
        complexity = "LOW"
        rc.append(
            "`frontend/token.txt` contains a JWT-shaped token committed to the repo; Fortify flags hardcoded API credentials."
        )
        plan.extend(
            [
                "1) Remove `frontend/token.txt` from tracked sources or replace with a non-secret placeholder.",
                "2) Load runtime tokens from env or a secrets manager; never commit production credentials.",
                "3) Add `token.txt` (or patterns) to `.gitignore` if a local-only file is still needed.",
            ]
        )
        val.extend(["Secret scanners clean", "File absent from default branch or contains only non-sensitive placeholder"])
        accept.extend(
            [
                "No live credentials in `frontend/token.txt` on tracked branches",
                "CI secret scan passes for this path",
            ]
        )
    elif "Cross-Site Scripting" in cat or "Cross-Site Scripting" in (row.get("kingdom") or ""):
        owner = "AI_AGENT"
        complexity = "MID"
        rc.append(
            "Fortify data-flow flags DOM XSS risk where browser-controlled data reaches markup or handlers without sufficient encoding/sanitization."
        )
        plan.extend(
            [
                "1) Inspect the cited component/HTML; ensure React JSX escapes dynamic values.",
                "2) For `dangerouslySetInnerHTML` or raw HTML docs under `docs/html_diagram/`, sanitize or remove.",
                "3) Prefer CSP and trusted types where applicable.",
            ]
        )
        val.extend(["ESLint/react security rules", "Manual retest of affected UI/docs", "Fortify rescan on scope"])
        accept.extend(["No unsanitized HTML injection from URL/query in flagged sinks", "Fortify XSS category cleared for path"])
    elif "Insecure Transport" in cat:
        owner = "H_REQ"
        complexity = "MID"
        rc.append(
            "`frontend/production-server.cjs` uses plain HTTP for local static hosting; acceptable for dev-only if production uses HTTPS behind ALB."
        )
        plan.extend(
            [
                "1) Document that this server is dev/local-only.",
                "2) Ensure production traffic terminates TLS on ALB per MIDAS architecture.",
                "3) Optionally gate the script so it cannot bind production-wide without TLS.",
            ]
        )
        val.extend(["Architecture review", "Prod ingress uses HTTPS only"])
        accept.extend(["Prod endpoints use TLS", "Dev exception documented"])
        human_h, cursor_h, hybrid_h = "1", "0", "2"
    elif "Hardcoded Password" in cat or "Password Management" in cat:
        owner = "H_REQ"
        complexity = "HIGH"
        rc.append(
            "Scanner detected password-like material in config/docs/terraform samples (e.g. compose defaults, commented examples)."
        )
        plan.extend(
            [
                "1) Replace literals with `${VAR}` / SSM / Secrets Manager references for real deploys.",
                "2) Redact or rotate any real credentials that were committed; purge from git history if leaked.",
                "3) Keep only non-functional placeholders in docs.",
            ]
        )
        val.extend(["`terraform plan` uses vars only", "Secrets rotation ticket if real creds exposed"])
        accept.extend(["No production passwords in compose/tf/md", "Fortify password category addressed"])
        human_h, cursor_h, hybrid_h = "4", "2", "6"
    else:
        rc.append("Fortify Critical finding; review sink against current repo revision.")
        plan.extend(["1) Confirm sink still exists.", "2) Apply vendor/Fortify recommendation.", "3) Retest."])
        val.extend(["Unit/IaC checks", "Fortify rescan"])
        accept.extend(["Sink remediated or risk accepted with ISG"])

    row["root_cause"] = " ".join(rc)
    row["remediation_plan"] = " ".join(plan)
    row["validation"] = "; ".join(val)
    row["acceptance_criteria"] = "; ".join(accept)
    row["resolution_owner"] = owner
    row["complexity"] = complexity
    row["human_fix_hours"] = human_h
    row["cursor_fix_hours"] = cursor_h
    row["hybrid_fix_hours"] = hybrid_h

    md = "\n".join(
        [
            f"# Analysis log — {obv}",
            f"",
            f"- **analysis_id:** `{aid}`",
            f"- **Category:** {cat}",
            f"- **Sink:** `{row.get('sink_file')}` line {row.get('sink_line')}",
            f"",
            "## Summary",
            row["root_cause"],
            f"",
            "## Plan",
            row["remediation_plan"],
            f"",
            "## Validation",
            row["validation"],
            f"",
        ]
    )
    return row, md


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if not CSV_IN.is_file():
        RUN_LOG.write_text(f"ERROR missing csv at {CSV_IN}\n", encoding="utf-8")
        raise SystemExit(1)

    with CSV_IN.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        assert fieldnames
        rows = list(reader)

    n = 0
    logs: dict[str, str] = {}
    out_rows: list[dict[str, str]] = []
    for row in rows:
        if (row.get("fortify_priority") or "").strip() != "Critical":
            out_rows.append(row)
            continue
        updated, md = _fill(dict(row))
        out_rows.append(updated)
        logs[updated["analysis_id"]] = md
        n += 1

    for aid, body in logs.items():
        (LOG_DIR / f"{aid}.md").write_text(body, encoding="utf-8")

    tmp = CSV_IN.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(out_rows)
    tmp.replace(CSV_IN)

    msg = (
        f"repo={REPO}\ncsv={CSV_IN}\nupdated_critical_rows={n}\nlogs_dir={LOG_DIR}\n"
    )
    RUN_LOG.write_text(msg, encoding="utf-8")
    print(msg, end="")


if __name__ == "__main__":
    main()
