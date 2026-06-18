# Strangler Fig Extraction — Phase 1 Prompt: Frontend Flow Discovery

> **Self-contained Cursor agent prompt.** It carries the full requirements (the CONTRACT below) **and** consumes the file produced by earlier phases, then enriches that single file. Run this first — it creates the analysis file the others build on.

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

## PHASE 1 — Frontend Flow Discovery
**Run order:** 1 of 19 · **Inputs:** codebase + analysis file (§0 present) + ledger · **Enriches:** §1–§2

**Precondition:** §0 repo map and primary extraction targets exist. If absent, **HALT**.

**Objective:** derive the user flow from the React SPA (frontend leads); produce the stage index and cross-stage state map that Phase 2 will deepen.

**Actions**
1. Trace login → project selection → Model Builder breadcrumb order from React components.
2. Build §2 stage index: step id, label, component, API calls, navigation gates, status.
3. Document cross-stage FE state carriers (`sessionStorage`, React state) with `path:line`.
4. Write §1 executive summary + **L0** full-flow Mermaid diagram.
5. Add **L2** `sequenceDiagram` for the canonical happy path (§2.2).
6. Trace legacy vs production auto-training FE paths; close or register G-P0-02.

**Gap pass (C11):** any stage not locatable in FE → register in §7.

**Acceptance criteria**
- [ ] §1 executive summary + valid L0 diagram.
- [ ] §2 stage index complete (all breadcrumb stages) with evidence-cited APIs.
- [ ] Cross-stage state table + L2 sequence diagram present.

**Write-back:** §1–§2 + ledger. Then proceed to Phase 2.
