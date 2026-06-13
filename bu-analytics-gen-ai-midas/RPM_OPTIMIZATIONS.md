# Performance, scalability, and reliability optimizations

This document summarizes backend and frontend optimizations applied to improve speed, Azure compatibility, and UX. It is organized by area.

---

## 1. Data loading, storage, and parallelism

- **Storage abstraction**: Introduced a storage layer (`storage_service.py`) with pluggable backends (in-memory, Parquet, CSV, optional Redis/Chroma) so the same code paths work locally and when SQL/Chroma are provisioned later on Azure.
- **Reduced redundant DataFrame I/O**: Addressed repeated loads and duplicate saves of identical frames; kept intentional multi-version copies only where needed (e.g. Compare Changes: `n` vs `n-1`).
- **Parallel / async work where dependencies allow**: Independent steps (e.g. data load vs validation vs insights) are structured to run concurrently using `asyncio`, `run_in_executor`, `ThreadPoolExecutor`, and `joblib.Parallel` where appropriate.
- **Heavy uploads**: CSV streaming and Arrow/Parquet-oriented paths to scale toward large files (~2 GB) without loading everything into memory in one shot when using the new storage paths.

---

## 2. Data insights (bivariate, correlation, correlation matrix, VIF, IV)

- **Parallel requests**: When multiple insight requests fire together, they use concurrent API calls instead of serial chains.
- **Computation fixes**: Guardrails for edge cases (e.g. empty iterables in numerical insight generation).
- **Caching and persistence**: Server-side `_InsightCache` (with TTL) and client-side caching keyed by dataset so navigation away and back does not always recompute; reduced duplicate calls.
- **Resilience on large variable counts**: Logic tuned so very wide datasets are less likely to hit timeouts or trivial failures.

---

## 3. LLM usage on upload (problem type and variable classification)

- **Non-blocking behavior**: ML problem type classification and variable classification moved to background jobs with polling so long LLM calls do not block the upload step or the whole UI.
- **Instant problem-type UI**: As soon as the problem-type LLM response returns, the UI can show it without waiting for variable classification to finish.
- **Deduplication**: Reduced redundant `classify-variables` / data-dictionary-driven calls so variable classification is not invoked many times for the same dataset unnecessarily.
- **Column info**: Offloaded heavy `calculate_column_info`-style work to executors where appropriate so the UI stays responsive.

---

## 4. Azure timeouts and background jobs

- **Model training as a job**: Training runs as a backend job with polling and persistent `training_jobs` state so Azure App Service’s ~230 s idle limits do not kill long runs.
- **Keep-alive endpoint**: Added `/keepalive`-style traffic pattern support where applicable to reduce idle disconnects during long operations.
- **MEEA (model evaluation) after training**: Full comprehensive evaluation runs in the background after training returns enough artifacts for the Model Training UI, avoiding a long synchronous tail that looked like a “hang” after Optuna.

---

## 5. Model training performance

- **Preprocessing and stats**: Faster `generate_column_stats` (vectorization, hoisting); avoided unnecessary full `DataFrame.copy()` where `assign` or views suffice.
- **Sparse data**: Strategic densification for columns that break numeric ops (e.g. `std` on sparse dtypes).
- **Holdout / split preparation**: Vectorized alignment for train/test holdout construction (major bottleneck on large data).
- **Tree models**: e.g. XGBoost `tree_method='hist'` (and similar tuning) for faster training.
- **Hyperparameter search**: Optuna integration with search spaces tuned for the allowed algorithms (XGBoost, LightGBM, CatBoost, RF, GBM, Logistic Regression).
- **Cross-validation quirks**: e.g. `early_stopping_rounds` cleared for XGBoost/LightGBM before `cross_val_score` when validation folds are incompatible.
- **Logistic regression**: Avoided slow solvers (e.g. `saga`) and capped `max_iter` where appropriate for speed.
- **Parallel training cautions with MEEA**: When using `joblib` with `loky`, child processes do not share the parent’s `_pending_meea_jobs`; MEEA args are returned from workers and registered in the parent so background evaluation still runs correctly.

---

## 6. Model evaluation (MEEA): phased pipeline and APIs

- **Three phases (sequential across phases, parallel across models within a phase)**:
  - **Phase 1 - Performance**: Metrics, ROC/PR, feature importance, error patterns, prediction confidence; writes `{model_id}_eval_phase1.json` and merges into `_comprehensive_evaluation.json`.
  - **Phase 2 - Monotonicity**: Reuses cached predictions from phase 1; decile / KS / monotonicity payloads.
  - **Phase 3 - Granular accuracy**: Reuses cache, then **drops per-model prediction cache** to free memory.
- **Class-level prediction cache**: Keyed by `model_id` between phases so predictions are not recomputed for phases 2 and 3.
- **Large-data sampling**: Stratified sampling caps (e.g. ~50k rows per split) for prediction-heavy paths so evaluation completes in reasonable time on very large datasets.
- **HTTP API**: `GET /model-evaluation/{model_id}/phase/{1|2|3}` returns `200` with data when ready, **`202`** with `{ ready: false }` while waiting-supports clean polling.
- **DB-less Azure**: Listing and fetching evaluation data fall back to reading `models/*.json` when the DB is empty or unavailable.
- **Listing models without waiting for “full” JSON**: `list_evaluated_models_by_dataset` scans both `*_comprehensive_evaluation.json` and `*_eval_phase1.json` so models appear in the UI as soon as phase 1 exists (avoids showing only one model while the second is still mid-pipeline).
- **Persistence of merged comprehensive file**: Each phase merge keeps legacy `GET /model-evaluation/{model_id}` working for older clients.

---

## 7. Frontend: Model Evaluation page

- **Progressive loading**: Polls phase endpoints per model; updates Performance, then Monotonicity, then Granular as data arrives.
- **Session storage safety**: `safeSessionSet` avoids `QuotaExceededError` black screens by progressively stripping large payloads (ROC/PR arrays first, then explainability blobs) and silent fallback when still too large.
- **ROC and naming**: Reads `roc_curve` / `roc_curve_train` from phase 1 payloads; falls back to `explainability_data` for legacy shapes; resolves display names from `algorithm`, `model_name`, etc.
- **Re-fetch when ROC missing**: If cached evaluation data exists but ROC is missing (e.g. stripped for quota), phase 1 is polled again for classification models.
- **Model list refresh**: `fetchModelsSignal` forces list refresh when MEEA completes; cached list is not wiped unnecessarily; **new models from a forced refresh are appended to `selectedModelIds`** so they load without manual re-selection.
- **Persistence**: Dataset-scoped keys for evaluation blobs, model lists, and selected model IDs where appropriate.
- **Monotonicity tab UI**: Wider model `<select>`, flex-wrap for toolbar, and **dropdown options use `algorithm` from API** (not only `name`) so options are populated.

---

## 8. Operational / deployment notes

- Prefer **file + in-memory fallbacks** on Azure when no database is attached; same code paths can later point to SQL/Chroma when provisioned.
- Long operations should use **jobs + polling** rather than a single long HTTP request.
- Avoid assuming **local filesystem paths** for artifacts; use storage service + fallback to in-session buffers where the product allows it.

---

## 9. Key files (reference)

| Area | Representative files |
|------|----------------------|
| MEEA service | `backend/app/services/model_evaluation_service.py` |
| Training + MEEA orchestration | `backend/app/services/model_training_auto_training.py` |
| HTTP routes (phases, list, eval) | `backend/app/api/routes.py` |
| JSON safety | `backend/app/utils/helpers.py` (`safe_json_serialize`) |
| Model evaluation UI | `frontend/src/pages/ModelEvaluationMEEA.tsx` |
| Phase API client | `frontend/src/services/modelEvaluationService.ts` |
| Monronicity tab | `frontend/src/components/MonotonicityTab.tsx` |
| Storage / data layer | `backend/app/services/storage_service.py`, `dataframe_state_manager.py`, `dataset_service.py` |

---
