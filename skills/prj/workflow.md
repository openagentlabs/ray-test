# prj — workflow (authoritative for this skill)

> **Read policy:** Open **only** when executing the **prj** skill (after **`SKILL.md`** mandatory rules). Read **[reference.md](reference.md)** **one section at a time** when a stage cites **VALIDATE**, **PATCH**, or **ON_ERROR**.

Execute **`WorkflowStart:`** → … → **`WorkflowEnd:`**. **`→`** = default next stage.

| Stage | Do | Branch / Jmp |
|-------|----|--------------|
| **`WorkflowStart:`** | Load capability (`init` \| `init-quick` \| `help` \| `show`). **STORE:** `capability`, `constants_path=.cursor/rules/constants/constants.mdc`, `answers={}`, `order=[PRJ_NAME, PRJ_SLUG, PRJ_PACKAGE, PRJ_DESCRIPTION, PRJ_VERSION, PRJ_RELEASE_DATE]`, `write_approved=false`. **RUN:** read full **`constants.mdc`** when capability needs it | `help` → **`Jmp: WorkflowHelp`**. `show` → **`Jmp: WorkflowShow`**. `init` / `init-quick` → **`WorkflowInit:`** |
| **`WorkflowHelp:`** | **RUN:** emit **[Help output](reference.md#help-output)** (capabilities table + how to ask). No file writes. Offer: “Reply with a capability name (`init`, `init-quick`, `show`) to continue.” | → **`WorkflowHandoff:`** |
| **`WorkflowInit:`** | Briefly explain: init configures **Group 1 — Project (`PRJ_*`)**; six constants; **one question per message**; reply **`keep`** to retain current value. **ASK:** “Start project init? (`yes` / `no`)" | No → **`Jmp: WorkflowHandoff`**. Yes → **`WorkflowLoadCurrent:`** |
| **`WorkflowLoadCurrent:`** | **RUN:** parse current Group 1 rows per **[reference.md § Parse](reference.md#parse-constantsmdc)**. **STORE:** `current{}` map id → value. **POSTCONDITION:** all six ids present | Missing row → report; **STOP** | → **`WorkflowCollectPRJ_NAME:`** |
| **`WorkflowCollectPRJ_NAME:`** | **ASK** one question for **`PRJ_NAME`** per **[reference.md § Question template](reference.md#question-template)**. Accept new value or **`keep`** | **VALIDATE** → **[PRJ_NAME](reference.md#prj_name)**. **ON_ERROR** → explain; **`Jmp: WorkflowCollectPRJ_NAME`**. **STORE** in `answers.PRJ_NAME` | → **`WorkflowCollectPRJ_SLUG:`** |
| **`WorkflowCollectPRJ_SLUG:`** | **ASK** for **`PRJ_SLUG`** (show current + format). Accept **`keep`** | **VALIDATE** → **[PRJ_SLUG](reference.md#prj_slug)**. **ON_ERROR** → **`Jmp: WorkflowCollectPRJ_SLUG`** | → **`WorkflowCollectPRJ_PACKAGE:`** |
| **`WorkflowCollectPRJ_PACKAGE:`** | **ASK** for **`PRJ_PACKAGE`** | **VALIDATE** → **[PRJ_PACKAGE](reference.md#prj_package)**. **ON_ERROR** → **`Jmp: WorkflowCollectPRJ_PACKAGE`** | → **`WorkflowCollectPRJ_DESCRIPTION:`** |
| **`WorkflowCollectPRJ_DESCRIPTION:`** | **ASK** for **`PRJ_DESCRIPTION`** | **VALIDATE** → **[PRJ_DESCRIPTION](reference.md#prj_description)**. **ON_ERROR** → **`Jmp: WorkflowCollectPRJ_DESCRIPTION`** | → **`WorkflowCollectPRJ_VERSION:`** |
| **`WorkflowCollectPRJ_VERSION:`** | **ASK** for **`PRJ_VERSION`** | **VALIDATE** → **[PRJ_VERSION](reference.md#prj_version)**. **ON_ERROR** → **`Jmp: WorkflowCollectPRJ_VERSION`** | → **`WorkflowCollectPRJ_RELEASE_DATE:`** |
| **`WorkflowCollectPRJ_RELEASE_DATE:`** | **ASK** for **`PRJ_RELEASE_DATE`** | **VALIDATE** → **[PRJ_RELEASE_DATE](reference.md#prj_release_date)**. **ON_ERROR** → **`Jmp: WorkflowCollectPRJ_RELEASE_DATE`** | → **`WorkflowCrossValidate:`** |
| **`WorkflowCrossValidate:`** | **RUN:** **[Cross-validation](reference.md#cross-validation)** on final `PRJ_SLUG` + `PRJ_PACKAGE` (use `answers` or `current` when **`keep`**) | Fail → show fix hint; **`Jmp: WorkflowCollectPRJ_SLUG`** or **`WorkflowCollectPRJ_PACKAGE`** per hint | → **`WorkflowSyncDerived:`** |
| **`WorkflowSyncDerived:`** | **RUN:** compute derived literal updates per **[Derived updates](reference.md#derived-updates)**. **STORE:** `derived_patches[]` | → **`WorkflowRecap:`** |
| **`WorkflowRecap:`** | Show table: Constant \| Previous \| New \| Changed (yes/no). Include derived rows if any. **ASK:** “Apply these changes to **`constants.mdc`**? (`yes` / `no`)" | No → **`Jmp: WorkflowHandoff`**. Yes → **`write_approved=true`** → **`WorkflowWriteConstants:`** |
| **`WorkflowWriteConstants:`** | **PRE:** `write_approved`. **RUN:** **[Patch constants.mdc](reference.md#patch-constantsmdc)** for Group 1 + `derived_patches`. Re-read file; verify six rows updated | **ON_ERROR** → report; **STOP** | → **`WorkflowHandoff:`** |
| **`WorkflowShow:`** | **RUN:** parse Group 1; emit read-only markdown table (id, value, format summary). No writes | → **`WorkflowHandoff:`** |
| **`WorkflowHandoff:`** | Summarize: capability run, constants changed (or “help/show only”), derived sync, reminder about **`terraform.tfvars`** / package.json if slug or package changed | → **`WorkflowEnd:`** |
| **`WorkflowEnd:`** | User knows outcome. **STOP** — no further writes without new **`WorkflowStart:`** | |

---

## Capability → path

| Capability | Stages |
|------------|--------|
| **`init`** | Start → Init → Load → Collect (×6) → CrossValidate → SyncDerived → Recap → Write → Handoff → End |
| **`init-quick`** | Same as **`init`**; **`keep`** allowed every collect stage |
| **`help`** | Start → Help → Handoff → End |
| **`show`** | Start → Show → Handoff → End |

---

## Jmp labels (this workflow)

| Label | Use |
|-------|-----|
| **`WorkflowHelp:`** | List capabilities; no writes |
| **`WorkflowCollectPRJ_<NAME>:`** | Re-ask after validation failure |
| **`WorkflowCollectPRJ_SLUG:`** / **`WorkflowCollectPRJ_PACKAGE:`** | Cross-validation mismatch |
| **`WorkflowHandoff:`** | User declined init or write |
| **`WorkflowShow:`** | Read-only path |

DSL semantics (generic): **[workflow-reference.md](../_shared/workflow-reference.md)**.

---

## Agent reminders (collect stages)

- **One message = one constant** — never batch two `PRJ_*` questions.
- **Be helpful** — if the user is unsure, offer 1–2 compliant examples from **[reference.md § Examples](reference.md#examples)**; do not choose for them unless they ask for a suggestion and confirm.
- **`keep`** — copy `current[id]` into `answers[id]` without validation failure.
- **Empty reply** — treat as unclear; re-ask the same constant (do not advance).
