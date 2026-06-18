# Strangler Fig Extraction — Plan Gap Register & Remediation

> A critical analysis of the prompt set itself (Phases 1–13) for the goal: use the Strangler Fig pattern to extract the target **function** and the **auto-training**, prove drop-in equivalence, and scale from 5M rows to a 1 TB file. This register lists every gap found in the *plan*, its severity, and the remediation now applied. Severity: **Blocker** (cannot safely cut without it) · **High** · **Medium** · **Low**.

## Method
The 13-phase plan was reviewed end-to-end against one question: *if an agent followed every prompt to completion, could a team safely cut the code and ship it?* Gaps are places where the answer was "no" or "not provably." Each gap is remediated by a new phase, a contract change, or a process document — never left open.

## Gap register

| ID | Area | Sev | Gap in the original 1–13 plan | Impact | Remediation |
|----|------|-----|-------------------------------|--------|-------------|
| G01 | Baseline | Blocker | Parity tests (§9, §14-test) reference "golden datasets" but no phase **captures current in-process behaviour** as the ground truth. | Parity has nothing to compare against; "drop-in equivalent" is unprovable. | **Phase 14** — Baseline Characterization Capture; **C25** parity ground truth. |
| G02 | Security | Blocker | Credit-rating **PII** crosses a new network boundary to externalized compute; plan is silent on encryption, IAM, isolation, governance. | Regulatory + breach risk; ARB would reject. | **Phase 15** — Security, Privacy & Governance. |
| G03 | Runtime | High | "Runs externally and scales" is asserted (§9) but no **runtime topology / deployment / packaging** is designed. | No way to actually run or size the externalized compute at 1 TB. | **Phase 16** — Externalized Runtime Topology & Deployment. |
| G04 | Migration safety | High | No production **routing toggle, staged rollout, or instant rollback** between original and externalized paths. | Cannot switch safely or revert on failure. | **Phase 17** — Resilience, Rollback & Strangler Routing. |
| G05 | Verification-in-prod | High | No **observability or live shadow-comparison** to confirm parity on real traffic. | Divergence in production goes undetected. | **Phase 18** — Observability & Parity-in-Production. |
| G06 | Onboarding | High | Phase 1 assumes repo access and target knowledge; no **bootstrap** (repo map, read-only guarantee, primary-target ID). | Inconsistent starts; the singular target "function" is never pinned. | **Phase 0** — Bootstrap & Repo Onboarding. |
| G07 | Closure | High | No **terminal audit / definition-of-done** for the whole extraction (per-phase acceptance only). | No single go/no-go; gaps can slip through. | **Phase 19** — Cut-Readiness Audit; **C26** DoD gate. |
| G08 | Tracking | Medium | Ledger (C12) tracks **stages only**, not compute units, clients, modules, tests, readiness items. | Later phases' work isn't trackable. | **C23** — extended ledger schema. |
| G09 | Failure analysis | Medium | No **FMEA** for the externalized boundary (down/slow/partial/divergent). | Unplanned failure behaviour. | Folded into **Phase 17** (FMEA step). |
| G10 | Evolution | Medium | No **interface versioning / schema evolution** for the contract or the CSV schema over time. | Future schema change silently breaks the client. | **C24** — interface versioning & evolution. |
| G11 | Cost | Medium | No **cost model** for externalized compute at scale. | Budget surprise at 1 TB. | Cost note added to **Phase 16**. |
| G12 | Governance | Medium | No **audit logging / data residency** for regulated data. | Compliance gap. | **Phase 15** (governance step). |
| G13 | Usability | Low | No consolidated **glossary** across three addenda for ARB readers. | Harder to review. | Glossary step in **Phase 19**. |
| G14 | Determinism | Low | Non-determinism (seeds) handled ad hoc; parity can't be asserted on stochastic training. | Flaky parity on auto-training. | **C25** — seeds + parity assertion strategy. |
| G15 | Process | Medium | No **operating instructions** for running the prompts (order, paste, HALT, resume). | Set is not turnkey. | **`00-RUNBOOK.md`**. |
| G16 | Targeting | Medium | The singular **"function"** target is discovered generically, late. | Effort diffuses across all compute units. | **Phase 0** names the primary target up front. |
| G17 | Traceability | Low | Analysis doc has no **changelog** of which phase wrote what. | Hard to audit provenance. | Changelog header in **C22**. |
| G18 | Analysis-vs-execution | Medium | Characterization capture and tests require **running** legacy code, tensioning with "analysis only". | Ambiguous whether the agent should execute. | **Phase 14** + runbook carve-out: prompts **design**, humans **execute** at gates. |

## Outcome
- **0 open Blockers** — both Blockers (G01, G02) now have dedicated phases.
- New phases added: **0, 14, 15, 16, 17, 18, 19** (7).
- New contract material: **ADDENDUM III (C22–C26)**.
- New process docs: **this register** + **`00-RUNBOOK.md`**.
- Residual **ACCEPTED** gaps (intentional, recorded): detailed cloud-vendor selection and final cost figures (G11) are left to Phase 16 execution with real pricing; concrete compliance regime (G12) depends on the deploying org and is captured as a Phase 15 input to confirm.

## Full phase chain after remediation
0 Bootstrap → 1 Frontend flow → 2 Per-stage analysis → 3 Gap remediation → 4 Seam/boundary → 5 Extraction dossier → 6 Compute profiling → 7 Strangler boundary/interface → 8 Auto-training externalization → 9 Model-training modularization → 10 Test strategy → 11 Synthetic data → 12 Component/client/interface tests → 13 Integration/scale/test document → 14 Baseline characterization → 15 Security/privacy → 16 Runtime topology → 17 Resilience/rollback/routing → 18 Observability/parity → 19 Cut-readiness audit.
