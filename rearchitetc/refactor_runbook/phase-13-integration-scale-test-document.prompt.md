# Strangler Fig Extraction — Phase 13 Prompt: Integration, Scale & Test Document

> **Self-contained Cursor agent prompt** (verification & testing set). Carries the full base CONTRACT, ADDENDUM I (scalable-compute), and ADDENDUM II (testing); consumes the file produced by earlier phases, then enriches that single file. Requires §12–§14 as input; produces the standalone TEST-PLAN.md.

---

## CONTRACT — shared requirements (identical in every phase prompt; read fully before phase work)

### C1 · Mission
You are a **legacy-extraction architect** applying the **Strangler Fig pattern** to isolate one self-contained block of a Python backend so it can be extracted from the monolith. You reverse-engineer the system **stage by stage** (driven by the frontend user flow), characterise every data and control dependency, and produce a **seam map** and **extraction dossier** that define where a clean boundary can be cut. **Analysis and documentation only — never refactor or move application code.**

### C2 · System under analysis
- **Backend:** Python app exposing **FastAPI** endpoints.
- **Frontend:** **React + Vite** SPA; the source of truth for the user flow.
- **Flow:** login → upload **CSV of customer credit-rating data** → file **streamed/chunked to S3** → later **loaded from S3 into backend RAM as a pandas DataFrame** → user advances through **stages shown in a UI breadcrumb** (upload → … → *data treatment* → … → **model training**).
- Each breadcrumb entry is a **stage** — the unit of analysis.

### C3 · Definitions
- **Seam** — a point where behaviour can change without editing code there (interception point: function boundary, API edge, I/O edge).
- **Boundary** — a closed interface where data crosses in/out of a candidate block (inputs, outputs, side-effects, owned state).
- **Extraction candidate** — a block whose boundary is clean enough to lift behind a facade / anti-corruption layer.
- **Stage** — one breadcrumb step.

### C4 · Operating rules
1. **Evidence over assumption** — every code claim cites `path:line`; unknowns become gaps, never invented.
2. **No code mutation** — only write the analysis file and ledger.
3. **Trace data by reading code** across module/function boundaries, not by name inference.
4. **Frontend leads** — derive intent/stages from React first, then map to API and backend internals.
5. **Determinism** — stages in breadcrumb order; sub-steps in listed order.
6. **Concise & structured** — tables/lists over prose; no filler.
7. **Resource math explicit** — every figure shows assumptions and arithmetic; fixed scenario = **5,000,000 records**.
8. **All diagrams** are valid, self-contained **Mermaid**.

### C5 · Input & file-write protocol (chaining)
- **Inputs:** the codebase, **and** the existing `ANALYSIS/strangler-fig-analysis.md` + `ANALYSIS/LEDGER.md` when they exist. **Read them fully before writing.**
- **Single source of truth:** one file `ANALYSIS/strangler-fig-analysis.md`. Enrich it; never fork copies.
- **Idempotent enrichment:** update sections in place by heading. If a section exists, refine/extend it — do not duplicate. If absent, create it in the correct TOC position.
- **Never destroy prior content** unless correcting a proven error; when correcting, note what changed and why.
- **Preconditions:** if expected prior content is missing, run the minimal prerequisite **or HALT with a precise message naming what is missing.** Never fabricate to proceed.
- **After every sub-step:** update `ANALYSIS/LEDGER.md`.

### C6 · Output document schema (TOC of `strangler-fig-analysis.md`)
1. Executive summary + L0 full-flow diagram
2. Stage index (table with status)
3. Per-stage sections — each with 03A–03I, then gap register, then seam map
4. Extraction dossier
5. Consolidated variable & hot-function appendix
6. Consolidated resource model (5M records)
7. Open-questions / accepted-gaps register

### C7 · Stage completeness — sub-steps 03A–03I (shared definition)
A stage is complete only when all are present and evidence-cited:
- **03A Purpose & UX** — what it is for, how/why the user uses it; each component's role, input type, displayed type.
- **03B Data provenance** — each datum classified **user-entered / user-selected / derived**; for derived, source + how mutated.
- **03C State & storage** — variable table (columns in C8) for FE+BE; mark copies, derived structures, types, purpose.
- **03D Order of operations** — exact event sequence FE→API→BE→response→FE.
- **03E API mapping** — each endpoint: method, path, request/response shape, FE call site.
- **03F Backend mapping** — each endpoint's inputs mapped to FE/internal vars; full internal state flow.
- **03G Diagrams L0–L3** (see C9).
- **03H Variable inventory & hot functions** — consolidated FE+BE vars for the stage; key/hot functions on the data-heavy path.
- **03I Resource model** — memory & CPU max-over-time at 5M records (see C10).

### C8 · Variable table columns
`| Variable | Side (FE/BE) | Type | Where stored | Created from | Mutated? (copy/in-place) | Produces new data? | Used by | Evidence (path:line) |`

### C9 · Diagram conventions (multi-zoom, all Mermaid)
Same flow at four zoom levels:
- **L0 100,000 ft** — `flowchart`, stage-in-context, one box per major actor.
- **L1 1,000 ft** — `flowchart`, component ↔ endpoint ↔ subsystem.
- **L2 100 ft** — `sequenceDiagram`, request lifecycle FE→API→services→S3/RAM→response.
- **L3 20 ft** — call graph (`flowchart`/`graph`), nodes = functions/components, edges labelled with what is passed.
- State lifecycle where useful — `stateDiagram-v2`. Every diagram in a fenced ```mermaid block.

### C10 · Resource model method (fixed: 5,000,000 records)
1. **Assumptions:** column count, per-column dtype, mean row bytes, pandas overhead multiplier (derive from CSV code + credit schema; flag unknowns as gaps).
2. **Raw size** = rows × mean_row_bytes.
3. **In-RAM DataFrame** = raw × overhead multiplier (state it; object/string cols are heavy).
4. **Copy & derived overhead** = sum of every copy/derived frame in the stage, each as a multiple of base.
5. **Peak memory** = base + concurrently-live copies/derived.
6. **CPU profile** = passes over data × cost class (vectorised / row-wise / Python-loop) per hot function.
7. **Over time** = short timeline of mem & CPU across stage lifecycle (ingest→load→transform→release).
- Output table: `| Phase | Live structures | Mem est. | CPU class | Assumptions |`

### C11 · Gap discipline (EVERY phase fills gaps)
1. **Identify** — missing/unverified info, classified by type: UX intent, data provenance, storage detail, API contract, internal flow, resource input, seam evidence.
2. **Fill** — read the code to close each gap; update the relevant section.
3. **Register** — any gap that cannot be closed goes to the Open-questions register as **CLOSED** (with evidence) or **ACCEPTED** (with reason). **No silent gaps.**

### C12 · Ledger format (`ANALYSIS/LEDGER.md`)
`| Stage | 03A-I | Gaps | Seam | Status |`
Statuses: `PENDING → IN_PROGRESS → GAPS_OPEN → COMPLETE`. Update after each sub-step.
---

## CONTRACT ADDENDUM — scalable-compute externalization (identical in Phases 6–9; extends the base CONTRACT, does not replace it)

### C13 · TOC extension (sections this set appends to `strangler-fig-analysis.md`)
- **8. Scalable-compute catalogue** — per stage: compute units, hotness at 5M, scale curve to the row count of a 1TB file.
- **9. Strangler interface contracts** — per compute unit: cut boundary, exact input/output interface, dependency closure, the drop-in strangler client, parity contract.
- **10. Auto-training externalization** — the auto-training compute treated exactly as §8 + §9.
- **11. Model-training modularization plan** — each model training separated into an independent module behind the strangler client.
- **Section 7 remains** the document-wide open-questions / accepted-gaps register; every phase keeps registering gaps there.

### C14 · Scale model (5,000,000 rows → rows in a 1 TB file)
1. Derive `mean_row_bytes` from the CSV schema/handling code (same basis as C10); state the byte basis.
2. `rows_per_1TB = 1,000,000,000,000 / mean_row_bytes` (state TB vs TiB choice; show the number).
3. Project each compute unit's **CPU time** and **peak memory** at checkpoints: **5M, 25M, 100M, rows@1TB**.
4. Classify **growth**: O(n) / O(n log n) / O(n²) / memory-bound / IO-bound; name the unit that **dominates at 1TB**.
5. Show arithmetic; flag every assumption as a gap.
- Table: `| Compute unit | Metric | 5M | 25M | 100M | rows@1TB | Growth class |`

### C15 · Compute-unit definition
A **compute unit** is a cohesive block whose cost scales with row count. Document each as:
- **id/name**, **location** (`path:line`), **what it computes**, **algorithmic shape & passes over data**.
- **Inputs** (types/shape/source), **Outputs** (types/shape/consumer).
- **Dependencies** — libraries, config, env, I/O (S3/DB/network), and hidden global/shared state.
- **Hotness at 5M** — CPU class + peak memory via C10; mark the hottest unit per stage.
- **Growth class** — per C14.

### C16 · Strangler client contract (the drop-in)
The **strangler client** replaces an in-process compute call while preserving a **byte-for-byte identical interface**, dispatching instead to externalized compute that runs independently and scales. Document:
- **Exact input interface** — signature/schema, types, ordering, units, invariants, null/edge handling.
- **Exact output interface** — signature/schema, types, invariants; **must equal the original output for the same input.**
- **Parity contract** — `externalized(input) == original(input)`; define **characterization tests** (golden input/output pairs captured at the boundary) that prove drop-in equivalence before any cut.
- **Dispatch** — how the client invokes the externalized compute (call protocol, payload/framing), plus error / timeout / retry / back-pressure semantics and idempotency.
- **Invariants for true drop-in** — same exceptions surfaced, and side-effects either preserved or explicitly relocated and documented.
- The externalized compute is **designed only** here — not implemented.
---

## CONTRACT ADDENDUM II — verification & testing (identical in Phases 10–13; extends the base CONTRACT and ADDENDUM I, does not replace them)

### C17 · TOC extension (sections this set appends to `strangler-fig-analysis.md`)
- **12. Test strategy & coverage matrix** — every testable unit × test type, with oracles and exit criteria.
- **13. Synthetic data & fixtures** — schema-faithful, seeded generators and fixture sets at every scale.
- **14. Per-artifact test designs** — concrete cases for each component, strangler client, and interface.
- **15. Integration, scale & regression** — end-to-end + scale validation + the traceability matrix.
- **Standalone deliverable:** `ANALYSIS/TEST-PLAN.md` (C21), assembled in the final phase.
- **Section 7 remains** the document-wide open-questions / accepted-gaps register.

### C18 · Test taxonomy (shared — every test type must be considered for each unit)
- **Unit** — a single function/method in isolation; proves local correctness.
- **Interface / contract** — input schema/type/ordering/invariants accepted; output schema/type/invariants produced.
- **Parity / characterization** — `strangler_client(input) == original(input)` and `externalized(input) == in_process(input)` on golden pairs; proves drop-in equivalence.
- **Integration** — strangler client ↔ externalized compute wired together.
- **End-to-end (stage)** — full stage path FE-contract → API → compute → output.
- **Property-based** — invariants that must hold across generated inputs.
- **Negative / edge** — nulls, out-of-range, empty, duplicate, malformed, encoding.
- **Performance / scale** — behaviour and resource envelope across 5M → rows@1TB (thresholds from C14).
- **Regression / smoke** — locks fixed behaviour; fast gate before a cut.

### C19 · Testable-unit definition
A **testable unit** is each: extracted **compute unit** (C15), each **strangler client** (C16), each **interface** (input contract + output contract), each **model-training module** (§11), and each **integrated stage path**. Document per unit:
- **id / what it is**, **what must be verified**, **oracle** (parity / golden dataset / property invariant / spec), **required fixtures**, **applicable test types** (from C18), **isolation needs** (how to test it standalone — fakes/stubs for I/O, S3, DB, model libs).

### C20 · Synthetic data principles
- **Schema-faithful** to the credit-rating CSV: columns, types, ranges, distributions, and relationships derived from code/§3 (flag unknowns as gaps).
- **Deterministic** — seeded generation; same seed → same data, for reproducible parity.
- **Scale-parameterised** — fixtures at 5M / 25M / 100M / rows@1TB-equivalent (tie to C14 byte basis).
- **Edge/adversarial fixtures** — nulls, out-of-range, empty, duplicate, malformed rows, mixed encodings.
- **Golden datasets** — captured original boundary I/O pairs that drive parity tests.
- **Safety** — synthetic only; **no real PII**; document provenance.

### C21 · Test Document spec (`ANALYSIS/TEST-PLAN.md`, standalone deliverable)
Assembled from §12–§15. Structure:
1. Scope & objective (what "fully testable" means here).
2. Testable-unit inventory (C19).
3. Test taxonomy applied (C18) — unit × type matrix.
4. Synthetic data & fixtures plan (C20).
5. Per-artifact test cases — component, client, interface (inputs, expected outputs, oracle).
6. Integration, end-to-end & scale plan.
7. Coverage targets & **exit criteria** (the gate that must pass before a cut).
8. **Traceability matrix** — requirement / interface / parity contract → covering test(s).
---

## PHASE 13 — Integration, Scale & Test Document
**Run order:** 13 of 13 · **Inputs:** codebase **+** analysis file (§12–§14 present) **+** ledger · **Enriches:** §15 + standalone `ANALYSIS/TEST-PLAN.md`

**Precondition:** §12–§14 exist. If absent, **HALT** naming what is missing.

**Objective:** design **integration, end-to-end, scale and regression** testing, then assemble the standalone **Test Document (C21)**.

**Actions**
1. **Integration tests** — strangler client ↔ externalized compute wired together; verify the parity contract holds across the boundary, not just in isolation.
2. **End-to-end (stage)** — full stage path FE-contract → API → compute → output, then cross-stage flow.
3. **Performance / scale tests** — validate behaviour and the resource envelope from 5M → rows@1TB; thresholds derived from the C14 projections; assert the dominating unit stays within budget.
4. **Regression / smoke + CI gate** — the fast suite that must pass before any cut is allowed; **parity is the gate**.
5. **Traceability matrix** — each requirement / interface / parity contract → its covering test(s); flag any uncovered item as a gap.
6. **Assemble `ANALYSIS/TEST-PLAN.md`** per the C21 structure from §12–§15.

**Gap pass (C11):** uncovered requirements, missing scale thresholds, undefined CI gate — fill or register.

**Acceptance criteria**
- [ ] Integration, end-to-end, scale, and regression designs complete.
- [ ] Traceability matrix with no uncovered requirement (or each registered).
- [ ] `ANALYSIS/TEST-PLAN.md` assembled and matching C21.

**On finish:** output a one-paragraph summary, the paths to `strangler-fig-analysis.md` and `TEST-PLAN.md`, the coverage/exit-criteria status, and any residual ACCEPTED gaps. Then **stop**.
