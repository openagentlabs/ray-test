---
name: parse_isg_code_scan_report_tool
description: Run parse_isg_code_scan_report_tool.py — Fortify/ISG Developer Workbook PDF extractor (tool card, JSON jobs, CSV/JSON/YAML).
---

# Fortify workbook extract (MIDAS)

Use this skill when the user wants to **extract Fortify findings from a Developer Workbook PDF**, needs **tool invocation JSON/schemas**, or asks how **Cursor should call** the remediation CLI.

## Tool location

- **Package:** `.cursor/tools/fortify_workbook_extract/fortify_workbook_tool/`
- **CLI tool (canonical):** `.cursor/tools/fortify_workbook_extract/parse_isg_code_scan_report_tool.py`
- **Legacy shim:** `.cursor/tools/fortify_workbook_extract/parse_isg_code_scan_report.py` (forwards to the `_tool` script)
- **uv project:** `.cursor/tools/fortify_workbook_extract/pyproject.toml`, `uv.lock`, optional `.venv`
- **Deps (pip fallback):** `.cursor/tools/fortify_workbook_extract/requirements-workbook-tools.txt`

**Recommended:** run with **uv** from repo root:

```bash
uv run --project .cursor/tools/fortify_workbook_extract parse-isg-code-scan-report-tool
uv run --project .cursor/tools/fortify_workbook_extract parse-isg-code-scan-report-tool --tool-card-json
uv run --project .cursor/tools/fortify_workbook_extract parse-isg-code-scan-report-tool \
  --pdf "/path/to/DeveloperWorkbook.pdf" --output /tmp/out.csv --format csv \
  --final-report /tmp/extract_final_report.md
uv run --project .cursor/tools/fortify_workbook_extract parse-isg-code-scan-report-tool --print-csv-fields
```

Non-uv (script adds its directory to `sys.path`):

```bash
python3 .cursor/tools/fortify_workbook_extract/parse_isg_code_scan_report_tool.py
python3 .cursor/tools/fortify_workbook_extract/parse_isg_code_scan_report_tool.py --tool-card-json
python3 .cursor/tools/fortify_workbook_extract/parse_isg_code_scan_report_tool.py --pdf "/path/to/DeveloperWorkbook.pdf" --output /tmp/out.csv --format csv
python3 .cursor/tools/fortify_workbook_extract/parse_isg_code_scan_report_tool.py --json-config job.json
echo '<json>' | python3 .cursor/tools/fortify_workbook_extract/parse_isg_code_scan_report_tool.py --json-config -

cd .cursor/tools/fortify_workbook_extract
python3 parse_isg_code_scan_report_tool.py
python3 parse_isg_code_scan_report_tool.py --tool-card-json
```

## What to run first

| Goal | Command |
|------|---------|
| Human-readable tool card (markdown) | `python3 .cursor/tools/fortify_workbook_extract/parse_isg_code_scan_report_tool.py` *(no arguments)* |
| Machine-readable descriptor + JSON Schemas for jobs | `python3 .cursor/tools/fortify_workbook_extract/parse_isg_code_scan_report_tool.py --tool-card-json` |

## JSON jobs (for agents)

Two validated shapes (Pydantic); full schemas are printed by `--tool-card-json`.

1. **`simple_file`** — `pdf_path`, `output_path`, `output_format` (`csv` \| `json` \| `yaml`).
2. **`structured`** — `pdf_path`, nested `output`: `format`, optional `path` (omit or `null` → write payload to **stdout**), `include_priority_summary`, optional `issue_field_subset` for projected columns (JSON/YAML only).

Optional envelope: `{ "job": { ... } }`.

## Reports (`fortify_workbook_tool.report`)

| Class | Role |
|-------|------|
| `IssueCsvColumnCatalog` | Holds **`field_names`** (CSV headers); renders a Markdown list of columns. |
| `ExtractionSummaryReport` | Priority counts, row counts, warning counts (embedded in `FinalReport`). |
| `FinalReport` | User-facing Markdown report: paths, schema version, summary table, warning counts, **`csv_field_names`** (same array as the CSV header). Use **`build_final_report_from_extraction()`** after a successful extract. |

CLI: **`--final-report PATH`** writes `FinalReport` to disk; **`--print-csv-fields`** prints column names only.

## Architecture (for maintainers)

Internal **`WorkbookExtraction`** (`FortifyIssue` rows) → **formatter strategies** (`CsvIssueSinkFormatter`, `JsonIssueSinkFormatter`, `YamlIssueSinkFormatter`). Input JSON is handled by **`ToolJsonInputProcessor`** + **`coerce_job_config`**.

**`FortifyIssue` columns (formatter schema 1.3):** The **first** column is **`obv_id`** (`OBV0001`, `OBV0002`, …). Then Fortify PDF fields, then analysis placeholders (usually empty on extract), then remediation placeholders — `root_cause`, `remediation_plan`, `validation`, `acceptance_criteria`, `issue_resolve_progress`, `resolved_date`, `working_log`, **`issue_state`** (default **`OPEN`**). Filled during analysis/fix per `jp_isg_code_scan_results_analyzer_helper`. Logs live under `remediation/security_remediation/analysis_log/<analysis_id>.md`.

## Related rules

- Pipeline mutations for shared environments stay Jenkins-first per `.cursor/rules/jkenkins/jenkins.mdc`; this tool is **local extract-only**.
