---
name: page-create
description: >-
  Arb Aspire (aspire.svc/) page scaffold: collects page and component metadata one
  question at a time with validation, generates UUID-backed page class wiring,
  route container, page component, and navigation entry per
  aspire.svc/.cursor/rules/nextjs.mdc. Use for new pages, routes, workspace sections,
  or when the user invokes page-create / page_create.
---

# page-create — Arb Aspire (Cursor skill)

## AI Agent Operating Rules (MUST FOLLOW)

Read these rules **before** running any step. They govern how the workflow below is executed.

1. **Execute the workflow in order, start to finish.** Begin at `STEP_1_INPUT_PAGE_SEGMENT` and proceed sequentially.
2. **NEVER skip a step.** Each step has a precondition, an action, and a postcondition. The next step MUST NOT begin until the current step's postcondition is satisfied.
3. **The only legal way to leave the current step out of order is a `JMP` or `GOTO` directive.** A `JMP <LABEL>` directive may appear:
   - Inside a step's `ON_ERROR` clause, redirecting flow to a recovery label.
   - Inside a step's `ON_<condition>` clause, redirecting flow based on a documented state (e.g. `ON_SIDEBAR_OPT_IN: PROCEED`, `ON_SIDEBAR_OPT_OUT: JMP STEP_10_VERIFY`).
   - In an explicit user instruction during the run (e.g. "GOTO STEP_3_GENERATE_UID").
4. **Validation is per-question, not per-step.** When a step collects input from the user, ask **one question at a time** and validate that input against the step's `VALIDATE` rules **before** asking the next question or advancing to the next step. On validation failure, `JMP` back to the same question with a corrective message.
5. **Never invent inputs.** If a required input is missing or ambiguous, `JMP` back to the input step. Do not assume defaults beyond those explicitly listed in `DEFAULT` clauses.
6. **All file paths are relative to the solution root** (`Arb Sherpa` repository root). Use the **`@/`** import alias for cross-folder imports.
7. **Obey existing rules** at every step:
   - Page structure (`aspire.svc/.cursor/rules/nextjs.mdc` §"Page routes and page components") — two-piece contract is mandatory.
   - TypeScript style (`aspire.svc/.cursor/rules/typescript/typescript.mdc`) — `strict`, no `any`, prefer `interface`, no enums.
   - Style guide (`aspire.svc/.cursor/rules/pages_compoents_style_guide.mdc`) — semantic tokens, shadcn, lucide.
   - Architecture (`aspire.svc/.cursor/rules/architetcure.mdc` → `nextjs.mdc`) — classes in `lib/` and page-private classes co-located in `components/pages/<segment>/`.
8. **Cleanup on abort.** If the user aborts mid-run, `JMP STEP_99_ABORT`. Do not leave half-created files on disk.

---

## Inputs collected (in order)

| # | Name | Type | Validation summary |
|---|------|------|--------------------|
| 1 | `page_segment` | kebab-case string | Matches `^[a-z][a-z0-9-]*$`; `app/pages/<page_segment>/` and `components/pages/<page_segment>/` do NOT already exist. |
| 2 | `page_title` | non-empty string | 1–64 chars; will be shown in the nav and `<h1>`. |
| 3 | `page_description` | non-empty string | 1–280 chars; shown as placeholder content + nav metadata. |
| 4 | `component_name` | PascalCase TS identifier | Matches `^[A-Z][A-Za-z0-9]*$`; not a reserved word; will be a class name. |
| 5 | `component_description` | non-empty string | 1–280 chars; stored as a readonly property on the component class. |
| 6 | `add_to_sidebar` | `yes` \| `no` | Lowercased; controls whether `NavigationService` is updated. |

The **`component_uid`** is generated automatically in `STEP_7_GENERATE_UID` (UUID v4 via `crypto.randomUUID()`). Never ask the user for it.

---

## Workflow

### STEP_1_INPUT_PAGE_SEGMENT

- **ASK** (one question): "What is the page route segment? Use kebab-case (lowercase letters, digits, and `-`), e.g. `reports` or `audit-trail`. This becomes `app/pages/<segment>/` and `components/pages/<segment>/`."
- **VALIDATE**:
  - Matches regex `^[a-z][a-z0-9-]*$` (must start with a letter; no leading/trailing `-`; no `--`).
  - Length 1–48.
  - Folder `app/pages/<page_segment>/` does NOT already exist.
  - Folder `components/pages/<page_segment>/` does NOT already exist.
  - Not in the reserved set: `api`, `actions`, `globals`, `layout`, `page`, `error`, `loading`, `not-found`.
- **ON_ERROR**: print the specific failure and `JMP STEP_1_INPUT_PAGE_SEGMENT`.
- **STORE** as `page_segment`.

### STEP_2_INPUT_PAGE_TITLE

- **ASK**: "What is the page title? This is the human-readable name shown in the sidebar and as the `<h1>` (e.g. `Reports`, `Audit trail`)."
- **VALIDATE**: 1–64 chars, non-whitespace.
- **ON_ERROR**: `JMP STEP_2_INPUT_PAGE_TITLE`.
- **STORE** as `page_title`.

### STEP_3_INPUT_PAGE_DESCRIPTION

- **ASK**: "Describe what this page does in one sentence (1–280 chars). It will be used as placeholder content and as nav metadata."
- **VALIDATE**: 1–280 chars, non-whitespace.
- **ON_ERROR**: `JMP STEP_3_INPUT_PAGE_DESCRIPTION`.
- **STORE** as `page_description`.

### STEP_4_INPUT_COMPONENT_NAME

- **ASK**: "What is the **component name** of the primary component used on this page? Use PascalCase, e.g. `ReportSummary`. This becomes the TypeScript **class name** (`<component_name>Component`) and the React wrapper component."
- **VALIDATE**:
  - Matches regex `^[A-Z][A-Za-z0-9]*$`.
  - Length 2–48.
  - Does NOT end with `Component`, `Page`, or `Props` (the workflow appends suffixes itself).
  - Not a reserved TS keyword.
- **ON_ERROR**: `JMP STEP_4_INPUT_COMPONENT_NAME`.
- **STORE** as `component_name`. Derive `component_kebab = kebabCase(component_name)` for filenames.

### STEP_5_INPUT_COMPONENT_DESCRIPTION

- **ASK**: "Describe what the `${component_name}` component does in one sentence (1–280 chars). This is stored as a `readonly description` property on the component class."
- **VALIDATE**: 1–280 chars, non-whitespace.
- **ON_ERROR**: `JMP STEP_5_INPUT_COMPONENT_DESCRIPTION`.
- **STORE** as `component_description`.

### STEP_6_INPUT_SIDEBAR

- **ASK**: "Should this page appear in the workspace sidebar? Answer `yes` or `no`."
- **VALIDATE**: lowercased value is exactly `yes` or `no`.
- **ON_ERROR**: `JMP STEP_6_INPUT_SIDEBAR`.
- **STORE** as `add_to_sidebar`.

### STEP_7_GENERATE_UID

- **ACTION**: generate `component_uid` as a **UUID v4** string via Node `crypto.randomUUID()` (or equivalent). Do not ask the user.
- **POSTCONDITION**: `component_uid` matches `^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`.
- **ON_ERROR**: `JMP STEP_7_GENERATE_UID`.

### STEP_8_CONFIRM

- **ACTION**: print a recap to the user with every input and the generated `component_uid`, plus the four planned files (and the optional nav edit). Ask: "Proceed with scaffolding? (`yes` / `no`)".
- **ON `no`**: `JMP STEP_99_ABORT`.
- **ON `yes`**: proceed.
- **ON invalid**: `JMP STEP_8_CONFIRM`.

### STEP_9_PREFLIGHT

- **ACTION**: re-verify that the following do NOT exist:
  - `app/pages/<page_segment>/page.tsx`
  - `components/pages/<page_segment>/` (and any file under it)
- **ACTION**: read `lib/navigation/navigation-service.ts` to confirm no nav `id` collision with `<page_segment>`.
- **ON_ERROR** (path or id already exists): print the conflict and `JMP STEP_1_INPUT_PAGE_SEGMENT`.

### STEP_10_CREATE_COMPONENT_CLASS

Create file **`components/pages/<page_segment>/<component_kebab>.ts`** with the contents from `TEMPLATE_COMPONENT_CLASS` below. Substitute placeholders:

- `{{ComponentName}}` → `component_name`
- `{{component_uid}}` → `component_uid`
- `{{component_name}}` → `component_name` (escape backticks inside the description value)
- `{{component_description}}` → `component_description` (escape backticks)

**POSTCONDITION**: file exists; no lint errors on it.
**ON_ERROR**: `JMP STEP_99_ABORT`.

### STEP_11_CREATE_COMPONENT_VIEW

Create file **`components/pages/<page_segment>/<component_kebab>.tsx`** with the contents from `TEMPLATE_COMPONENT_VIEW`. This is the React wrapper that renders the metadata held by the class created in STEP_10.

**POSTCONDITION**: file exists; no lint errors on it.
**ON_ERROR**: `JMP STEP_99_ABORT`.

### STEP_12_CREATE_PAGE_COMPONENT

Create file **`components/pages/<page_segment>/<page_segment>-page.tsx`** with the contents from `TEMPLATE_PAGE_COMPONENT`. The page component is the container that composes `<{{ComponentName}}View />` from STEP_11.

**POSTCONDITION**: file exists; no lint errors on it; named export is `<PageSegmentPascal>Page` and exported props type is `<PageSegmentPascal>PageProps`.
**ON_ERROR**: `JMP STEP_99_ABORT`.

### STEP_13_CREATE_ROUTE_FILE

Create file **`app/pages/<page_segment>/page.tsx`** with the contents from `TEMPLATE_ROUTE_FILE`. The default export is named `<PageSegmentPascal>Route` and renders `<{{PageSegmentPascal}}Page />`.

**POSTCONDITION**: file exists; route renders without runtime errors; no lint errors on it.
**ON_ERROR**: `JMP STEP_99_ABORT`.

### STEP_14_UPDATE_NAVIGATION

- **PRECONDITION**: `add_to_sidebar` is set.
- **ON `no`**: `JMP STEP_15_VERIFY`.
- **ON `yes`**:
  - Open `lib/navigation/navigation-service.ts`.
  - Insert a new entry into the `mainNavigation` frozen array, **before** the existing `user` entry (or at the end if `user` is absent), with shape:
    ```ts
    {
      id: "<page_segment>",
      title: "<page_title>",
      href: "/pages/<page_segment>",
    },
    ```
  - If the page needs a sidebar icon, also add a string-id → icon mapping in `lib/navigation/navigation-icon-resolver.ts`. Use a lucide icon that matches the page's purpose (e.g. `FileText` for report-like pages, `Settings` for config). If no obvious match, do NOT add an icon mapping — the resolver should fall back gracefully.
- **POSTCONDITION**: `NavigationService.getInstance().getMainNavigation()` would return an entry with `id === <page_segment>` and `href === "/pages/<page_segment>"`.
- **ON_ERROR**: `JMP STEP_99_ABORT`.

### STEP_15_VERIFY

- **ACTION**: run `ReadLints` on every file created or modified during the run. Address any lint error introduced by the scaffold (do NOT fix unrelated pre-existing lints).
- **ACTION**: confirm the route file's `<PageSegmentPascal>Route` default export type-checks against Next.js page signature for this version (read `node_modules/next/dist/docs/` if uncertain — see `AGENTS.md`).
- **ON_ERROR**: fix the specific error, re-run `ReadLints` once, and proceed. If still failing, report the failure to the user verbatim and `JMP STEP_99_ABORT`.

### STEP_16_REPORT

- **ACTION**: print a final summary to the user listing:
  - The four files created (with solution-relative paths).
  - The navigation change (or note that it was skipped).
  - The generated `component_uid`.
  - The URL the new page is reachable at: **`/pages/<page_segment>`**.
- **ACTION**: end the workflow successfully.

### STEP_99_ABORT

- **ACTION**: list every file the workflow created during this run.
- **ASK** (once): "Scaffolding aborted. Delete the files just created? (`yes` / `no`)".
- **ON `yes`**: delete those files (and the `components/pages/<page_segment>/` folder if now empty). Revert the navigation edit if applied.
- **ON `no`**: leave files in place.
- End the workflow.

---

## Path conventions (relative to solution root)

| Concern | Path |
|---|---|
| Route container | `app/pages/<page_segment>/page.tsx` |
| Page component folder | `components/pages/<page_segment>/` |
| Page component | `components/pages/<page_segment>/<page_segment>-page.tsx` |
| Component metadata class | `components/pages/<page_segment>/<component_kebab>.ts` |
| Component React view | `components/pages/<page_segment>/<component_kebab>.tsx` |
| Navigation registry | `lib/navigation/navigation-service.ts` |
| Navigation icons | `lib/navigation/navigation-icon-resolver.ts` |

---

## File templates

> Substitute placeholders **exactly once** per file. Do not leave any `{{ }}` markers in the output.

### TEMPLATE_COMPONENT_CLASS — `components/pages/<page_segment>/<component_kebab>.ts`

```ts
/**
 * Page-private metadata for the {{ComponentName}} component used on the
 * `{{page_segment}}` page. The UID is generated once at scaffold time and is
 * stable for the lifetime of the component.
 */
export class {{ComponentName}}Component {
  public readonly uid: string;
  public readonly name: string;
  public readonly description: string;

  public constructor() {
    this.uid = "{{component_uid}}";
    this.name = "{{component_name}}";
    this.description = "{{component_description}}";
  }
}
```

### TEMPLATE_COMPONENT_VIEW — `components/pages/<page_segment>/<component_kebab>.tsx`

```tsx
import { {{ComponentName}}Component } from "./{{component_kebab}}";

const componentMetadata = new {{ComponentName}}Component();

/**
 * Renders the {{ComponentName}} component on the `{{page_segment}}` page.
 * Page-private: do not import from outside `components/pages/{{page_segment}}/`.
 */
export function {{ComponentName}}View() {
  return (
    <section className="rounded-lg border border-border bg-card p-6 shadow-sm">
      <header className="flex flex-col gap-1">
        <h2 className="text-lg font-semibold text-foreground">
          {componentMetadata.name}
        </h2>
        <p className="text-sm text-muted-foreground">
          {componentMetadata.description}
        </p>
      </header>
      <p className="mt-4 font-mono text-xs text-muted-foreground">
        uid: {componentMetadata.uid}
      </p>
    </section>
  );
}
```

### TEMPLATE_PAGE_COMPONENT — `components/pages/<page_segment>/<page_segment>-page.tsx`

```tsx
import { {{ComponentName}}View } from "./{{component_kebab}}";

/**
 * Props for {@link {{PageSegmentPascal}}Page}.
 */
export interface {{PageSegmentPascal}}PageProps {
  // Add route-supplied props here as the page grows. Keep every prop
  // JSON-serializable so the route container can pass it from the server.
}

/**
 * `{{page_title}}` page. Composes the page-private components that live in
 * `components/pages/{{page_segment}}/`. Route container is at
 * `app/pages/{{page_segment}}/page.tsx`.
 */
export function {{PageSegmentPascal}}Page(_props: {{PageSegmentPascal}}PageProps) {
  return (
    <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight">
          {{page_title}}
        </h1>
        <p className="text-muted-foreground">
          {{page_description}}
        </p>
      </header>
      <{{ComponentName}}View />
    </div>
  );
}
```

### TEMPLATE_ROUTE_FILE — `app/pages/<page_segment>/page.tsx`

```tsx
import { {{PageSegmentPascal}}Page } from "@/components/pages/{{page_segment}}/{{page_segment}}-page";

export default function {{PageSegmentPascal}}Route() {
  return <{{PageSegmentPascal}}Page />;
}
```

> If the page later needs route props, change the route function to `async` and `await props.params` / `props.searchParams` per `aspire.svc/.cursor/rules/nextjs.mdc` §"Next.js App Router (installed major)" — and pass only **JSON-serializable** values into `<{{PageSegmentPascal}}Page />`.

---

## Placeholder derivation

Compute these from the collected inputs before substitution:

- `<page_segment>` = `page_segment` (e.g. `reports`).
- `PageSegmentPascal` = PascalCase of `page_segment` (e.g. `reports` → `Reports`, `audit-trail` → `AuditTrail`).
- `ComponentName` = `component_name` as given (already PascalCase).
- `component_kebab` = kebab-case of `component_name` (e.g. `ReportSummary` → `report-summary`).
- `component_uid` = UUID v4 from `STEP_7_GENERATE_UID`.
- `page_title`, `page_description`, `component_name`, `component_description` are inserted **as plain strings**. If any contain `"` or `\`, escape them for TypeScript string literals before substitution.

---

## JMP label reference

| Label | Role |
|---|---|
| `STEP_1_INPUT_PAGE_SEGMENT` | Collect page route segment |
| `STEP_2_INPUT_PAGE_TITLE` | Collect page title |
| `STEP_3_INPUT_PAGE_DESCRIPTION` | Collect page description |
| `STEP_4_INPUT_COMPONENT_NAME` | Collect component class name |
| `STEP_5_INPUT_COMPONENT_DESCRIPTION` | Collect component description |
| `STEP_6_INPUT_SIDEBAR` | Collect sidebar opt-in |
| `STEP_7_GENERATE_UID` | Generate UUID v4 |
| `STEP_8_CONFIRM` | Recap and confirm |
| `STEP_9_PREFLIGHT` | Re-verify paths and nav id |
| `STEP_10_CREATE_COMPONENT_CLASS` | Write component metadata class |
| `STEP_11_CREATE_COMPONENT_VIEW` | Write React view for the component |
| `STEP_12_CREATE_PAGE_COMPONENT` | Write page component |
| `STEP_13_CREATE_ROUTE_FILE` | Write route container |
| `STEP_14_UPDATE_NAVIGATION` | Update `NavigationService` (conditional) |
| `STEP_15_VERIFY` | Lint + type check |
| `STEP_16_REPORT` | Print summary |
| `STEP_99_ABORT` | Cleanup and exit |

A `JMP` to any label not in this table is invalid — fall back to `STEP_99_ABORT`.
