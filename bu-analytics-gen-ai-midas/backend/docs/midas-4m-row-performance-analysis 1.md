# MIDAS: 4M-row performance analysis

This document mirrors the Cursor Canvas used for the same analysis. It describes why large-dataset flows can exceed 30 minutes, what to change to reach a **~3–5 minute** end-to-end target on a **16 vCPU / 64 GiB** EKS pod, and where the interactive canvas lives in-repo.

## Canvas (interactive)

| Artifact | Path |
|----------|------|
| **Cursor Canvas source (repo copy)** | `docs/canvas/midas-perf-analysis.canvas.tsx` |
| **Live canvas (IDE-managed copy)** | `~/.cursor/projects/Users-keith334747-Dev003-bu-analytics-gen-ai-midas/canvases/midas-perf-analysis.canvas.tsx` |

Open the `.canvas.tsx` file from the repo in Cursor and use **Canvas** beside the chat for tabs: **Overview**, **Code Fixes**, **EKS Timing**. The repo copy is for review, PRs, and search; the IDE may still prefer the path under `.cursor/projects/…/canvases/` for the built-in canvas runner.

## Assumptions

- **~4 million rows**, **~50 columns**, typical MIDAS training / lock-variables / search paths.
- **EKS pod:** 16 vCPU, 64 GiB RAM; pandas/NumPy with OpenMP; Polars for CSV load where applicable.
- Times are **estimates** from code inspection (not measured benchmarks on your cluster).

## Executive summary

| Area | Status | Notes |
|------|--------|-------|
| Root causes identified | **OK** | 6 issues (3 critical, 2 high, 1 medium) |
| Primary bottleneck | **Risk** | Python GIL: `apply` / `lambda` row work uses ~1 effective core |
| VIF / correlation path | **Risk** | Full-frame work on 4M rows; sampling caps exist but were commented out in places |
| Job serialization | **Warn** | `dataset_job_lock` is correct for OOM prevention; long lock hold = long queue |
| Fix scope | **OK** | No new AWS services; vectorisation + sampling + fewer passes |

**Key insight:** Doubling vCPU **without** code changes does **not** fix the before state, because pure-Python row iteration is GIL-bound. Fixes move work into C (pandas/NumPy) so all cores can help.

## End-to-end time (minutes) — 16 vCPU / 64 GiB

| Pipeline stage | Before (est.) | After (est.) | Primary fix |
|----------------|---------------|--------------|-------------|
| CSV parse & load | ~2 min | ~2 min | Already reasonable (Polars) |
| VIF + correlation (`/training/lock-variables`) | ~8–15 min | ~20–45 s | Re-enable **100k row** sample + optional **var cap** in `calculate_vif_and_correlation` |
| High-cardinality bucketing | ~2–6 min / col | ~1–3 s | Replace `Series.apply(lambda)` with `where` + `isin` |
| OHE "Other" bucketing | ~1–3 min / var | ~1–2 s | Replace `apply(lambda)` with `where` + `isin` |
| Search filter (`row_matches`) | ~5–10 min | ~3–6 s | Replace `DataFrame.apply(..., axis=1)` with per-column `str.contains` + OR masks |
| Numeric coerce (holdout) | ~1–3 min | ~15–30 s | Single pass `pd.to_numeric` instead of double `apply` |
| Model training | ~4 min | ~2.5 min | `n_jobs=16` (and equivalent for tree libs) |
| Job lock wait (if queued) | +100% if stacked | Much smaller after shorter VIF | Long-term: Redis lock (Phase 2) per `job_locks.py` doc |
| **TOTAL** | **~30–40 min** | **~3–5 min** | — |

### EKS stage rollup (same model as canvas)

| Stage | Before (min) | After (min) | Speedup (approx.) |
|-------|--------------|-------------|-------------------|
| CSV parse & load | 2.0 | 2.0 | 1× |
| VIF + correlation | 12.0 | 0.5 | 24× |
| High-cardinality bucketing | 5.0 | 0.1 | 50× |
| OHE "Other" bucketing | 3.0 | 0.08 | 38× |
| Search filter | 8.0 | 0.15 | 53× |
| Numeric coerce | 2.0 | 0.25 | 8× |
| Model training | 4.0 | 2.5 | 1.6× |
| Job lock wait | 2.0 | 2.0 | — |
| **Sum** | **38.0** | **~7.6** | **~5×** (stage sum; overlap in real runs differs) |

Use the **~30–40 min → ~3–5 min** band for narrative; stage sums are conservative and do not double-count parallel overlap.

## RAM (64 GiB pod)

| Component | Before (peak, est.) | After (peak, est.) |
|-----------|---------------------|---------------------|
| Base DataFrame 4M×50 | ~4–6 GiB | ~4–6 GiB |
| VIF / corr working copy | ~6–8 GiB | ~150–200 MB (with sampling) |
| Concurrent two-job overlap | ~30–40 GiB risk | Lower after shorter / smaller working sets |

`dataset_job_lock` exists partly because overlapping heavy jobs on the same dataset blew memory on 4M workloads; sampling and vectorisation reduce how long and how large those peaks are.

## Issues and implementation checklist

### Issue 1 — CRITICAL: `routes.py` search uses `apply(axis=1)`

- **File:** `backend/app/api/routes.py` (approx. lines 16820–16836)
- **Problem:** `sub_df.apply(row_matches, axis=1)` runs Python per row.
- **After:** Build boolean masks with `str.contains(..., case=False, na=False, regex=False)` per column and combine with `functools.reduce(operator.or_, ...)`.
- **Steps:** Remove nested `row_matches`; add `functools`/`operator` imports if missing; add tests for search parity.

### Issue 2 — CRITICAL: `helpers.py` high-cardinality `apply(lambda)`

- **File:** `backend/app/utils/helpers.py` (approx. 1766–1771)
- **Problem:** `Series.apply(lambda x: ...)` over millions of rows.
- **After:** `top_cats_set = set(top_cats)` then `col.where(col.isin(top_cats_set), other="Others")`.
- **Steps:** One localized replacement; run categorical analysis tests.

### Issue 3 — CRITICAL: `feature_engineering_service.py` OHE "Other" path

- **File:** `backend/app/services/feature_engineering_service.py` (approx. 653–656)
- **Problem:** `s_obj.apply(lambda x: ...)` on full length.
- **After:** `s_obj.where(s_obj.isin(cats_set), other="Other")` (avoid redundant `import numpy as np` inside the branch unless the file does not already import numpy at module level).
- **Steps:** Replace one line; run OHE / encoding tests.

### Issue 4 — HIGH: VIF / correlation on full frame

- **Files:** `backend/app/services/model_training_manual_configuration.py`, `backend/app/services/model_training_auto_training.py` (`calculate_vif_and_correlation`)
- **Problem:** Imputation and matrix work on full 4M rows; sampling / var caps may be commented or bypassed.
- **After:** Stratified or random **sample** (e.g. 100k rows) for VIF/correlation-only work; optional cap on feature count for O(p²) correlation cost; document product acceptance for “metrics on sample”.
- **Steps:** Align both services; add/refresh unit tests; log sample size in structured logs.

### Issue 5 — HIGH: `dataset_job_lock` serialisation

- **File:** `backend/app/services/job_locks.py` (behaviour); callers in `routes.py` and training runners.
- **Problem:** Correct mutual exclusion, but wall-clock grows when jobs queue.
- **After (short term):** Shorter critical sections via Issues 1–4 and 6.
- **After (medium term):** Phase 2 cross-pod lock (e.g. Redis `SETNX`) as described in the module docstring—requires explicit infra ADR per MIDAS architecture rules.

### Issue 6 — MEDIUM: double `apply(pd.to_numeric)`

- **File:** `backend/app/services/model_training_auto_training.py` (approx. 2701–2727)
- **Problem:** Two passes over overlapping numeric columns.
- **After:** One combined column list and one coerce pass; keep median imputation only where required.
- **Steps:** Refactor block; run holdout / scoring tests.

## Implementation order (recommended)

1. **VIF sampling + var cap** (both services) — largest wall-clock and RAM win, often few lines.
2. **`helpers.py` vectorisation** — very small diff.
3. **`feature_engineering_service.py` vectorisation** — very small diff.
4. **`routes.py` search vectorisation** — slightly more test surface.
5. **`model_training_auto_training.py` single coerce pass** — medium refactor.
6. **Redis lock (Phase 2)** — architecture change; needs ADR and pipeline deploy, not a same-day code-only fix.

## Related code references (repository)

| Topic | Location |
|-------|----------|
| Lock-variables API | `backend/app/api/routes.py` — `POST /training/lock-variables` |
| Per-dataset job lock | `backend/app/services/job_locks.py` — `dataset_job_lock` |
| Dataset load cache | `backend/app/services/dataset_service.py` — `_SharedDataFrameLoadCache` |

## Document history

- **2026-05-12:** Initial write from performance / canvas work; EKS 16 vCPU / 64 GiB scenario included.
