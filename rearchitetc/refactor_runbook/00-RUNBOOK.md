# Strangler Fig Extraction — Master Runbook

> The operating manual for the prompt set. It tells you how to run all 20 phase prompts (0–19) in Cursor to produce one analysis document plus a test plan, prove drop-in equivalence, and reach a go/no-go on cutting the target **function** and **auto-training** out of the monolith. **The prompts analyze and design; they never modify application code. Execution steps (running tests, capturing baselines, deploying) are performed by you at the marked gates.**

## 1 · What you end up with
- **`ANALYSIS/strangler-fig-analysis.md`** — the single enriched analysis document (§0–§21).
- **`ANALYSIS/TEST-PLAN.md`** — the standalone test document (from Phase 13).
- **`ANALYSIS/LEDGER.md`** — progress tracker (extended schema, C23).
- A **Go/No-Go verdict** with a cut-readiness checklist (Phase 19).

## 2 · One-time setup
1. Open the repo in Cursor on a **read-only branch** (e.g. `analysis/strangler-fig`). The agent must not commit code changes.
2. Create an empty `ANALYSIS/` folder (or use `rearchitetc/refactor_output/` if directed by the operator).
3. Keep all 20 prompt files somewhere accessible (e.g. `.cursor/prompts/`).

## 3 · The core loop (repeat for every phase, in order)
1. **Open a fresh agent chat.** Fresh context per phase keeps quality high.
2. **Paste the whole phase prompt** (each is self-contained — it carries the full CONTRACT + addenda it needs).
3. **Point the agent at the repo and `ANALYSIS/`.** Say: "Inputs are this repo and `ANALYSIS/`. Follow the prompt; enrich `ANALYSIS/strangler-fig-analysis.md` and update `ANALYSIS/LEDGER.md`."
4. **Let it run to its acceptance criteria.** It writes its section(s) and updates the ledger.
5. **Review before moving on:** skim the new section, confirm evidence is `path:line`, check the ledger row, and read the phase's gap register. Fix anything thin by asking the agent to deepen that sub-step.
6. **Advance** to the next phase only when the current one's acceptance criteria are met.

## 4 · Run order & dependencies
Run strictly in this order; each phase's **Precondition** names what must already be in the file.

| # | Phase | Produces | Needs first |
|---|-------|----------|-------------|
| 0 | Bootstrap & onboarding | §0, scaffold, ledger | repo only |
| 1 | Frontend flow discovery | §1–§2 | §0 |
| 2 | Per-stage deep analysis | §3 (03A–I) | §2 |
| 3 | Gap analysis & remediation | gap closure, §7 | §3 |
| 4 | Seam & boundary | seam maps | §3 closed |
| 5 | Extraction dossier | §4 | §4 |
| 6 | Compute profiling | §8 | §4 seams |
| 7 | Strangler boundary/interface | §9 | §8 |
| 8 | Auto-training externalization | §10 | §8–§9 |
| 9 | Model-training modularization | §11 | §10 |
| 10 | Test strategy & coverage | §12 | §9 (+§11) |
| 11 | Synthetic data & fixtures | §13 | §12 |
| 12 | Component/client/interface tests | §14 | §12–§13 |
| 13 | Integration/scale + test doc | §15, `TEST-PLAN.md` | §12–§14 |
| 14 | Baseline characterization | §16 | §9, §13 |
| 15 | Security/privacy/governance | §17 | §9 |
| 16 | Runtime topology/deployment | §18 | §8, §9, §15 |
| 17 | Resilience/rollback/routing | §19 | §9, §18 |
| 18 | Observability/parity-in-prod | §20 | §16, §17 |
| 19 | Cut-readiness audit | §21, verdict | §1–§20 + TEST-PLAN |

Phases **2, 6, 7, 10, 12** loop over each stage / compute unit / artifact — let the agent finish all items before advancing.

## 5 · Handling a HALT
A phase HALTs when its precondition isn't met (it names what's missing). Don't override it — go back, run the missing phase (or deepen the thin section), then re-run the halted phase. HALT is the safety mechanism that stops seams being drawn over open gaps.

## 6 · Design vs execution gates (important)
The prompts **design** these; **you execute** them as explicit gates:
- **After Phase 14:** actually capture the golden baselines from the running legacy code (read-only) per the §16 design. Parity has no ground truth until this is done.
- **After Phase 13 + 14:** run the unit / contract / parity test suites; confirm green.
- **After Phase 16:** stand up the externalized runtime in a non-prod environment.
- **During Phase 17/18:** run shadow → canary → full, watching the live parity comparison; auto-rollback on divergence.
- **Phase 19 gate:** do not cut until the C26 checklist is fully green.

## 7 · Resuming later
The ledger (`ANALYSIS/LEDGER.md`) is the resume point. Open it, find the first row not `COMPLETE`, and start the core loop at that phase. Because each prompt is self-contained and reads the existing file, you can stop and resume across days without losing state.

## 8 · Quality bar (what "gold standard" means here)
- Every claim about the code cites `path:line`; unknowns are registered, never invented.
- Every boundary has an explicit **parity contract** (`externalized == original`) backed by captured baselines.
- No silent gaps — §7 holds every gap as CLOSED or ACCEPTED-with-reason.
- The cut is reversible (Phase 17) and observable (Phase 18) before it is permanent.

## 9 · Definition of done (C26 — the cut gate)
Cut only when ALL are green: baseline characterized · parity passing · security signed off · runtime deployable · routing toggle + proven rollback · observability + live parity · tests at exit criteria · all gaps closed/accepted. Phase 19 produces this checklist and the single **Go/No-Go** verdict.

## 10 · Glossary pointer
Key terms are defined in the contract carried by every prompt: Seam/Boundary/Extraction candidate (C3), Compute unit (C15), Strangler client + parity (C16), Testable unit (C19), Interface versioning (C24), Parity ground truth (C25), Cut-readiness (C26). Phase 19 consolidates these into a single index in the analysis doc.
