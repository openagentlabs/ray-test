"""Human + machine-readable tool cards for Cursor agents and operators."""

from __future__ import annotations

from typing import Any, Dict

from fortify_workbook_tool.input_models import SimpleFileJobConfig, StructuredJobConfig


TOOL_CARD_MARKDOWN = """\
# Fortify Developer Workbook Extract

## What it does
Extracts every Fortify finding from an Open Text **Fortify Audit Workbench Developer Workbook** PDF
(text under **Results Outline**) into structured rows (internal model), then serializes to **CSV**, **JSON**, or **YAML**.

## When to use
- After ISG / AppSec shares a Developer Workbook PDF — convert it to CSV/JSON/YAML for remediation tracking.
- From Cursor — drive the tool via **JSON config** so agents pass strict paths and output shapes.

## How it runs (pipeline)
1. **PdfLoader** — extract plain text from the PDF.
2. **WorkbookParser** — parse Results Outline → canonical **FortifyIssue** rows (one per `Kingdom:` block).
3. **Formatter** — write **CSV** / **JSON** / **YAML** using pluggable **IssueSinkFormatter** classes.

## Invocation — no arguments
```bash
# uv (recommended — uses pyproject.toml / lockfile in this directory)
uv run --project .cursor/tools/fortify_workbook_extract parse-isg-code-scan-report-tool

python3 parse_isg_code_scan_report_tool.py
# or
python3 -m fortify_workbook_tool
```
(`parse_isg_code_scan_report.py` remains as a thin shim for older scripts.)

Prints this tool card (markdown on stdout).

## Flags (CLI)

| Flag | Purpose |
|------|---------|
| *(none)* | Print tool card (markdown). |
| `--app-config PATH` | Load `app_config.toml` from this path (overrides `FORTIFY_WORKBOOK_APP_CONFIG`). |
| `--tool-card-json` | Print **machine-readable** descriptor + JSON Schema snippets (stdout). Use for agents. |
| `--json-config PATH` | Read job definition JSON from `PATH`. Use `-` for **stdin**. |
| `--pdf PATH` | Input Developer Workbook PDF (legacy / quick runs). |
| `--output PATH` | Output file path (alias: `--csv` for backward compatibility). |
| `--format {csv,json,yaml}` | Output encoding (default from `app_config.toml` `output.default_format` when using `--pdf`). |
| `--no-normalize-paths` | Keep raw `File:` paths (no repo-prefix stripping). |
| `--fail-on-warnings` | Exit **2** if loader/parser emitted warnings. |
| `--final-report PATH` | After a successful run, write a Markdown **final report** (paths, priority counts, **CSV column list**). |
| `--print-csv-fields` | Print `FortifyIssue` CSV column names (one per line) and exit (no PDF needed). |

## JSON job types (schemas from `--tool-card-json`)

### A) Structured job — nested `output` object
Use when you want **optional field projection** (`issue_field_subset`), optional **priority_summary**, or stdout output (`output.path` omitted → writes formatted payload to stdout).

Minimal shape:
```json
{
  "schema_version": "1",
  "job_type": "structured",
  "pdf_path": "/abs/path/DeveloperWorkbook.pdf",
  "normalize_paths": true,
  "fail_on_warnings": false,
  "output": {
    "format": "json",
    "path": "/tmp/issues.json",
    "include_priority_summary": true,
    "issue_field_subset": null
  }
}
```

### B) Simple file job — flat output path + format
Use when you only need **pdf_path**, **output_path**, and **output_format** (csv/json/yaml).

```json
{
  "schema_version": "1",
  "job_type": "simple_file",
  "pdf_path": "/abs/path/DeveloperWorkbook.pdf",
  "output_path": "/tmp/out.csv",
  "output_format": "csv",
  "normalize_paths": true,
  "fail_on_warnings": false
}
```

### Wrapper envelope (optional)
```json
{ "job": { ...same as A or B... } }
```

## Output JSON payload shape (json/yaml formatters)
Top-level keys: `schema_version` (formatter metadata **1.3**), `format`, `source_pdf`, `warnings`, `priority_summary`, `issues` (array of FortifyIssue-shaped objects).

## CSV columns (schema 1.3)
First column: **`obv_id`** (`OBV0001`, `OBV0002`, …). After Fortify PDF fields come optional analysis and remediation placeholders (filled during triage/fix). Extract defaults: analysis columns empty; **`issue_state`** defaults to **`OPEN`**; remaining remediation columns empty until updated.

| Column | Purpose |
|--------|---------|
| `analysis_id` | UUID for the analysis run for this row. |
| `analysis_log_file` | Repo-relative path to the markdown log, typically `.cursor/scratch/analysis_log/<analysis_id>.md`. |
| `resolution_owner` | `AI_AGENT` or `H_REQ` — see skill `jp_isg_code_scan_results_analyzer_helper`. |
| `complexity` | `MAX`, `HIGH`, `MID`, or `LOW`. |
| `human_fix_hours` | Integer hours (string), human-led estimate. |
| `cursor_fix_hours` | Integer hours (string), Cursor-only estimate. |
| `hybrid_fix_hours` | Integer hours (string), hybrid (agent + human checkpoints). |
| `issue_scope_summary` | Concise: finding, paths, artifact types. |
| `root_cause` | Root cause analysis text. |
| `remediation_plan` | Planned remediation steps. |
| `validation` | How the fix was / will be validated. |
| `acceptance_criteria` | Testable acceptance criteria. |
| `issue_resolve_progress` | Progress notes or percent/state detail. |
| `resolved_date` | Resolution date (ISO string recommended). |
| `working_log` | Short log pointer or notes (e.g. link to analysis log). |
| `issue_state` | Workflow state; extract default **`OPEN`**. |

## Dependencies
`pip install -r .cursor/tools/fortify_workbook_extract/requirements-workbook-tools.txt`
"""


def tool_descriptor_json() -> Dict[str, Any]:
    """Structured descriptor for Cursor skills / automation (schemas + exit codes)."""
    return {
        "tool_id": "parse_isg_code_scan_report_tool",
        "display_name": "Fortify Developer Workbook Extract",
        "cli_module": "fortify_workbook_tool.cli",
        "entry_points": [
            "python3 -m fortify_workbook_tool",
            "python3 parse_isg_code_scan_report_tool.py",
            "python3 parse_isg_code_scan_report.py",
        ],
        "behavior_without_arguments": "Print TOOL_CARD_MARKDOWN (human tool card) to stdout.",
        "exit_codes": {
            "0": "Success",
            "1": "Input/IO/PDF error",
            "2": "Warnings present and --fail-on-warnings set",
        },
        "json_job_schemas": {
            "structured_job": StructuredJobConfig.model_json_schema(),
            "simple_file_job": SimpleFileJobConfig.model_json_schema(),
        },
        "notes": {
            "project_issues": "Use structured job output.issue_field_subset for partial columns (JSON/YAML only).",
            "stdout": "Structured job with output.path omitted writes formatted text to stdout (json/yaml/csv).",
            "issue_row_schema": "FortifyIssue includes obv_id (OBV0001+), Fortify PDF fields, analysis/remediation placeholders; issue_state defaults OPEN on extract; formatter payload schema_version is 1.3.",
        },
    }
