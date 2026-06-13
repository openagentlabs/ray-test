# tf-tool — job card

> **Read policy:** Open **only** when you need to **invoke tf-tool** (public Terraform Registry search/list). For **`terraform init/plan/apply`**, use **[workflow.md](../../skills/tf/workflow.md)** instead. Read **one job** matching your intent; do not preload the whole file.

**Skill entry:** [../../skills/tf/SKILL.md](../../skills/tf/SKILL.md)  
**Tool path (repo root):** `.cursor/tools/tf-tool/`  
**Run (preferred):** `cd .cursor/tools/tf-tool && uv run tf-tool <command>`  
**Binary on PATH:** `tf-tool` (optional after [install](#job-00-install))  
**Auth:** none (public registry API)  
**Env check:** runs automatically before every command. Explicit: [JOB-01a](#job-01a-environment-doctor).  
**Operation UI (TTY):** blue spinner + operation label → green/red/yellow replay on stderr → summary table at end. JSON stays on stdout. Disable: `TF_TOOL_PLAIN=1`.

**Provider aliases** (`-p` / `--provider`): `azure`, `microsoft` → `azurerm`; `gcp`, `google-cloud` → `google`; `amazon`, `aws` → `aws`; also `alicloud`, `ibm`, `oracle`, `kubernetes`, etc. (see `catalog.py`).

---

## JOB-00: Install and sync (one-time / after lockfile change)

| Field | Value |
|-------|--------|
| **When** | First use, missing deps, or `doctor` fails |
| **Command** | `cd .cursor/tools/tf-tool && uv sync --dev` |
| **Optional PATH install** | `uv run tf-tool-build && uv run tf-tool-install` |
| **Verify** | `uv run tf-tool doctor` |
| **Exit** | 0 on success |
| **Output** | `.venv` with locked deps; `doctor` JSON with `"ok": true` |

**Agents:** always run via **`uv run tf-tool …`** from **`.cursor/tools/tf-tool`** unless a global `tf-tool` on PATH is verified with `doctor`.

---

## JOB-01a: Environment doctor

| Field | Value |
|-------|--------|
| **When** | Before first tf-tool use in a session; after `uv sync`; when imports fail |
| **Command** | `cd .cursor/tools/tf-tool && uv run tf-tool doctor` |
| **Alias** | `uv run tf-tool env-check` |
| **Exit** | 0 pass · 2 fail |
| **Output (stdout, JSON)** | Python + each runtime dependency with installed version vs required specifier |

```json
{
  "python": { "required": ">=3.12", "current": "3.12.3", "ok": true },
  "dependencies": [
    { "name": "httpx", "required": "httpx>=0.28", "installed": "0.28.1", "import_ok": true, "ok": true, "detail": null },
    { "name": "pydantic", "required": "pydantic>=2.10", "installed": "2.12.5", "import_ok": true, "ok": true, "detail": null },
    { "name": "returns", "required": "returns>=0.23", "installed": "0.26.0", "import_ok": true, "ok": true, "detail": null },
    { "name": "typer", "required": "typer>=0.15", "installed": "0.24.1", "import_ok": true, "ok": true, "detail": null }
  ],
  "source": "pyproject.toml (/path/to/.cursor/tools/tf-tool)",
  "ok": true
}
```

**Fail (stdout, JSON, exit 2):** `{ "error": "environment", "message": "...", "detail": "..." }`  
**Checks:** `requires-python` satisfied; each `dependencies` entry importable with version matching specifier (not exact pin — compatible with `pyproject.toml` / wheel metadata).

---

## JOB-01: Agent guide (live card)

| Field | Value |
|-------|--------|
| **When** | First use in session or output shape unclear |
| **Command** | `tf-tool --agent-help` |
| **Alternates** | `tf-tool agent-guide` · `tf-tool agent-help` |
| **Flags** | Do **not** combine with another subcommand |
| **Exit** | 0 |
| **Output** | Plain-text guide on **stdout**; build gate skipped |

---

## JOB-02: Smoke test — helloworld (subcommand)

| Field | Value |
|-------|--------|
| **When** | Verify CLI wiring |
| **Command** | `tf-tool helloworld` |
| **Parameters** | `--name` / `-n` (optional, default `World`) |
| **Example** | `tf-tool helloworld --name Terraform` |
| **Exit** | 0 |
| **Output (stdout, text)** | `Hello, Terraform!` |

---

## JOB-03: Smoke test — helloworld (root flag)

| Field | Value |
|-------|--------|
| **When** | Same as JOB-02 via root callback |
| **Command** | `tf-tool -w` or `tf-tool --helloworld` |
| **Parameters** | `-n` / `--name` (optional, default `World`) |
| **Example** | `tf-tool -w -n Terraform` |
| **Exit** | 0 |
| **Output (stdout, text)** | `Hello, Terraform!` |

---

## JOB-04: Search AWS by keyword (default)

| Field | Value |
|-------|--------|
| **When** | Find AWS modules by keyword |
| **Command** | `tf-tool search-aws` |
| **Parameters** | `-q` / `--query` **required**; `--limit` 1–100 (default 20); `--offset` ≥0 (default 0); `--namespace`; `--verified` / `--all`; optional pagination |
| **Example** | `tf-tool search-aws -q vpc --limit 1` |
| **Alias** | `registry-search-aws` (same flags) |
| **Exit** | 0 success · 2 validation/build |
| **Output (stdout, JSON)** | Search envelope — see [Search JSON shape](#search-json-shape) |

```json
{
  "query": "vpc",
  "provider": "aws",
  "namespace": null,
  "verified": null,
  "limit": 1,
  "offset": 0,
  "meta": { "limit": 1, "current_offset": 0, "next_offset": 1, "next_url": "..." },
  "modules": [{ "id": "terraform-aws-modules/vpc/aws/6.6.1", "namespace": "...", "name": "vpc", "version": "6.6.1", "provider": "aws", "description": "...", "source": "https://github.com/...", "downloads": 191212434, "verified": false, "published_at": "2026-04-02T20:22:11.071125Z" }],
  "count": 1
}
```

---

## JOB-05: Search AWS — publisher namespace filter

| Field | Value |
|-------|--------|
| **Command** | `tf-tool search-aws -q <keyword> --namespace <publisher> --limit <n>` |
| **Example** | `tf-tool search-aws -q vpc --namespace terraform-aws-modules --limit 5` |
| **Output** | Same as JOB-04; `namespace` field set in envelope |

---

## JOB-06: Search AWS — verified partners only

| Field | Value |
|-------|--------|
| **Command** | `tf-tool search-aws -q <keyword> --verified --limit <n>` |
| **Example** | `tf-tool search-aws -q label --verified --limit 5` |
| **Output** | Same as JOB-04; modules have `"verified": true` |

---

## JOB-07: Search AWS — pagination

| Field | Value |
|-------|--------|
| **Command** | `tf-tool search-aws -q <keyword> --offset <n> --limit <n>` |
| **Example** | `tf-tool search-aws -q vpc --offset 20 --limit 10` |
| **Output** | Same as JOB-04; use `meta.next_offset` / `meta.next_url` for next page |

---

## JOB-08: Generic search — keyword + optional provider

| Field | Value |
|-------|--------|
| **When** | Search with optional `-p` filter |
| **Command** | `tf-tool registry-search` |
| **Parameters** | `-q` **required**; `-p` / `--provider` optional; `--namespace`; `--verified`; `--limit`; `--offset` |
| **Example** | `tf-tool registry-search -q s3 -p aws --limit 5` |
| **Exit** | 0 · 2 |
| **Output** | Search JSON (JOB-04) |

---

## JOB-09: Generic search — keyword only (all providers)

| Field | Value |
|-------|--------|
| **Command** | `tf-tool registry-search -q <keyword> --limit <n>` |
| **Example** | `tf-tool registry-search -q database --limit 10` |
| **Output** | Search JSON; `"provider": null` in envelope |

---

## JOB-10: Search cloud — keyword + required provider

| Field | Value |
|-------|--------|
| **When** | Search one cloud; `-p` **required** |
| **Command** | `tf-tool search-cloud` |
| **Parameters** | `-q` **required**; `-p` **required**; `--namespace`; `--verified`; `--limit`; `--offset` |
| **Example** | `tf-tool search-cloud -q network -p gcp --limit 5` |
| **Output** | Search JSON; `provider` = resolved slug (e.g. `google`) |

---

## JOB-11: Search Google Cloud by keyword

| Field | Value |
|-------|--------|
| **Command** | `tf-tool registry-search-google` |
| **Parameters** | `-q` **required**; `--namespace`; `--verified`; `--limit`; `--offset` |
| **Example** | `tf-tool registry-search-google -q vpc --limit 5` |
| **Output** | Search JSON; `provider` always `google` |

---

## JOB-12: Search Azure by keyword

| Field | Value |
|-------|--------|
| **Command** | `tf-tool registry-search-azurerm` |
| **Parameters** | `-q` **required**; `--namespace`; `--verified`; `--limit`; `--offset` |
| **Example** | `tf-tool registry-search-azurerm -q vnet --limit 5` |
| **Output** | Search JSON; `provider` always `azurerm` |

---

## JOB-13: List AWS — JSON (agents / CI)

| Field | Value |
|-------|--------|
| **When** | Browse AWS modules without keyword; **must** use `--json` in automation |
| **Command** | `tf-tool list-aws --json` |
| **Parameters** | `--limit` 1–100 (default 20); `--offset`; `--namespace`; `--verified`; **`--json` required** for non-TTY |
| **Example** | `tf-tool list-aws --limit 2 --json` |
| **Alias** | `registry-list-aws` |
| **Exit** | 0 · 2 |
| **Output (stdout, JSON)** | List envelope — see [List JSON shape](#list-json-shape) |

```json
{
  "mode": "list",
  "provider": "aws",
  "namespace": null,
  "verified": null,
  "limit": 2,
  "offset": 0,
  "meta": { "limit": 2, "current_offset": 0, "next_offset": 2, "next_url": "..." },
  "modules": [{ "id": "aws-ia/label/aws/0.0.6", "namespace": "aws-ia", "name": "label", "version": "0.0.6", "provider": "aws", "description": "AWS Label Module", "source": "https://github.com/...", "downloads": 1792726, "verified": true }],
  "count": 2
}
```

---

## JOB-14: List AWS — human table (TTY)

| Field | Value |
|-------|--------|
| **When** | Interactive browse; stdin is a TTY |
| **Command** | `tf-tool list-aws --limit <n>` |
| **Example** | `tf-tool list-aws --limit 2` |
| **Output (stdout, text table)** | Numbered rows; optional download prompt after table |
| **Note** | No `--json`; piped/non-TTY ends after table (no prompt) |

```text
Terraform Registry modules (provider=aws) — showing 2:

  #  Name                                       Version      Description
------------------------------------------------------------------------
  1. aws-ia/label/aws                           0.0.6        AWS Label Module
  2. aws-ia/vpc/aws                             4.7.3        AWS VPC Module

Enter row number to download (Esc to exit):
```

---

## JOB-15: List AWS — namespace filter (JSON)

| Field | Value |
|-------|--------|
| **Command** | `tf-tool list-aws --namespace <publisher> --limit <n> --json` |
| **Example** | `tf-tool list-aws --namespace terraform-aws-modules --limit 5 --json` |
| **Output** | List JSON; `namespace` set in envelope |

---

## JOB-16: List AWS — verified only (JSON)

| Field | Value |
|-------|--------|
| **Command** | `tf-tool list-aws --verified --limit <n> --json` |
| **Example** | `tf-tool list-aws --verified --limit 10 --json` |
| **Output** | List JSON; verified modules only |

---

## JOB-17: Generic list — optional provider (JSON)

| Field | Value |
|-------|--------|
| **Command** | `tf-tool registry-list --json` |
| **Parameters** | `-p` optional; `--namespace`; `--verified`; `--limit`; `--offset`; **`--json`** |
| **Example** | `tf-tool registry-list -p aws --limit 5 --json` |
| **Output** | List JSON |

---

## JOB-18: List cloud — required provider (JSON)

| Field | Value |
|-------|--------|
| **When** | Browse one cloud without keyword |
| **Command** | `tf-tool list-cloud -p <provider> --json` |
| **Parameters** | `-p` **required**; `--namespace`; `--verified`; `--limit`; `--offset`; **`--json`** |
| **Example** | `tf-tool list-cloud -p azure --limit 5 --json` |
| **Output** | List JSON; `provider` = resolved slug |

---

## JOB-19: Validation error (any search command)

| Field | Value |
|-------|--------|
| **When** | Blank/invalid input (example) |
| **Command** | `tf-tool registry-search -q "   "` |
| **Exit** | **2** |
| **Output (stderr, JSON)** | |

```json
{
  "error": "validation",
  "message": "Invalid registry search request.",
  "detail": "query: Search query must not be blank."
}
```

---

## Output shapes (reference)

### Search JSON shape

| Field | Type | Notes |
|-------|------|-------|
| `query` | string | Search keyword |
| `provider` | string \| null | Filter slug |
| `namespace` | string \| null | Publisher filter |
| `verified` | bool \| null | Partner filter |
| `limit`, `offset` | int | Request paging |
| `meta` | object | `limit`, `current_offset`, `next_offset`, `next_url` |
| `modules[]` | array | `id`, `namespace`, `name`, `version`, `provider`, `description`, `source`, `downloads`, `verified`, `published_at`, … |
| `count` | int | Length of `modules` |

### List JSON shape

Same as search except: `"mode": "list"`, no `query` field.

---

## Decision quick pick

| Need | Job |
|------|-----|
| Sync / install | JOB-00 |
| Validate Python + deps | JOB-01a |
| AWS keyword search | JOB-04 |
| Any cloud keyword | JOB-10 |
| Browse AWS (agent) | JOB-13 |
| Browse one cloud (agent) | JOB-18 |
| CLI smoke test | JOB-02 |
| Full live guide | JOB-01 |

**Not supported:** `terraform plan/apply/validate`, private registries, non-interactive module download on list (use `--json` for metadata only).
