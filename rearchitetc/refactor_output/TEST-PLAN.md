# MIDAS Strangler Fig Extraction — Test Plan

> Standalone deliverable (C21), assembled from `strangler-fig-analysis.md` §12–§15.
> **Scope:** Prove drop-in equivalence of externalized `run_complete_auto_training` + `train_models_with_iterations`.

---

## 1. Scope & objective

**Fully testable** means: every testable unit in §12 has defined oracles, fixtures, and at least one covering test; parity gate `externalized(input) == original(input)` is automatable on golden baselines (§16); CI smoke suite blocks cut.

**Out of scope:** Upload/S3 ingest parity, agent QC chat flows, production deployment execution (human gates).

**Edge cases:** Cross-cutting scenarios E-01–E-14 in analysis §7.1 must have at least one covering test where automatable.

---

## 2. Testable-unit inventory (C19)

| ID | What it is | Must verify | Oracle | Fixtures | Isolation |
|----|------------|-------------|--------|----------|-----------|
| TU-TRAIN | `train_models_with_iterations` | Metrics, feature lists, model count | Golden JSON | FX-SMALL, FX-5M | Mock S3; real sklearn |
| TU-AT-ORCH | `run_complete_auto_training` | End-to-end pipeline output | Golden JSON | FX-SMALL, FX-5M | Mock DFSM with parquet |
| TU-CLIENT | StranglerTrainingClient | Dispatch + error parity | Golden pairs | FX-SMALL | Mock external HTTP |
| TU-API-RUN | `POST /auto-training/run` | Job lifecycle schema | OpenAPI contract | FX-SMALL via API | TestClient + auth |
| TU-PREPROC | `preprocess_data` | Matrix shape, encoders | Property invariants | FX-EDGE | Unit only |
| TU-STAGE45-E2E | Stage 4.5 path | FE → API → results | E2E success criteria | FX-MEDIUM | Full stack staging |

---

## 3. Test taxonomy matrix (C18)

| Unit | Unit | Contract | Parity | Integration | E2E | Property | Negative | Scale | Regression |
|------|:----:|:--------:|:------:|:-----------:|:---:|:--------:|:--------:|:-----:|:----------:|
| TU-TRAIN | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |
| TU-AT-ORCH | ✓ | ✓ | ✓ | ✓ | — | — | ✓ | ✓ | ✓ |
| TU-CLIENT | ✓ | ✓ | ✓ | ✓ | ✓ | — | ✓ | — | ✓ |
| TU-API-RUN | — | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ |
| TU-PREPROC | ✓ | ✓ | — | — | — | ✓ | ✓ | — | ✓ |
| TU-STAGE45-E2E | — | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ |

---

## 4. Synthetic data & fixtures (C20)

| Fixture | Rows | Seed | Location (planned) | Use |
|---------|------|------|------------------|-----|
| FX-SMALL | 10,000 | 42 | `tests/fixtures/fx_small.csv` | Unit, parity, smoke |
| FX-MEDIUM | 500,000 | 42 | `tests/fixtures/fx_medium.csv` | Integration, E2E |
| FX-5M | 5,000,000 | 42 | `tests/fixtures/fx_5m.csv` | Scale, baseline |
| FX-EDGE | 1,000 | 99 | `tests/fixtures/fx_edge.csv` | Negative tests |
| FX-GOLDEN | 50,000 | 42 | `baselines/golden/` | Parity oracle capture |

**Schema (synthetic fixture — test only):** `customer_id`, `target_default`, 20 numeric, 8 categorical. Production CSV is upload-defined (`routes.py:2538-2583`).

**Safety:** Synthetic only; no production PII.

---

## 5. Per-artifact test cases

### 5.1 TU-TRAIN

| Case | Input | Expected | Oracle |
|------|-------|----------|--------|
| TC-TRAIN-01 | FX-SMALL, logistic, 3 features | classification, ≥1 model | baseline JSON |
| TC-TRAIN-02 | FX-EDGE with dup keys | stable `used_features` | exact list match |
| TC-TRAIN-03 | weight column | metrics differ from unweighted | tolerance vs golden |
| TC-TRAIN-04 | cancel_check mid-fit | failed job, cancel in error | status contract |

### 5.2 TU-CLIENT

| Case | Input | Expected | Oracle |
|------|-------|----------|--------|
| TC-CLI-01 | local backend | identical to direct call | byte-identical JSON |
| TC-CLI-02 | external mock | matches golden | parity |
| TC-CLI-03 | worker timeout | same exception surface | error class match |

### 5.3 TU-API-RUN

| Case | Input | Expected | Oracle |
|------|-------|----------|--------|
| TC-API-01 | missing dataset_id | HTTP 400 | OpenAPI |
| TC-API-02 | duplicate dataset train | same job_id returned | `routes.py:15593` |
| TC-API-03 | poll to completion | results keys present | schema |
| TC-API-04 | cancel completed job | `success: false` | `routes.py:15834-15840` |
| TC-API-05 | cancel running job | `cancelled: true` | `routes.py:15858-15868` |
| TC-API-06 | upload file > MAX_FILE_SIZE | HTTP 400 | `routes.py:2479-2481` |

---

## 6. Integration, E2E & scale plan

| ID | Type | Description | Pass criteria |
|----|------|-------------|---------------|
| IT-01 | Integration | Client ↔ mock worker | Parity on FX-SMALL |
| IT-02 | Integration | API ↔ in-process train | Job completes, valid JSON |
| IT-03 | Integration | Upload + train FX-MEDIUM | Model in list API |
| E2E-01 | E2E | Login → upload FX-SMALL → train | < 5 min |
| E2E-02 | E2E | Wizard steps 1→4.5 FX-MEDIUM | training_results in session; mtaFlowGate |
| E2E-03 | E2E | Session → Step 9 docs | training_results present |
| PERF-01 | Scale | FX-5M external worker | RSS < 8 GB |
| PERF-02 | Scale | FX-5M wall time | < 2× baseline |
| smoke-parity | Regression | TC-TRAIN-01 + TC-CLI-01 + TC-API-02 | green every PR |

---

## 7. Coverage targets & exit criteria

| Metric | Target |
|--------|--------|
| Parity cases | 100% pass on FX-SMALL + FX-5M baselines |
| Contract tests | All TU-API-RUN cases (TC-API-01–06) green |
| Traceability | 100% requirements R1–R9 covered (analysis §15.5) |
| Edge cases | E-04–E-06 covered by TC-API-02/04/05; E-02 by TC-API-06 |
| Smoke runtime | < 10 minutes |
| Scale | PERF-01/02 green in staging |

**Cut blocked until:** §16 baselines captured **and** all exit criteria green **and** C26 checklist (analysis §21) execution items signed off.

---

## 8. Traceability matrix

| Req ID | Requirement | Test(s) |
|--------|-------------|---------|
| R1 | `externalized == original` | TC-TRAIN-01, TC-CLI-01/02, IT-01 |
| R2 | API contract preserved | TC-API-01–06 |
| R3 | 5M scale envelope | PERF-01, PERF-02 |
| R4 | Cancel semantics | TC-TRAIN-04, TC-API-05 |
| R5 | Job deduplication | TC-API-02 |
| R6 | E2E wizard training | E2E-01, E2E-02 |
| R7 | Session → documentation handoff | E2E-03 |
| R8 | Edge-case register E-01–E-14 | TC-API-04–06, §7.1 |
| R9 | mtaFlowGate navigation | E2E-02 |
