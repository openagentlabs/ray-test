# Strangler Fig Extraction — Ledger

> Extended schema (C23). Progress tracker for `rearchitetc/refactor_output/`.
> Statuses: `PENDING` → `IN_PROGRESS` → `GAPS_OPEN` → `COMPLETE`

| Work item | Type | Phase | Status | Evidence (path:line) | Gaps |
|-----------|------|-------|--------|----------------------|------|
| Read-only guarantee & output path | readiness-item | 0 | COMPLETE | `strangler-fig-analysis.md:§0.1` | — |
| Repo map (all concerns) | readiness-item | 0 | COMPLETE | `strangler-fig-analysis.md:§0.2` | — |
| Primary extraction targets pinned | readiness-item | 0 | COMPLETE | `model_training_auto_training.py:2466,4776` | — |
| Toolchain inventory | readiness-item | 0 | COMPLETE | `strangler-fig-analysis.md:§0.4` | G-P0-03 ACCEPTED |
| §1 Executive summary + L0 | readiness-item | 1 | COMPLETE | `strangler-fig-analysis.md:§1` | — |
| §2 Stage index + ingest paths | readiness-item | 1 | COMPLETE | `strangler-fig-analysis.md:§2` | G-P1-02 CLOSED |
| Legacy auto-train FE trace | readiness-item | 1 | COMPLETE | `Step6_5ModelTrainingAgent.tsx:2200` | G-P0-02 CLOSED |
| Stage 1 — Objectives (03A–I) | stage | 2 | COMPLETE | `strangler-fig-analysis.md:§3 S1` | G-P0-01 CLOSED |
| Stage 2 — Data Treatment | stage | 2 | COMPLETE | `strangler-fig-analysis.md:§3 S2` | — |
| Stage 3 — Data Insights | stage | 2 | COMPLETE | `strangler-fig-analysis.md:§3 S3` | — |
| Stage 3.5 — Segmentation | stage | 2 | COMPLETE | `strangler-fig-analysis.md:§3 S3.5` | G-P2-02 CLOSED |
| Stage 4 — Feature Engineering | stage | 2 | COMPLETE | `strangler-fig-analysis.md:§3 S4` | — |
| Stage 4.5 — Model Training | stage | 2 | COMPLETE | `strangler-fig-analysis.md:§3 S4.5` | 03J edge cases |
| Stage 5 — Model Evaluation | stage | 2 | COMPLETE | `strangler-fig-analysis.md:§3 S5` | G-P1-03 ACCEPTED |
| Stage 8 — AI Explainability | stage | 2 | COMPLETE | `strangler-fig-analysis.md:§3 S8` | G-P2-01 CLOSED |
| Stage 9 — Model Documentation | stage | 2 | COMPLETE | `strangler-fig-analysis.md:§3 S9` | — |
| Gap remediation pass | readiness-item | 3 | COMPLETE | `strangler-fig-analysis.md:§7` | 4 ACCEPTED only |
| Edge-case register | readiness-item | 3 | COMPLETE | `strangler-fig-analysis.md:§7.1` | E-01–E-14 |
| Seam maps (all stages) | readiness-item | 4 | COMPLETE | `strangler-fig-analysis.md:§3 seam maps` | — |
| Extraction dossier + boundary edges | readiness-item | 5 | COMPLETE | `strangler-fig-analysis.md:§4.5` | — |
| Consolidated variables & hot functions | readiness-item | 5 | COMPLETE | `strangler-fig-analysis.md:§5` | — |
| Consolidated resource model 5M | readiness-item | 5 | COMPLETE | `strangler-fig-analysis.md:§6` | G-P0-01 CLOSED |
| Per-stage compute catalogue | readiness-item | 6 | COMPLETE | `strangler-fig-analysis.md:§8.1` | — |
| C14 projection all units | readiness-item | 6 | COMPLETE | `strangler-fig-analysis.md:§8 C14` | — |
| `train_models_with_iterations` profiling | compute-unit | 6 | COMPLETE | `strangler-fig-analysis.md:§9.2` | — |
| `run_complete_auto_training` profiling | compute-unit | 6 | COMPLETE | `strangler-fig-analysis.md:§9.1` | — |
| Strangler interface contracts | interface | 7 | COMPLETE | `strangler-fig-analysis.md:§9.1–9.3` | — |
| Deferred in-monolith units | interface | 7 | COMPLETE | `strangler-fig-analysis.md:§9.4` | — |
| Auto-training externalization design | training | 8 | COMPLETE | `strangler-fig-analysis.md:§10` | — |
| Model-training modularization | model-module | 9 | COMPLETE | `strangler-fig-analysis.md:§11` | — |
| Test strategy & coverage matrix | test-suite | 10 | COMPLETE | `strangler-fig-analysis.md:§12` | — |
| Synthetic data & fixtures plan | test-suite | 11 | COMPLETE | `strangler-fig-analysis.md:§13` | — |
| Per-artifact test designs | test-suite | 12 | COMPLETE | `strangler-fig-analysis.md:§14` | TC-API-04–06 |
| Integration/scale/regression + traceability | test-suite | 13 | COMPLETE | `strangler-fig-analysis.md:§15` | R1–R9 |
| TEST-PLAN.md assembled | readiness-item | 13 | COMPLETE | `TEST-PLAN.md` | — |
| Baseline characterization design | readiness-item | 14 | COMPLETE | `strangler-fig-analysis.md:§16` | execution pending |
| Security/privacy/governance | readiness-item | 15 | COMPLETE | `strangler-fig-analysis.md:§17` | G-P3-02 ACCEPTED |
| Runtime topology/deployment | readiness-item | 16 | COMPLETE | `strangler-fig-analysis.md:§18` | G-P3-01 ACCEPTED |
| Resilience/rollback/routing | readiness-item | 17 | COMPLETE | `strangler-fig-analysis.md:§19` | FMEA F1–F10 |
| Observability/parity-in-prod | readiness-item | 18 | COMPLETE | `strangler-fig-analysis.md:§20` | — |
| Cut-readiness audit + verdict | readiness-item | 19 | COMPLETE | `strangler-fig-analysis.md:§21` | NO-GO execution |
| Final audit pass | readiness-item | 19 | COMPLETE | `strangler-fig-analysis.md:§21.0` | — |
| Runbook phases 0–19 PHASE sections | readiness-item | — | COMPLETE | `refactor_runbook/phase-*.prompt.md` | — |
