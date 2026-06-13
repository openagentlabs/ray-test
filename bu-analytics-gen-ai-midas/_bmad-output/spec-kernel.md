# SPEC kernel — when to use `bmad-spec`

## Feature slug

Use the **Jira ticket ID** or a **short kebab-case feature name** as `<slug>`. Pick it at intake and reuse it unchanged in:

- `planning-artifacts/<slug>/prd.md`
- `specs/spec-<slug>/` (this skill)
- `planning-artifacts/epics/<slug>/`
- `implementation-artifacts/<slug>/`

Examples: `woe-export`, `MIDAS-42`, `eks-large-csv-scale`.

---

The **`bmad-spec`** skill produces a folder:

```
_bmad-output/specs/spec-<slug>/
  SPEC.md           # five-field kernel
  <companion>.md    # optional load-bearing detail
  .decision-log.md
```

## Five kernel fields

| Field | Purpose |
|---|---|
| **Why** | Problem and user outcome |
| **Capabilities** | What the system must do (testable) |
| **Constraints** | Non-negotiables (auth, memory, AWS, MIDAS rules) |
| **Non-goals** | Explicit exclusions |
| **Success signal** | How we know it worked |

## Best fit by scenario

| Scenario | Use spec? | Notes |
|---|---|---|
| **1 Model Lab** | **Yes** — default | After PRD (`bmad-prd` if needed); produce `traceability.md`; then epics/stories before dev |
| **2 Platform module** | **Yes** | Non-goals must state auth-only boundary |
| **3 Bug fix** | Usually **no** | Use `bmad-investigate`; **regression test required** regardless |
| **4 EKS scale** | **Yes** | Constraints must cite 5 GB / 20 GB and memory rules |

## Relationship to PRD

- Thin idea → `bmad-spec` (express mode) or `bmad-prfaq` (**WB**) then `bmad-prd`
- Large stakeholder doc → `bmad-prd` first, then `bmad-spec` to distill kernel for dev

## Invocation

Fresh chat:

```
Use bmad-spec. Slug: <slug>. Input: _bmad-output/intake/<scenario-folder>/ and _bmad-output/project-context.md.
```

See `.agents/skills/bmad-spec/SKILL.md` for headless vs interactive behavior.

## Downstream consumers

`bmad-create-story`, `bmad-dev-story`, and `bmad-code-review` should read `SPEC.md` and listed companions from frontmatter.
