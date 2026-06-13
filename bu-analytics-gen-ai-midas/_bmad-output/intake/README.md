# Business document intake

Place **user- or business-provided** materials here before running BMad skills. Agents should read intake files **by reference** (paths), not assume content is in chat history.

## Folder structure

| Folder | Scenario | What to put here |
|---|---|---|
| `01-model-lab/` | Model Lab feature | **Authoritative PRD/requirements** (numbered sections help). Wireframes, API sketches, acceptance criteria. Agents must not contradict these — see `scenarios/01-requirements-traceability.md` |
| `02-platform-module/` | New platform module | Module vision, user personas, auth assumptions, integration diagram (auth only), hosting preference |
| `03-bug-resolution/` | Bugs | One subfolder per ticket, e.g. `03-bug-resolution/MIDAS-1234/` with repro steps, screenshots, logs |
| `04-eks-scalability/` | Scale / large data | Load targets, CSV size, concurrent users, SLOs, incident reports, profiling notes |

## Feature slug (required for parallel features)

Use the **Jira ticket ID** or a **short kebab-case feature name** as the slug. Pick it when you create the intake file and use it **unchanged** through all phases (PRD → SPEC → epics → stories). Examples: `woe-export`, `MIDAS-42`, `segment-comparison`.

The same slug must appear in every artifact path:

| Phase | Path |
|---|---|
| PRD | `_bmad-output/planning-artifacts/<slug>/prd.md` |
| SPEC | `_bmad-output/specs/spec-<slug>/SPEC.md` |
| Backlog | `_bmad-output/planning-artifacts/epics/<slug>/backlog.md` |
| Story | `_bmad-output/implementation-artifacts/<slug>/story-ST-NNN.md` |

If the slug differs between phases, the artifact chain breaks silently — agents will not find upstream inputs.

## Naming conventions

- Use **kebab-case** filenames: `feature-x-requirements.md`, `repro-steps.md`
- Prefer **markdown or PDF** for narrative; **CSV samples** should be small representative snippets (`sample-1000-rows.csv`), not production-sized files
- Redact secrets and PII before commit; intake may be committed to git unless marked sensitive (then use `.gitignore` locally and share via secure channel)

## How skills consume intake

1. Start a **fresh** Cursor chat for each BMad skill.
2. Point the skill at intake paths explicitly, e.g. `_bmad-output/intake/01-model-lab/feature-foo.md`.
3. `bmad-spec` and `bmad-investigate` load these files as primary sources.
4. Outputs go to `_bmad-output/specs/`, `_bmad-output/planning-artifacts/`, or `_bmad-output/implementation-artifacts/` — not back into `intake/` (intake is immutable input unless you version filenames).
5. **Scenarios 1–3:** implementation is not done until tests pass — see `_bmad-output/testing/scenario-test-gate.md`.

## Related

- [_bmad-output/How to use BMAD for each scenario.md](../How%20to%20use%20BMAD%20for%20each%20scenario.md)
- [_bmad-output/scenarios/](../scenarios/)
