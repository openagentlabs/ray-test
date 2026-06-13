#!/usr/bin/env python3
"""Fill Phase-2 placeholders for Fortify High / Medium / Low rows (skips rows with analysis_id set)."""
from __future__ import annotations

import csv
import uuid
from pathlib import Path


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for anc in here.parents:
        if (anc / ".git").is_dir():
            return anc
    raise RuntimeError(f"Cannot resolve repo root from {here}")


REPO = _repo_root()
CSV_IN = REPO / ".cursor/scratch/extracted_files/workbook_issues.csv"
LOG_DIR = REPO / ".cursor/scratch/analysis_log"
RUN_LOG = REPO / ".cursor/scratch/extracted_files/_phase2_hml_run.log"

TARGET_PRIORITIES = frozenset({"High", "Medium", "Low"})


def _paths_blob(row: dict[str, str]) -> str:
    parts = [
        row.get("sink_file") or "",
        row.get("source_file") or "",
        row.get("reference_line") or "",
    ]
    return " ".join(parts).replace("\\", "/")


def _is_ai_gateway(row: dict[str, str]) -> bool:
    return "ai_gateway" in _paths_blob(row).lower()


def _scope(cat: str, sink: str, source: str, work_kind: str) -> str:
    head = (cat.split(":")[0] if ":" in cat else cat)[:72]
    primary = sink or source or "n/a"
    return f"{head}; primary `{primary}`; {work_kind}."


def _hours(priority: str, owner: str, complexity: str) -> tuple[str, str, str]:
    """Whole hours as strings per skill."""
    ph, pc, py = "3", "2", "4"
    if priority == "Low":
        ph, pc, py = "2", "1", "3"
    elif priority == "Medium":
        ph, pc, py = "3", "2", "5"
    elif priority == "High":
        ph, pc, py = "5", "3", "7"

    if complexity == "LOW":
        ph, pc, py = str(max(1, int(ph) - 1)), str(max(1, int(pc) - 1)), str(max(2, int(py) - 1))
    elif complexity == "HIGH":
        ph, pc, py = str(int(ph) + 2), str(int(pc) + 1), str(int(py) + 2)
    elif complexity == "MAX":
        ph, pc, py = str(int(ph) + 6), str(int(pc) + 4), str(int(py) + 6)

    if owner == "H_REQ":
        py = str(int(py) + 2)

    return ph, pc, py


def _fill(row: dict[str, str]) -> tuple[dict[str, str], str]:
    cat = row.get("category") or ""
    priority = (row.get("fortify_priority") or "").strip()
    sink_path = row.get("sink_file") or ""
    src_path = row.get("source_file") or ""
    sink_lower = sink_path.lower()
    cat_lower = cat.lower()
    obv = row.get("obv_id") or ""

    aid = str(uuid.uuid4())
    row["analysis_id"] = aid
    row["analysis_log_file"] = f".cursor/scratch/analysis_log/{aid}.md"
    row["issue_state"] = "ANALYZED"
    row["issue_resolve_progress"] = (
        "Phase 2 batch triage (category routing); confirm sinks and apply fixes via Jenkins pipeline for shared envs."
    )
    row["working_log"] = f".cursor/scratch/analysis_log/{aid}.md"
    row["resolved_date"] = ""

    owner = "AI_AGENT"
    complexity = "MID"
    work_kind = "Terraform/IaC"
    if any(x in sink_lower for x in (".tsx", ".jsx", ".ts", ".js", ".py")) and "deploy/" not in sink_lower:
        work_kind = "Application code"

    rc: list[str] = []
    plan: list[str] = []
    val: list[str] = []
    accept: list[str] = []

    ag = _is_ai_gateway(row)

    # --- Same security patterns as Critical (can appear at any Fortify priority) ---
    if "token.txt" in sink_lower or "hardcoded api" in cat_lower:
        owner = "AI_AGENT"
        complexity = "LOW"
        work_kind = "Application code / secrets hygiene"
        rc.append(
            "Hardcoded API credential material under the cited path; credentials in VCS increase blast radius and bypass rotation."
        )
        plan.extend(
            [
                "1) Remove or replace with non-sensitive placeholders; never ship production secrets.",
                "2) Load secrets from runtime env or Secrets Manager; block commits via secret scanning.",
            ]
        )
        val.extend(["Gitleaks/secret scanner clean", "Fortify rescan"])
        accept.extend(["No live tokens in repo for this sink", "Scanner clears category for path"])
    elif "cross-site scripting" in cat_lower:
        owner = "AI_AGENT"
        complexity = "MID"
        work_kind = "Application code (DOM/UI)"
        rc.append(
            "Fortify flags DOM XSS risk: untrusted data may reach HTML or sinks without encoding/sanitization."
        )
        plan.extend(
            [
                "1) Trace data flow to the cited sink; ensure JSX escaping or sanitize HTML.",
                "2) Avoid raw HTML unless sanitized; add CSP where feasible.",
            ]
        )
        val.extend(["UI regression", "Fortify XSS cleared for path"])
        accept.extend(["No exploitable XSS from untrusted input at sink"])
    elif "insecure transport" in cat_lower:
        owner = "H_REQ"
        complexity = "MID"
        rc.append(
            "Plain HTTP or TLS downgrade risk at cited sink; production must align with MIDAS TLS-at-ingress patterns."
        )
        plan.extend(
            [
                "1) Confirm scope is dev-only vs prod.",
                "2) Ensure prod listeners use TLS (ALB/ACM); document exceptions.",
            ]
        )
        val.extend(["Architecture review", "Fortify transport category addressed"])
        accept.extend(["Prod uses HTTPS end-to-end per design"])
    elif "hardcoded password" in cat_lower or (
        "password management" in cat_lower and "hardcoded" in cat_lower
    ):
        owner = "H_REQ"
        complexity = "HIGH"
        rc.append(
            "Password or secret-like literal in config/docs/IaC samples; treat as credential hygiene risk."
        )
        plan.extend(
            [
                "1) Replace with variables and Secrets Manager/SSM references for real deploys.",
                "2) Rotate any real leaked credentials; scrub history if necessary.",
            ]
        )
        val.extend(["tf compose lint", "secret scan"])
        accept.extend(["No production passwords in repo"])

    elif ag:
        owner = "H_REQ"
        complexity = "MAX"
        work_kind = "Upstream submodule (`ai_gateway/`); coordinate Unified-Cloud-DevOps"
        rc.append(
            "Finding touches `ai_gateway/` paths; MIDAS treats this submodule as read-only — remediation is upstream or policy exception, not direct MIDAS edits."
        )
        plan.extend(
            [
                "1) Open/track upstream issue in AI Gateway repo per team process.",
                "2) Re-pin submodule after upstream fix; Fortify re-scan.",
                "3) Do not wire MIDAS Jenkins/Terraform to mutate `ai_gateway/**` content.",
            ]
        )
        val.extend(["Upstream release notes", "Submodule pin bump PR", "Fortify delta"])
        accept.extend(
            [
                "Upstream addresses finding or MIDAS documents accepted risk + compensating controls",
                "Submodule pinned to commit containing fix when applicable",
            ]
        )

    elif "cloudwatch missing" in cat_lower and "customer-managed" in cat_lower:
        complexity = "MID"
        rc.append(
            "CloudWatch log group lacks explicit customer-managed KMS (CMK); Fortify prefers CMK for audit/compliance over AWS-managed keys."
        )
        plan.extend(
            [
                "1) Add `kms_key_id` (CMK ARN) to affected `aws_cloudwatch_log_group` resources.",
                "2) Grant CloudWatch Logs service usage of the CMK per AWS docs.",
                "3) Deploy via MIDAS Jenkins pipeline (no laptop apply to shared envs).",
            ]
        )
        val.extend(["`terraform plan` shows CMK binding", "CloudWatch Logs encrypts with CMK"])
        accept.extend(["Rule no longer flags these resources", "KMS permissions documented"])

    elif cat.startswith("Encryption Key") or (
        "encryption key" in cat_lower and "terraform" in cat_lower
    ):
        complexity = "MID"
        rc.append(
            "ElastiCache/Redis (or related) configuration lacks explicit customer-managed KMS for encryption at rest per Fortify structural rule."
        )
        plan.extend(
            [
                "1) Set replication group `kms_key_id` / at-rest encryption per AWS provider schema.",
                "2) Validate KMS key policy for ElastiCache/SNS as required.",
                "3) Roll out through pipeline.",
            ]
        )
        val.extend(["tf validate/plan", "AWS console spot-check encryption"])
        accept.extend(["At-rest encryption uses organization CMK where required"])

    elif "improper ecr access" in cat_lower:
        complexity = "LOW"
        rc.append(
            "ECR repository policy/tag mutability settings may allow tag overwrite or overly broad pull/push; Fortify flags mutable tags by default."
        )
        plan.extend(
            [
                "1) Set `image_tag_mutability = \"IMMUTABLE\"` where compatible with release process.",
                "2) Tighten IAM/repo policies to least privilege.",
            ]
        )
        val.extend(["ECR settings review", "Pipeline still pushes tags successfully"])
        accept.extend(["Immutable tags for prod images or documented exception"])

    elif "improper eks network" in cat_lower or (
        "eks" in cat_lower and "network access" in cat_lower
    ):
        owner = "H_REQ"
        complexity = "HIGH"
        rc.append(
            "EKS API endpoint may allow public access (`endpoint_public_access`); MIDAS is private-by-default — cluster endpoint posture must match architecture."
        )
        plan.extend(
            [
                "1) Set private-only API endpoint access consistent with VPC design; restrict public if any.",
                "2) Pair with security group and CIDR rules from approved sources only.",
                "3) Validate kubectl/CI access paths still work (private endpoints, VPN, CI agents).",
            ]
        )
        val.extend(["EKS endpoint configuration review", "Network reachability test from approved CIDRs"])
        accept.extend(["Cluster endpoint aligned with private-by-default policy"])

    elif "insecure ec2 storage" in cat_lower:
        complexity = "LOW"
        rc.append("EC2/AMI block device or volume lacks encryption-at-rest flag.")
        plan.extend(
            [
                "1) Set `encrypted = true` on relevant `ebs_block_device` / volumes.",
                "2) Use CMK if policy requires customer-managed keys.",
            ]
        )
        val.extend(["tf plan", "AMI/volume encryption verified"])
        accept.extend(["Volumes encrypted at rest"])

    elif "insecure ecr storage" in cat_lower:
        complexity = "LOW"
        rc.append("ECR repo lacks explicit encryption configuration in Terraform per Fortify.")
        plan.extend(
            [
                "1) Add `encryption_configuration` (AES256 or KMS) on `aws_ecr_repository`.",
            ]
        )
        val.extend(["tf plan", "ECR console encryption summary"])
        accept.extend(["ECR images encrypted at rest"])

    elif "insecure eks storage" in cat_lower:
        complexity = "MID"
        rc.append("EKS cluster secrets encryption (`encryption_config` / KMS key) missing or incomplete.")
        plan.extend(
            [
                "1) Configure `encryption_config` with KMS `key_arn` for etcd secrets.",
                "2) Ensure KMS permissions for EKS service-linked role.",
            ]
        )
        val.extend(["tf plan", "EKS cluster details show secrets encryption"])
        accept.extend(["etcd secrets encrypted with approved KMS key"])

    elif "insufficient ec2 logging" in cat_lower:
        complexity = "LOW"
        rc.append("EC2 instance monitoring/detailed monitoring or audit posture flagged as insufficient.")
        plan.extend(
            [
                "1) Enable detailed monitoring where required.",
                "2) Ensure OS/agent logs ship to CloudWatch per observability standard.",
            ]
        )
        val.extend(["CloudWatch agent/config review"])
        accept.extend(["Monitoring meets ops baseline"])

    elif "insufficient rds backup" in cat_lower:
        complexity = "LOW"
        rc.append("RDS `backup_retention_period` is zero or missing automated backups.")
        plan.extend(
            [
                "1) Set non-zero `backup_retention_period` per RPO.",
                "2) Validate maintenance window and snapshot exports if needed.",
            ]
        )
        val.extend(["RDS backup settings in tf", "Restore drill optional"])
        accept.extend(["Automated backups enabled with agreed retention"])

    elif "insufficient rds monitoring" in cat_lower:
        complexity = "LOW"
        rc.append("RDS lacks CloudWatch log exports or enhanced monitoring per Fortify rule.")
        plan.extend(
            [
                "1) Enable `enabled_cloudwatch_logs_exports` for needed log types.",
                "2) Enable Enhanced Monitoring if required by policy.",
            ]
        )
        val.extend(["CW logs present for RDS", "Metrics/alarm spot-check"])
        accept.extend(["Audit logs available per compliance need"])

    elif "rds auto-upgrade disabled" in cat_lower or (
        "auto-upgrade" in cat_lower and "rds" in cat_lower
    ):
        complexity = "LOW"
        rc.append("`auto_minor_version_upgrade` set false — delays minor security patches.")
        plan.extend(
            [
                "1) Set `auto_minor_version_upgrade = true` unless documented exception.",
                "2) Schedule maintenance windows with DBA.",
            ]
        )
        val.extend(["tf plan", "RDS modify window"])
        accept.extend(["Auto minor upgrades enabled or formal exception recorded"])

    elif "reduced elb availability" in cat_lower or "elb availability" in cat_lower:
        complexity = "MID"
        rc.append(
            "ELB/ALB resilience setting flagged (e.g. deletion protection off, scheme, or cross-zone)."
        )
        plan.extend(
            [
                "1) Enable deletion protection for prod LBs where required.",
                "2) Confirm multi-AZ / cross-zone settings meet HA baseline.",
            ]
        )
        val.extend(["tf plan", "LB attributes in console"])
        accept.extend(["Availability controls match HA requirement"])

    elif "aws terraform" in cat_lower:
        complexity = "MID"
        rc.append(
            f"Fortify AWS Terraform rulepack: {cat.split(':')[-1].strip() if ':' in cat else cat}; align resource attributes with secure baseline."
        )
        plan.extend(
            [
                "1) Map finding to exact Terraform resource in cited file/line.",
                "2) Apply Fortify recommendation + org cloud baseline.",
                "3) Deploy through MIDAS Jenkins; capture plan output in PR.",
            ]
        )
        val.extend(["Checkov/tf validate optional", "Fortify delta on scope"])
        accept.extend(["Specific insecure attributes remediated or risk accepted with ISG"])

    else:
        complexity = "MID"
        rc.append(
            f"Fortify ({priority}): {cat}; validate sink `{sink_path or src_path}` against current branch."
        )
        plan.extend(
            [
                "1) Read cited sink/source in repo.",
                "2) Implement Fortify `recommendation` with minimal blast radius.",
                "3) Retest / rescan.",
            ]
        )
        val.extend(["Targeted test or IaC plan", "Fortify rescan"])
        accept.extend(["Finding cleared or documented exception"])

    row["issue_scope_summary"] = _scope(cat, sink_path, src_path, work_kind)

    if not rc:
        rc.append(f"Fortify category `{cat}` at `{sink_path or src_path}`.")
    if not plan:
        plan.append("1) Review Fortify abstract/recommendation against repo.")
    if not val:
        val.append("Fortify rescan on changed paths")
    if not accept:
        accept.append("Observable remediation per ISG")

    ph, pc, py = _hours(priority, owner, complexity)
    row["root_cause"] = " ".join(rc)
    row["remediation_plan"] = " ".join(plan)
    row["validation"] = "; ".join(val)
    row["acceptance_criteria"] = "; ".join(accept)
    row["resolution_owner"] = owner
    row["complexity"] = complexity
    row["human_fix_hours"] = ph
    row["cursor_fix_hours"] = pc
    row["hybrid_fix_hours"] = py

    md = "\n".join(
        [
            f"# Analysis log — {obv}",
            "",
            f"- **analysis_id:** `{aid}`",
            f"- **Fortify priority:** {priority}",
            f"- **Category:** {cat}",
            f"- **Sink:** `{sink_path}` line {row.get('sink_line')}",
            f"- **Source:** `{src_path}` line {row.get('source_line')}",
            "",
            "## Summary",
            row["root_cause"],
            "",
            "## Plan",
            row["remediation_plan"],
            "",
            "## Validation",
            row["validation"],
            "",
            "## Notes",
            "- Batch Phase 2 routing by category + path; confirm line-level accuracy before closure.",
            "- Shared env changes: Jenkins pipeline only per MIDAS policy.",
            "",
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

    updated = 0
    skipped_has_id = 0
    skipped_priority = 0
    logs: dict[str, str] = {}
    out_rows: list[dict[str, str]] = []

    for row in rows:
        pr = (row.get("fortify_priority") or "").strip()
        existing = (row.get("analysis_id") or "").strip()
        if pr not in TARGET_PRIORITIES:
            out_rows.append(row)
            skipped_priority += 1
            continue
        if existing:
            out_rows.append(row)
            skipped_has_id += 1
            continue
        new_row, md = _fill(dict(row))
        out_rows.append(new_row)
        logs[new_row["analysis_id"]] = md
        updated += 1

    for aid, body in logs.items():
        (LOG_DIR / f"{aid}.md").write_text(body, encoding="utf-8")

    tmp = CSV_IN.with_suffix(".csv.tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        w.writeheader()
        w.writerows(out_rows)
    tmp.replace(CSV_IN)

    msg = (
        f"repo={REPO}\n"
        f"csv={CSV_IN}\n"
        f"updated_hml_rows={updated}\n"
        f"skipped_already_had_analysis_id={skipped_has_id}\n"
        f"skipped_not_hml_priority={skipped_priority}\n"
        f"logs_written={len(logs)}\n"
        f"logs_dir={LOG_DIR}\n"
    )
    RUN_LOG.write_text(msg, encoding="utf-8")
    print(msg, end="")


if __name__ == "__main__":
    main()
