# Planning artifacts

BMad planning skills write here (`_bmad/bmm/config.yaml` → `planning_artifacts`).

## Feature slug

Parallel features each get `planning-artifacts/<slug>/`. Use the **Jira ticket ID** or **kebab-case name** chosen at intake — same slug in `specs/spec-<slug>/` and `epics/<slug>/`. See [_bmad-output/intake/README.md](../intake/README.md#feature-slug-required-for-parallel-features).

## When files appear

| Skill | Typical output |
|---|---|
| `bmad-prd` | `prd-<feature>.md` |
| `bmad-ux` | `ux-<feature>.md` |
| `bmad-create-architecture` | `architecture-<module>.md` |
| `bmad-technical-research` | `research-<topic>.md` |

## Templates (copy before first run)

Use `templates/` as starting points — skills may overwrite with richer content:

- `templates/prd-outline.md`
- `templates/ux-spec-outline.md`
- `templates/architecture-outline.md`
- `templates/epic-backlog-template.md`
- `templates/traceability-matrix-template.md`

## Epics (scenario 1)

New Model Lab features produce:

```
planning-artifacts/epics/<slug>/
  backlog.md
  traceability-matrix.md
  party-reviews/
    backlog-roundtable.md      # bmad-party-mode after backlog approval
    pre-dev-ST-001.md          # before each bmad-dev-story
    pre-merge-ST-001.md        # optional before code review
```

Template: `templates/party-review-synthesis-template.md`

## Tests

Planning alone does not satisfy the scenario test gate. Tests are required after `bmad-dev-story` / `bmad-quick-dev` per `_bmad-output/testing/scenario-test-gate.md`.
