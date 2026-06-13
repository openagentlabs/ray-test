"""Grouping and JIRA ticket generation logic.

Input: parsed rows from all four scan sources (Fortify workbook CSV,
container_images CSV, iac CSV, oss_packages CSV).

Output:
  - list[ConsolidatedFinding]  — one entry per original finding row
  - list[JiraTicket]           — one entry per Bug (grouped or residual)
  - dict[str, str]             — finding_id → bug_id back-fill mapping
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from isg_jira_ticket_gen.ticket_schema import (
    ComplexityLevel,
    ConsolidatedFinding,
    EffortEstimate,
    JiraPriority,
    JiraTicket,
    OwnerTeam,
    ParentGroup,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Fortify categories that require per-site individual bugs (residuals)
RESIDUAL_CATEGORIES = {
    "Command Injection",
    "SQL Injection",
    "LDAP Injection",
    "Path Manipulation",
    "Hardcoded Password",
    "Password Management: Hardcoded Password",
    "Key Management: Hardcoded Encryption Key",
    "Hardcoded API Key",
    "DOM XSS",
    "Cross-Site Scripting: DOM",
    "Cross-Site Scripting: Reflected",
    "Unsafe Deserialization",
    "Object Injection",
    "Server-Side Request Forgery",
    "SSRF",
}

# Max severity ordering for aggregation
_SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "": 4}


def _max_severity(*sevs: str) -> str:
    return min(sevs, key=lambda s: _SEV_ORDER.get(s.upper(), 99))


def _fortify_priority_to_severity(p: str) -> str:
    return {"Critical": "CRITICAL", "High": "HIGH", "Medium": "MEDIUM", "Low": "LOW"}.get(p, "LOW")


def _severity_to_jira_priority(s: str) -> JiraPriority:
    return {"CRITICAL": "Critical", "HIGH": "High", "MEDIUM": "Medium", "LOW": "Low"}.get(
        s.upper(), "Low"
    )


def _effort(count: int, complexity: ComplexityLevel) -> EffortEstimate:
    if complexity in ("HIGH", "MAX"):
        return "L"
    if count <= 5 and complexity in ("LOW", "MID"):
        return "S"
    if count <= 30:
        return "M"
    return "L"


def _complexity_from_counts(count: int) -> ComplexityLevel:
    if count >= 30:
        return "HIGH"
    if count >= 6:
        return "MID"
    return "LOW"


def _normalise_path(raw: str) -> str:
    """Strip the Jenkins workspace prefix and trailing annotation from a path string.

    The raw format is:
      /bu-analytics-gen-ai-midas-deployment-<hash>/actual/path/Dockerfile (base-image lines:N-N (sha256:...))

    After stripping the workspace prefix the result is:
      actual/path/Dockerfile (base-image lines:N-N (sha256:...))

    We then strip everything from the first ' (' onward to get the clean file path.
    """
    cleaned = re.sub(r"^/bu-analytics-gen-ai-midas-deployment-[^/]+/", "", raw)
    # Strip the trailing annotation that starts with ' (' (base image info, line numbers, sha)
    cleaned = re.sub(r"\s+\(.*$", "", cleaned).strip()
    return cleaned


def _extract_dockerfile_context(path_raw: str) -> str:
    """Return a short label for grouping container CVEs, e.g. 'nginx:1.25-alpine'."""
    m = re.search(r"\(([^)]+lines:)", path_raw)
    if m:
        # e.g. "nginx:1.25-alpine lines:55-55 (sha256:11cedc39e6)"
        inner = m.group(1).split(" lines:")[0].strip()
        return inner
    # Fall back: extract Dockerfile name from path
    parts = _normalise_path(path_raw).split("/")
    for p in reversed(parts):
        if "dockerfile" in p.lower():
            return p
    return "unknown"


# ---------------------------------------------------------------------------
# Loader helpers
# ---------------------------------------------------------------------------

def load_fortify_rows(csv_path: str) -> list[dict[str, Any]]:
    import csv as _csv
    with open(csv_path, newline="", encoding="utf-8") as fh:
        return list(_csv.DictReader(fh))


def load_supplementary_rows(csv_path: str) -> list[dict[str, Any]]:
    import csv as _csv
    with open(csv_path, newline="", encoding="utf-8") as fh:
        return list(_csv.DictReader(fh))


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def _normalise_fortify(rows: list[dict[str, Any]]) -> list[ConsolidatedFinding]:
    out = []
    for r in rows:
        out.append(ConsolidatedFinding(
            finding_id=r.get("obv_id", ""),
            source="fortify",
            severity=_fortify_priority_to_severity(r.get("fortify_priority", "")),
            category_or_policy=r.get("category", ""),
            file_or_resource=r.get("sink_file", "") or r.get("source_file", ""),
            vulnerability_or_policy_id=r.get("obv_id", ""),
            description=r.get("abstract", ""),
            fix_version_or_recommendation=r.get("recommendation", ""),
        ))
    return out


def _normalise_cve(rows: list[dict[str, Any]], source: str) -> list[ConsolidatedFinding]:
    out = []
    for r in rows:
        norm_path = _normalise_path(r.get("Path", ""))
        # Include the normalised path in the finding_id so the same CVE appearing
        # in multiple Dockerfiles (or requirements files) gets a distinct row ID.
        path_slug = norm_path.replace("/", "_").replace(".", "_")
        out.append(ConsolidatedFinding(
            finding_id=f"{source.upper()}-{r.get('Vulnerability', 'UNK')}-{r.get('Package', '')}-{path_slug}",
            source=source,  # type: ignore[arg-type]
            severity=(r.get("Severity") or "").upper(),
            category_or_policy=r.get("Package", ""),
            file_or_resource=norm_path,
            vulnerability_or_policy_id=r.get("Vulnerability", ""),
            description=(r.get("Description", "") or "")[:300],
            fix_version_or_recommendation=r.get("Fix Version", ""),
        ))
    return out


def _normalise_iac(rows: list[dict[str, Any]]) -> list[ConsolidatedFinding]:
    out = []
    for r in rows:
        policy = (r.get("Misconfigurations") or "").strip()
        if not policy:
            continue  # skip informational/pass rows
        norm_path = _normalise_path(r.get("Path", ""))
        path_slug = norm_path.replace("/", "_").replace(".", "_")
        resource = r.get("Resource", "")
        out.append(ConsolidatedFinding(
            finding_id=f"IAC-{policy}-{resource}-{path_slug}",
            source="iac",
            severity=(r.get("Severity") or "").upper(),
            category_or_policy=resource,  # carry resource name for ticket generation
            file_or_resource=norm_path,
            vulnerability_or_policy_id=policy,
            description=r.get("Policy title", ""),
            fix_version_or_recommendation=r.get("Guideline", ""),
        ))
    return out


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def _group_container(
    findings: list[ConsolidatedFinding],
    ticket_counter: list[int],
) -> tuple[list[JiraTicket], dict[str, str]]:
    # Group by the full normalised path (e.g. "frontend/Dockerfile",
    # "backend/Dockerfile", "deploy/ecs-app/docker/midas-api-backend-svc/Dockerfile").
    # Using only the filename part previously collapsed distinct Dockerfiles with the
    # same name into a single bucket.
    groups: dict[str, list[ConsolidatedFinding]] = defaultdict(list)
    for f in findings:
        key = f.file_or_resource if f.file_or_resource else "unknown"
        groups[key].append(f)

    tickets: list[JiraTicket] = []
    mapping: dict[str, str] = {}

    for dockerfile_path, group_findings in sorted(groups.items(), key=lambda x: -len(x[1])):
        ticket_counter[0] += 1
        tid = f"BUG-{ticket_counter[0]:03d}"
        count = len(group_findings)
        max_sev = _max_severity(*[f.severity for f in group_findings])
        complexity = _complexity_from_counts(count)

        # Short label for titles/labels: just the filename + parent dir
        path_parts = dockerfile_path.replace("\\", "/").split("/")
        short_label = "/".join(path_parts[-2:]) if len(path_parts) >= 2 else dockerfile_path

        # Unique CVE IDs
        cve_ids = sorted({f.vulnerability_or_policy_id for f in group_findings})
        # Unique packages
        packages = sorted({f.category_or_policy for f in group_findings})

        finding_ids_sorted = sorted({f.finding_id for f in group_findings})
        ticket = JiraTicket(
            ticket_id=tid,
            parent_group="CONTAINER_CVE",
            title=f"Refresh base image in {short_label} — {count} CVE(s) cleared",
            priority=_severity_to_jira_priority(max_sev),
            owner_team="DevOps",
            effort_estimate=_effort(count, complexity),
            complexity=complexity,
            root_cause=(
                f"{count} CVE(s) in {len(packages)} package(s) "
                f"({', '.join(packages[:5])}{'...' if len(packages) > 5 else ''}) "
                f"present in the base image used by {dockerfile_path}. "
                f"Upgrading to a patched base image or bumping packages clears all findings."
            ),
            files_to_change=dockerfile_path,
            findings_cleared_count=count,
            findings_cleared_ids=", ".join(cve_ids[:30]) + (f" ... +{len(cve_ids)-30} more" if len(cve_ids) > 30 else ""),
            risk=(
                "Base-image upgrade may introduce breaking changes in system libraries. "
                "Run full integration tests after upgrade. Pin to a specific digest after validation."
            ),
            validation_steps=(
                f"1. Update the base image in {dockerfile_path}.\n"
                "2. Rebuild the Docker image.\n"
                "3. Re-run the ISG container image scan.\n"
                "4. Confirm CVE count for this Dockerfile drops to zero for the listed findings.\n"
                "5. Run smoke tests for the affected service."
            ),
            is_grouped=True,
            labels=f"container-cve,{short_label.lower().replace('/', '-')},{max_sev.lower()}",
            consolidated_finding_ids=", ".join(finding_ids_sorted),
        )
        tickets.append(ticket)
        for f in group_findings:
            mapping[f.finding_id] = tid

    return tickets, mapping


def _group_oss(
    findings: list[ConsolidatedFinding],
    ticket_counter: list[int],
) -> tuple[list[JiraTicket], dict[str, str]]:
    groups: dict[str, list[ConsolidatedFinding]] = defaultdict(list)
    for f in findings:
        groups[f.category_or_policy].append(f)

    tickets: list[JiraTicket] = []
    mapping: dict[str, str] = {}

    for package, group_findings in sorted(groups.items(), key=lambda x: -len(x[1])):
        ticket_counter[0] += 1
        tid = f"BUG-{ticket_counter[0]:03d}"
        count = len(group_findings)
        max_sev = _max_severity(*[f.severity for f in group_findings])
        complexity = _complexity_from_counts(count)

        cve_ids = sorted({f.vulnerability_or_policy_id for f in group_findings})
        files = sorted({f.file_or_resource for f in group_findings})
        fix_versions = sorted({f.fix_version_or_recommendation for f in group_findings if f.fix_version_or_recommendation})
        finding_ids_sorted = sorted({f.finding_id for f in group_findings})

        fix_hint = f"Upgrade to {fix_versions[0]}" if fix_versions else "Upgrade to the latest patched version"

        ticket = JiraTicket(
            ticket_id=tid,
            parent_group="OSS_CVE",
            title=f"Upgrade {package} — {count} CVE(s) cleared",
            priority=_severity_to_jira_priority(max_sev),
            owner_team="Software",
            effort_estimate=_effort(count, complexity),
            complexity=complexity,
            root_cause=(
                f"{package} has {count} known CVE(s). {fix_hint} in all affected dependency files."
            ),
            files_to_change="\n".join(files),
            findings_cleared_count=count,
            findings_cleared_ids=", ".join(cve_ids),
            risk=(
                f"Upgrading {package} may introduce API incompatibilities. "
                "Run unit and integration test suites after the bump."
            ),
            validation_steps=(
                f"1. Update {package} version in requirements.txt / package.json.\n"
                "2. Run `pip install -r requirements.txt` or `npm install` and verify no errors.\n"
                "3. Re-run the ISG OSS package scan.\n"
                "4. Confirm the listed CVEs no longer appear for this package."
            ),
            is_grouped=True,
            labels=f"oss-cve,{package.lower().replace(' ','-')},{max_sev.lower()}",
            consolidated_finding_ids=", ".join(finding_ids_sorted),
        )
        tickets.append(ticket)
        for f in group_findings:
            mapping[f.finding_id] = tid

    return tickets, mapping


def _group_iac(
    findings: list[ConsolidatedFinding],
    ticket_counter: list[int],
) -> tuple[list[JiraTicket], dict[str, str]]:
    groups: dict[str, list[ConsolidatedFinding]] = defaultdict(list)
    for f in findings:
        groups[f.vulnerability_or_policy_id].append(f)

    tickets: list[JiraTicket] = []
    mapping: dict[str, str] = {}

    for policy, group_findings in sorted(groups.items(), key=lambda x: -len(x[1])):
        ticket_counter[0] += 1
        tid = f"BUG-{ticket_counter[0]:03d}"
        count = len(group_findings)
        max_sev = _max_severity(*[f.severity for f in group_findings])
        complexity = _complexity_from_counts(count)

        policy_title = group_findings[0].description if group_findings else policy
        guideline = group_findings[0].fix_version_or_recommendation if group_findings else ""
        files = sorted({f.file_or_resource for f in group_findings})
        # category_or_policy carries the raw Resource name for IaC rows
        resource_names = sorted({f.category_or_policy for f in group_findings if f.category_or_policy})
        finding_ids_sorted = sorted({f.finding_id for f in group_findings})

        # findings_cleared_ids: list all resource names so auditors can trace back
        resource_id_list = ", ".join(resource_names[:30])
        if len(resource_names) > 30:
            resource_id_list += f" ... +{len(resource_names)-30} more"

        ticket = JiraTicket(
            ticket_id=tid,
            parent_group="IAC_POLICY",
            title=f"Fix {policy}: {policy_title[:80]}",
            priority=_severity_to_jira_priority(max_sev),
            owner_team="DevOps",
            effort_estimate=_effort(count, complexity),
            complexity=complexity,
            root_cause=(
                f"{count} resource(s) violate Checkov policy {policy} ({policy_title}). "
                f"Affected resources: {', '.join(resource_names[:5])}{'...' if len(resource_names) > 5 else ''}."
            ),
            files_to_change="\n".join(files[:15]),
            findings_cleared_count=count,
            findings_cleared_ids=resource_id_list,
            risk=(
                "Terraform attribute changes may affect running infrastructure. "
                "Run `terraform plan` and review the diff before applying."
            ),
            validation_steps=(
                f"1. Update the Terraform/Helm resources listed above to satisfy {policy}.\n"
                "2. Run `terraform plan` — confirm no unintended changes.\n"
                f"3. Re-run Checkov: `checkov -d deploy/ --check {policy}`.\n"
                "4. Confirm 0 violations for this policy.\n"
                f"5. Reference: {guideline}"
            ),
            is_grouped=True,
            labels=f"iac,checkov,{policy.lower()},{max_sev.lower()}",
            consolidated_finding_ids=", ".join(finding_ids_sorted),
        )
        tickets.append(ticket)
        for f in group_findings:
            mapping[f.finding_id] = tid

    return tickets, mapping


def _group_fortify(
    fortify_rows: list[dict[str, Any]],
    findings: list[ConsolidatedFinding],
    ticket_counter: list[int],
) -> tuple[list[JiraTicket], dict[str, str]]:
    """Group Fortify findings. Residual categories get individual tickets."""
    grouped: dict[str, list[tuple[dict[str, Any], ConsolidatedFinding]]] = defaultdict(list)
    residuals: list[tuple[dict[str, Any], ConsolidatedFinding]] = []

    row_by_obv: dict[str, dict[str, Any]] = {r["obv_id"]: r for r in fortify_rows}

    for f in findings:
        raw = row_by_obv.get(f.finding_id, {})
        cat = raw.get("category", f.category_or_policy)
        if any(res_cat.lower() in cat.lower() for res_cat in RESIDUAL_CATEGORIES):
            residuals.append((raw, f))
        else:
            grouped[cat].append((raw, f))

    tickets: list[JiraTicket] = []
    mapping: dict[str, str] = {}

    # Grouped tickets
    for category, pairs in sorted(grouped.items(), key=lambda x: -len(x[1])):
        ticket_counter[0] += 1
        tid = f"BUG-{ticket_counter[0]:03d}"
        count = len(pairs)
        sevs = [_fortify_priority_to_severity(p[0].get("fortify_priority", "Low")) for p in pairs]
        max_sev = _max_severity(*sevs)
        complexity = _complexity_from_counts(count)

        all_files = sorted({
            f for f in (
                p[0].get("sink_file", "") or p[0].get("source_file", "") for p in pairs if p[0]
            ) if f  # exclude empty strings that cause leading newlines
        })
        obv_ids = sorted({p[1].finding_id for p in pairs})
        remediation = pairs[0][0].get("remediation_plan", "") or pairs[0][0].get("recommendation", "")

        ticket = JiraTicket(
            ticket_id=tid,
            parent_group="FORTIFY_CODE",
            title=f"[Fortify] Fix {category} — {count} finding(s)",
            priority=_severity_to_jira_priority(max_sev),
            owner_team=_infer_owner(all_files, category),
            effort_estimate=_effort(count, complexity),
            complexity=complexity,
            root_cause=(
                pairs[0][0].get("root_cause", "")
                or pairs[0][0].get("abstract", "")
                or f"{count} finding(s) of category '{category}'."
            ),
            files_to_change="\n".join(all_files[:15]),
            findings_cleared_count=count,
            findings_cleared_ids=", ".join(obv_ids),
            risk=(
                "Code changes may affect application behaviour. "
                "Run unit tests and integration tests after remediation."
            ),
            validation_steps=(
                remediation or (
                    "1. Apply the fix to each listed file.\n"
                    "2. Re-run the Fortify scan.\n"
                    "3. Confirm finding count for this category drops to zero."
                )
            ),
            is_grouped=True,
            labels=f"fortify,{category.lower().replace(' ','-').replace(':','')}",
            consolidated_finding_ids=", ".join(obv_ids),
        )
        tickets.append(ticket)
        for _, f in pairs:
            mapping[f.finding_id] = tid

    # Residual tickets — one per (category, sink_file) pair, not one per finding.
    # Multiple findings in the same file for the same category are a single fix task.
    residual_groups: dict[tuple[str, str], list[tuple[dict[str, Any], ConsolidatedFinding]]] = defaultdict(list)
    for raw, f in residuals:
        cat = raw.get("category", f.category_or_policy)
        sink_file = raw.get("sink_file", "") or raw.get("source_file", "")
        residual_groups[(cat, sink_file)].append((raw, f))

    for (cat, sink_file), group_pairs in sorted(
        residual_groups.items(), key=lambda x: (-len(x[1]), x[0])
    ):
        ticket_counter[0] += 1
        tid = f"BUG-{ticket_counter[0]:03d}"
        count = len(group_pairs)

        # Use the highest severity across all findings in this group
        sevs = [_fortify_priority_to_severity(p[0].get("fortify_priority", "Low")) for p in group_pairs]
        max_sev = _max_severity(*sevs)

        # Collect all sink lines for traceability
        sink_lines = [
            p[0].get("sink_line", "") or p[0].get("source_line", "")
            for p in group_pairs
        ]
        sink_lines_str = ", ".join(l for l in sink_lines if l)

        # Use the most detailed root_cause / remediation_plan from the group
        representative_raw = next(
            (p[0] for p in group_pairs if p[0].get("root_cause")),
            group_pairs[0][0],
        )

        file_label = sink_file if sink_file else "unknown"
        if len(file_label) > 60:
            file_label = "..." + file_label[-57:]

        obv_ids = sorted({p[1].finding_id for p in group_pairs})
        files_to_change = (
            f"{sink_file} (lines: {sink_lines_str})" if sink_file and sink_lines_str
            else sink_file or ""
        )

        ticket = JiraTicket(
            ticket_id=tid,
            parent_group="RESIDUAL",
            title=f"[Fortify] {cat} — {file_label}" + (f" ({count} sites)" if count > 1 else ""),
            priority=_severity_to_jira_priority(max_sev),
            owner_team=_infer_owner([sink_file], cat),
            effort_estimate=_effort(count, "MID"),
            complexity="MID",
            root_cause=representative_raw.get("root_cause", "") or representative_raw.get("abstract", ""),
            files_to_change=files_to_change,
            findings_cleared_count=count,
            findings_cleared_ids=", ".join(obv_ids),
            risk="Per-file code change; review carefully for logic side-effects.",
            validation_steps=(
                representative_raw.get("remediation_plan", "")
                or representative_raw.get("recommendation", "")
                or (
                    f"1. Fix all {count} site(s) in {sink_file}.\n"
                    "2. Re-run the Fortify scan.\n"
                    f"3. Confirm {', '.join(obv_ids)} no longer appear."
                )
            ),
            is_grouped=count > 1,
            residual_file_line=sink_file if sink_file else "",
            labels=f"fortify,residual,{cat.lower().replace(' ','-').replace(':','')}",
            consolidated_finding_ids=", ".join(obv_ids),
        )
        tickets.append(ticket)
        for _, f in group_pairs:
            mapping[f.finding_id] = tid

    return tickets, mapping


def _infer_owner(files: list[str], category: str) -> OwnerTeam:
    iac_exts = {".tf", ".tfvars", ".yaml", ".yml", ".json"}
    iac_paths = {"deploy/", "infra/", "helm/", "ai_gateway/"}
    for f in files:
        if not f:
            continue
        fl = f.lower()
        if any(fl.endswith(ext) for ext in iac_exts):
            return "DevOps"
        if any(p in fl for p in iac_paths):
            return "DevOps"
    cat_lower = category.lower()
    devops_keywords = {
        "encryption key", "ecr", "eks", "ec2", "rds", "elb", "elasticache",
        "cloudwatch", "s3", "kms", "iam", "vpc", "logging", "monitoring",
        "backup", "network", "storage",
    }
    if any(k in cat_lower for k in devops_keywords):
        return "DevOps"
    return "Software"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_tickets(
    fortify_csv: str,
    container_csv: str | None,
    iac_csv: str | None,
    oss_csv: str | None,
) -> tuple[list[ConsolidatedFinding], list[JiraTicket], dict[str, str]]:
    """Load all sources, group, generate tickets, and return the three outputs.

    Returns:
        all_findings   — normalised ConsolidatedFinding objects (one per row)
        all_tickets    — JiraTicket objects (grouped + residual)
        bug_id_map     — finding_id → ticket_id mapping for back-fill
    """
    fortify_rows = load_fortify_rows(fortify_csv)

    all_findings: list[ConsolidatedFinding] = _normalise_fortify(fortify_rows)
    container_rows: list[dict] = load_supplementary_rows(container_csv) if container_csv else []
    iac_rows: list[dict] = load_supplementary_rows(iac_csv) if iac_csv else []
    oss_rows: list[dict] = load_supplementary_rows(oss_csv) if oss_csv else []

    container_findings = _normalise_cve(container_rows, "container")
    oss_findings = _normalise_cve(oss_rows, "oss")
    iac_findings = _normalise_iac(iac_rows)

    all_findings = (
        _normalise_fortify(fortify_rows)
        + container_findings
        + iac_findings
        + oss_findings
    )

    counter = [0]
    all_tickets: list[JiraTicket] = []
    bug_id_map: dict[str, str] = {}

    # Container CVEs
    t, m = _group_container(container_findings, counter)
    all_tickets.extend(t)
    bug_id_map.update(m)

    # OSS CVEs
    t, m = _group_oss(oss_findings, counter)
    all_tickets.extend(t)
    bug_id_map.update(m)

    # IaC
    t, m = _group_iac(iac_findings, counter)
    all_tickets.extend(t)
    bug_id_map.update(m)

    # Fortify (grouped + residuals)
    t, m = _group_fortify(fortify_rows, _normalise_fortify(fortify_rows), counter)
    all_tickets.extend(t)
    bug_id_map.update(m)

    # Back-fill bug_id into consolidated findings
    for f in all_findings:
        f.bug_id = bug_id_map.get(f.finding_id, "")

    return all_findings, all_tickets, bug_id_map
