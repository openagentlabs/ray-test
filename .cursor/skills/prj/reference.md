# prj — reference (on demand)

> **Read policy:** Open **only** when **workflow.md** cites a section below. Read **one section at a time**.

**Catalog path:** **`.cursor/rules/constants.mdc`**

---

## Help output

When **`WorkflowHelp:`** runs, emit this block (keep capability order: **init** → **init-quick** → **help** → **show**):

```markdown
# prj skill — capabilities

| Capability | What it does | How to ask the agent |
|------------|--------------|----------------------|
| **init** | Guided setup of all six `PRJ_*` constants (one question per turn); validates; writes `constants.mdc` after you confirm | `prj init`, "init project constants", "configure PRJ_NAME" |
| **init-quick** | Same as init; reply **keep** to skip any constant | `prj init --quick`, "quick project init" |
| **help** | Show this list (no file changes) | `prj help`, "what can prj do?" |
| **show** | Read-only table of current `PRJ_*` values (no file changes) | `prj show`, "show project constants", "what are the PRJ_* values?" |

**Constants covered:** `PRJ_NAME`, `PRJ_SLUG`, `PRJ_PACKAGE`, `PRJ_DESCRIPTION`, `PRJ_VERSION`, `PRJ_RELEASE_DATE`

**Catalog file:** `.cursor/rules/constants.mdc` (Group 1 — Project)

Reply with a capability name to start (`init`, `init-quick`, or `show`).
```

Do not read **workflow.md** or **reference.md** for **`help`** beyond this section.

---

## Parse constants.mdc

Group 1 rows live under **`### Group 1 — Project (`PRJ_`)`**.

Each row format:

```text
N. **`PRJ_<ID>`** — `<value>` — <Use> — Format: <constraints>
```

**Parse rules:**

1. Match `` **`PRJ_[A-Z_]+`** — `` then capture value between backticks before the next ` — `.
2. Strip surrounding backticks from value; preserve inner spaces for `PRJ_NAME` / `PRJ_DESCRIPTION`.
3. Capture the **Format / constraints** segment (after last ` — Format:` or trailing ` — Format` on the line).

**POSTCONDITION:** `current` map has keys: `PRJ_NAME`, `PRJ_SLUG`, `PRJ_PACKAGE`, `PRJ_DESCRIPTION`, `PRJ_VERSION`, `PRJ_RELEASE_DATE`.

---

## Question template

For constant **`PRJ_<ID>`** (step **k/6**):

```markdown
### PRJ_<ID> (k/6)

**Current value:** `<current[id]>`

**Used for:** <Use column from constants.mdc>

**Format / constraints:** <Format column from constants.mdc>

Reply with a new value, or **`keep`** to leave unchanged.
```

Optional one-line hint when the format is non-obvious (see **[Examples](#examples)**).

---

## Validation by constant ID

Apply **before** leaving the collect stage. Return `{ ok: true }` or `{ ok: false, message: "..." }` with a **specific** fix hint.

### PRJ_NAME

| Rule | Check |
|------|--------|
| Required | Non-empty after trim |
| Length | 1–128 characters |
| Type | Free text — any printable Unicode allowed |

**ON_ERROR examples:** “Name cannot be empty.” / “Shorten to 128 characters or fewer.”

### PRJ_SLUG

| Rule | Check |
|------|--------|
| Pattern | `^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$` (single char ok; no leading/trailing `-`) |
| No double hyphen | Must not contain `--` |
| Length | 2–32 characters recommended (warn if >32; block if >63) |

**ON_ERROR examples:** “Use lowercase letters, digits, and single hyphens only.” / “Remove leading/trailing hyphens.” / “Replace `--` with single `-`.”

### PRJ_PACKAGE

| Rule | Check |
|------|--------|
| Pattern | `^[a-z][a-z0-9_]*$` |
| No hyphen | Must not contain `-` |
| Length | 2–32 characters recommended |

**ON_ERROR examples:** “Use lowercase snake_case (e.g. `my_app`).” / “Hyphens are not allowed — use `_`.”

### PRJ_DESCRIPTION

| Rule | Check |
|------|--------|
| Required | Non-empty after trim |
| Length | 1–256 characters (AWS tag practical limit) |

### PRJ_VERSION

| Rule | Check |
|------|--------|
| Semver | `^\d+\.\d+\.\d+$` |
| Components | Non-negative integers |

**ON_ERROR:** “Use semver `MAJOR.MINOR.PATCH` (e.g. `1.0.0`).”

### PRJ_RELEASE_DATE

| Rule | Check |
|------|--------|
| Pattern | `^\d{4}-\d{2}-\d{2}$` |
| Valid date | Real calendar date (reject 2026-02-30) |

**ON_ERROR:** “Use ISO date `YYYY-MM-DD` (e.g. `2026-05-16`).”

---

## Cross-validation

After all six constants collected (resolve **`keep`** → `current` value):

```text
replace(PRJ_PACKAGE, "_", "-") MUST EQUAL PRJ_SLUG
```

**If mismatch:**

- Message: “`PRJ_SLUG` must equal `PRJ_PACKAGE` with `_` replaced by `-`. Given package `{PRJ_PACKAGE}` → expected slug `{expected}`.”
- **Jmp:** `WorkflowCollectPRJ_SLUG` if user should fix slug; or `WorkflowCollectPRJ_PACKAGE` if they should fix package — ask which they prefer to change.

---

## Derived updates

When **`PRJ_SLUG`**, **`PRJ_PACKAGE`**, or description/version/date change, patch **literal echoes** in **`constants.mdc`** (same file edit pass):

| Constant ID | Update rule |
|-------------|-------------|
| **`NET_EKS_CLUSTER_NAME`** | Value backtick text must equal final **`PRJ_SLUG`** |
| **`TAG_KEY_APPLICATION`** | Example/value prose referencing slug — value line uses **`PRJ_SLUG`** reference (already formula); update parenthetical example `(ray-test)` → `({PRJ_SLUG value})` |
| **`TAG_KEY_PROJECT`** | Update parenthetical `({PRJ_PACKAGE value})` example |
| **`TAG_KEY_PROJECT_ID`** | Update **Example:** `ray-test-dev-…` prefix to `{PRJ_SLUG}-…` (keep **`DEP_KEY`** suffix) |
| Group 4 **Example:** fragments | Replace old slug prefix in examples (`ray-test-platform` → `{PRJ_SLUG}-platform`, etc.) only where the example used the previous slug |

Do **not** recompute **`DEP_KEY`** or network **Name** pattern templates (`{prefix}-…`) — those use `{prefix}` = **`PRJ_SLUG`** symbolically.

**STORE** each literal replacement in `derived_patches[]` for recap table.

---

## Patch constants.mdc

1. Read full file.
2. For each `PRJ_*` in `answers`, replace only the **value** backticks on that constant’s numbered row — preserve row number, Use, and Format text.
3. Apply `derived_patches[]` similarly (value or example segments only).
4. Do not alter frontmatter, Rules, or unrelated groups.
5. Re-read and verify all six Group 1 values match `answers`.

**Row pattern (regex-friendly):**

```text
^(\d+\. \*\*`PRJ_NAME`\*\* — )`[^`]*`( — .*)$
→ replace middle value only
```

Repeat per id.

---

## Examples

Helpful suggestions when user asks (must still validate if accepted):

| ID | Compliant examples |
|----|-------------------|
| `PRJ_NAME` | `Ray Test`, `Acme Platform` |
| `PRJ_SLUG` | `ray-test`, `acme-platform` |
| `PRJ_PACKAGE` | `ray_test`, `acme_platform` |
| `PRJ_DESCRIPTION` | `Ray Test primary AWS infrastructure.` |
| `PRJ_VERSION` | `0.1.0`, `1.2.3` |
| `PRJ_RELEASE_DATE` | `2026-05-16` |

**Slug ↔ package pairs:**

| `PRJ_PACKAGE` | Matching `PRJ_SLUG` |
|---------------|---------------------|
| `ray_test` | `ray-test` |
| `acme_platform` | `acme-platform` |

---

## Common error → Jmp map

| Error | Fix hint | Jump |
|-------|----------|------|
| Empty name/description | Provide non-empty text | Same collect stage |
| Invalid slug charset | Lowercase kebab-case | `WorkflowCollectPRJ_SLUG` |
| Package has hyphen | Use underscore | `WorkflowCollectPRJ_PACKAGE` |
| Slug ≠ package transform | Align pair per cross-validation | Slug or package collect stage |
| Bad semver | `MAJOR.MINOR.PATCH` | `WorkflowCollectPRJ_VERSION` |
| Bad date | `YYYY-MM-DD` | `WorkflowCollectPRJ_RELEASE_DATE` |
| User declined write | No file change | `WorkflowHandoff` |
| Parse failure | Fix constants.mdc structure manually | **STOP** |

Workflow stages: **[workflow.md](workflow.md)**.
