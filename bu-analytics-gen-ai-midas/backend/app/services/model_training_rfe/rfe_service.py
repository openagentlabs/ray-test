"""
RfeService - orchestrates the RFE loop.

Contract: `RfeService.run(job_id)` is the single entrypoint. It:
  1. Rehydrates RfeJobConfig from StorageBackend.get_json(job_id, "config.json").
  2. Loads the training partition via TrainingDataProvider.
  3. Seeds iteration 0 (full feature set) and iterates until stop rule fires.
  4. Writes per-iteration payload to storage and publishes SSE ticks.
  5. Builds the final RfeFinalResult.json with dual-VIF rows + rank trajectories.

Never references request/FastAPI objects, so the same function body runs in the
API-pod local-thread worker AND the standalone worker container.
"""

from __future__ import annotations

import time
import traceback
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from app.core.logging_config import get_logger

from .contracts import (
    FeatureImportance,
    IterationRecord,
    RfeFinalResult,
    RfeJobConfig,
    RfeStatus,
    StopReason,
    VariableRow,
    WorkingFeatureSet,
    _to_plain,
)
from .elimination_policy import AdaptiveEliminationPolicy
from .event_bus.base import EventBus
from .job_state.base import JobStateRow, JobStateStore
from .metrics import MetricEngine
from .shap_ranker import ShapRanker, rfe_ranking_mode, rfe_shap_explain_rows, rfe_shap_timeout_seconds
from .storage.base import StorageBackend
from .training_data_provider import TrainingDataProvider
from .warmup import start_rfe_warmup, wait_for_warmup
from .xgb_trainer import XGBoostRfeTrainer, rfe_cv_folds, rfe_subsample_rows, rfe_xgb_params

_logger = get_logger(__name__)


class RfeService:
    def __init__(
        self,
        *,
        storage: StorageBackend,
        job_state: JobStateStore,
        event_bus: EventBus,
        data_provider: Optional[TrainingDataProvider] = None,
        worker_context: bool = False,
    ) -> None:
        self._storage = storage
        self._job_state = job_state
        self._event_bus = event_bus
        self._data = data_provider or TrainingDataProvider(storage=storage)
        self._worker_context = worker_context
        self._policy = AdaptiveEliminationPolicy()
        self._metrics = MetricEngine()

    # -------------------- public API --------------------

    def run(self, job_id: str) -> None:
        try:
            self._job_state.update(job_id, status=RfeStatus.RUNNING.value, message="starting", heartbeat_at=time.time())
            self._audit(job_id, {"event": "job_started", "ts": time.time()})
            cfg = self._load_config(job_id)
            self._execute(job_id, cfg)
        except Exception as e:
            _logger.exception("RFE run failed for job %s", job_id)
            err = f"{type(e).__name__}: {e}"
            self._job_state.update(
                job_id,
                status=RfeStatus.FAILED.value,
                message="RFE failed",
                error=err,
            )
            self._audit(job_id, {"event": "job_failed", "error": err, "traceback": traceback.format_exc(), "ts": time.time()})
            self._event_bus.publish(
                job_id,
                {"job_id": job_id, "status": "failed", "error": err, "message": "RFE failed"},
            )
            self._event_bus.close_channel(job_id)

    # -------------------- loop --------------------

    def _execute(self, job_id: str, cfg: RfeJobConfig) -> None:
        ws = cfg.working_set
        requested_features = ws.all_features
        if not requested_features:
            raise ValueError("Working feature set is empty - nothing to RFE.")

        _logger.info(
            "RFE %s: loading train partition (dataset=%s, target=%s, features=%d)",
            job_id, cfg.dataset_id, cfg.target, len(requested_features),
        )
        self._publish_status(job_id, "Loading training partition...")

        # Make sure the scientific stack (matplotlib/xgboost/shap) is imported
        # before we enter the RFE loop. The startup hook already kicks this off
        # in a daemon thread; here we just wait briefly for it so the first
        # iteration does not absorb a ~20-45s font-cache build or DLL load.
        start_rfe_warmup(background=True)
        if not wait_for_warmup(timeout=120.0):
            _logger.info(
                "RFE %s: warmup still running after 120s, proceeding anyway "
                "(first SHAP call may take additional time)", job_id,
            )

        X, y, w = self._data.get_xy(
            dataset_id=cfg.dataset_id,
            target=cfg.target,
            feature_cols=requested_features,
            weight_col=cfg.weight_col,
            job_id=job_id,
            prefer_parquet=self._worker_context and cfg.train_parquet_available,
        )
        _logger.info("RFE %s: train partition ready (rows=%d, features=%d)", job_id, len(X), len(X.columns))

        # --- Test partition (for real per-iteration Test AUC) ---------------
        # When the objectives page carved out a test partition, we fit a fresh
        # model each iteration and score on it. This is cheap (one extra fit
        # per iteration) and gives the modeler a true generalization metric
        # alongside the k-fold CV estimate. If the test partition is missing
        # or single-class we silently fall back to Test AUC == CV AUC.
        X_test: Optional[pd.DataFrame] = None
        y_test: Optional[pd.Series] = None
        try:
            _test = self._data.get_test_xy(
                dataset_id=cfg.dataset_id,
                target=cfg.target,
                feature_cols=requested_features,
            )
        except Exception as e:
            _logger.info(
                "RFE %s: test partition load failed (%s) - falling back to CV-only.",
                job_id, e,
            )
            _test = None
        if _test is not None:
            X_test, y_test = _test
            _logger.info(
                "RFE %s: test partition ready (rows=%d, cols=%d) - will compute real Test AUC per iteration",
                job_id, len(X_test), len(X_test.columns),
            )
        else:
            _logger.info(
                "RFE %s: no usable test partition - Test AUC will mirror CV AUC",
                job_id,
            )

        # The data provider may legitimately drop a subset of the requested features
        # (system columns like split_tag, un-coercible dtypes, etc). Reconcile our
        # working list with the columns that actually survived into X so every
        # downstream slice (X[feature_cols], rank_trajectory keys, locked filter,
        # etc.) is guaranteed to be a subset of X.columns.
        kept_features = [c for c in requested_features if c in X.columns]
        dropped = [c for c in requested_features if c not in X.columns]
        if dropped:
            _logger.info(
                "RFE working set: %d features survived after preprocessing (%d dropped: %s)",
                len(kept_features), len(dropped),
                dropped[:10] + (["..."] if len(dropped) > 10 else []),
            )
        if not kept_features:
            raise ValueError(
                "All requested features were dropped during preprocessing - "
                "nothing to RFE. Dropped: " + str(dropped[:20])
            )
        feature_cols = kept_features

        trainer = XGBoostRfeTrainer()
        ranker = ShapRanker()
        _logger.info(
            "RFE %s: ranker config — mode=%s, shap_timeout=%ds, shap_explain_rows=%d "
            "(override: RFE_RANKING_MODE, RFE_SHAP_TIMEOUT_SECONDS, RFE_SHAP_EXPLAIN_ROWS)",
            job_id, rfe_ranking_mode(), rfe_shap_timeout_seconds(), rfe_shap_explain_rows(),
        )
        # Locked variables that did not survive preprocessing can no longer be
        # honoured as locked - they would break X[retained_cols] indexing.
        locked = [c for c in ws.locked if c in X.columns]
        dropped_locked = [c for c in ws.locked if c not in X.columns]
        if dropped_locked:
            _logger.warning(
                "RFE: %d locked variables were dropped by preprocessing and will not be honoured: %s",
                len(dropped_locked), dropped_locked[:10],
            )

        _logger.info("RFE %s: computing baseline metrics (IV/VIF/|Corr|/Missing) for %d features", job_id, len(feature_cols))
        self._publish_status(job_id, "Computing baseline IV/VIF/Correlation metrics...")
        baseline_metrics = self._metrics.ensure_metrics(
            X=X, y=y, feature_cols=feature_cols, precomputed=self._unwrap_precomputed(ws),
        )
        self._storage.put_json(job_id, "baseline_metrics.json", baseline_metrics)
        _logger.info("RFE %s: baseline metrics ready", job_id)

        # --- Target-leakage sniff test ----------------------------------------
        # Any feature that is almost perfectly correlated with the target is
        # almost always a target proxy (e.g. `loan_status` in Lending Club data
        # when target_flag is derived from it). XGB on such a feature trivially
        # returns AUC ≈ 1.0, which makes the whole RFE loop degenerate:
        # deltas are all zero, the stop rule fires after 1-2 drops, and the
        # modeller is left wondering why nothing moved. We don't block the
        # run (the user might genuinely want to keep the feature), but we log
        # a loud warning with the offenders so they can exclude/screen it
        # back in Step 2.
        try:
            leak_threshold = 0.95
            target_class_counts = y.value_counts(dropna=False).to_dict()
            _logger.info(
                "RFE %s: target '%s' class distribution on train partition = %s (rows=%d)",
                job_id, cfg.target, target_class_counts, len(y),
            )
            suspect = []
            for col in feature_cols:
                bm = baseline_metrics.get(col, {}) or {}
                ac = bm.get("abs_corr")
                if ac is not None and ac >= leak_threshold:
                    suspect.append((col, float(ac)))
            suspect.sort(key=lambda t: t[1], reverse=True)
            if suspect:
                _logger.warning(
                    "RFE %s: ⚠ possible target leakage — %d feature(s) have |corr(target)| ≥ %.2f on "
                    "the train partition: %s. CV AUC will look artificially close to 1.0 and the "
                    "elimination loop may terminate almost immediately. Consider removing these "
                    "features from the working set in Step 2 (screener) if they are post-outcome "
                    "fields or direct target proxies.",
                    job_id, len(suspect), leak_threshold,
                    [f"{name} (|corr|={v:.3f})" for name, v in suspect[:10]]
                    + (["..."] if len(suspect) > 10 else []),
                )
        except Exception as _leak_err:
            _logger.debug("RFE %s: leakage sniff test failed (non-fatal): %s", job_id, _leak_err)

        # --- Subsample for speed --------------------------------------------
        # XGBoost ranking signal is stable with ~5k rows. On a laptop a full
        # 24k-row fit × 3 folds × 128 trees ≈ several minutes per iteration.
        # We stratify-sample down to RFE_SUBSAMPLE_ROWS (default 5000) for the
        # RFE loop only; the final full-model fit in Step 5 uses the full set.
        max_rows = rfe_subsample_rows()
        X_fit, y_fit, w_fit = X, y, w
        if 0 < max_rows < len(X):
            from sklearn.model_selection import train_test_split
            keep_frac = max_rows / len(X)
            try:
                X_fit, _, y_fit, _, *_w = train_test_split(
                    X, y,
                    *([] if w is None else [w]),
                    train_size=keep_frac,
                    stratify=y,
                    random_state=42,
                )
                w_fit = _w[0] if _w else None
            except Exception:
                # If stratify fails (e.g. tiny class), fallback to head slice
                X_fit = X.iloc[:max_rows]
                y_fit = y.iloc[:max_rows]
                w_fit = w.iloc[:max_rows] if w is not None else None
            _logger.info(
                "RFE %s: subsampled %d → %d rows for CV (full set used for SHAP after CV; "
                "disable with RFE_SUBSAMPLE_ROWS=-1)",
                job_id, len(X), len(X_fit),
            )
        else:
            _logger.info("RFE %s: using all %d rows for CV (subsampling disabled)", job_id, len(X))

        cv_folds = rfe_cv_folds()
        _xgb = rfe_xgb_params()
        _logger.info(
            "RFE %s: CV config — folds=%d, n_estimators=%s, tree_method=%s, n_jobs=%s "
            "rows=%d (override: RFE_CV_FOLDS, RFE_XGB_N_ESTIMATORS, RFE_XGB_N_JOBS, RFE_SUBSAMPLE_ROWS)",
            job_id, cv_folds,
            _xgb.get("n_estimators"),
            _xgb.get("tree_method"),
            _xgb.get("n_jobs"),
            len(X_fit),
        )

        # --- Main RFE loop -----------------------------------------------
        # Iteration 0 is the "baseline" pass: we fit on the full feature set,
        # compute CV + Test AUC, but do NOT drop anything. Iterations 1..N are
        # the true elimination steps. This matches the wireframe's
        # "0 (Base) | 1 | 2 | ..." iteration log exactly.
        iterations: List[IterationRecord] = []
        cv_history: List[float] = []
        rank_trajectory: Dict[str, List[Optional[int]]] = {c: [] for c in feature_cols}
        retained_cols = list(feature_cols)
        iteration_idx = 0
        best_iter = 0
        best_auc = -1.0
        stop_reason: Optional[StopReason] = None

        # Business rule: at most 20 real elimination iterations on top of the
        # baseline (iteration 0). So the loop is allowed to record iter 0..20
        # inclusive — 21 rows in the iteration log. The safety cap is a
        # defensive upper bound in case the loop body ever fails to advance.
        max_real_iterations = 20
        total_cap = max_real_iterations + 1  # baseline + 20 real iters

        def _compute_test_auc(model_obj: Any, cols: List[str]) -> Optional[float]:
            """Score `model_obj` on the held-out test partition restricted to `cols`.
            Returns None (caller falls back to CV AUC) on any failure / missing test set."""
            if X_test is None or y_test is None:
                return None
            present = [c for c in cols if c in X_test.columns]
            if len(present) != len(cols) or not present:
                # Some retained columns are missing from the test frame; skip.
                return None
            try:
                from sklearn.metrics import roc_auc_score
                proba = model_obj.predict_proba(X_test[present])[:, 1]
                return float(roc_auc_score(y_test.values, proba))
            except Exception as e:
                _logger.info(
                    "RFE %s: test AUC computation failed for %d features: %s",
                    job_id, len(cols), e,
                )
                return None

        while iteration_idx < total_cap:
            # Cancellation check at iteration boundary (soft-cancel semantics).
            state = self._job_state.get(job_id)
            if state is not None and state.cancel_flag:
                stop_reason = StopReason.CANCELLED
                break

            self._job_state.update(
                job_id,
                current_iteration=iteration_idx,
                total_features=len(retained_cols),
                heartbeat_at=time.time(),
                message=f"iteration {iteration_idx}, {len(retained_cols)} features",
            )
            _logger.info(
                "RFE %s: iteration %d - computing %d-fold CV on %d features (%d rows)",
                job_id, iteration_idx, cv_folds, len(retained_cols), len(X_fit),
            )
            self._publish_status(
                job_id,
                f"Iteration {iteration_idx}: computing {cv_folds}-fold CV on {len(retained_cols)} features ({len(X_fit)} rows)...",
                current_iteration=iteration_idx,
                total_features=len(retained_cols),
            )

            Xi = X_fit[retained_cols]

            def _on_fold(fold_idx: int, total_folds: int, fold_auc: float, _it=iteration_idx, _n=len(retained_cols)) -> None:
                self._job_state.update(job_id, heartbeat_at=time.time())
                self._publish_status(
                    job_id,
                    f"Iteration {_it}: fold {fold_idx}/{total_folds} done (AUC {fold_auc:.4f})",
                    current_iteration=_it,
                    total_features=_n,
                )

            def _on_fold_start(fold_idx: int, total_folds: int, _it=iteration_idx, _n=len(retained_cols)) -> None:
                self._job_state.update(job_id, heartbeat_at=time.time())
                self._publish_status(
                    job_id,
                    f"Iteration {_it}: training fold {fold_idx}/{total_folds}...",
                    current_iteration=_it,
                    total_features=_n,
                )

            iter_t0 = time.time()
            cv_t0 = time.time()
            model, cv_auc_mean, _ = trainer.fit_and_cv(
                Xi,
                y_fit,
                sample_weight=w_fit,
                folds=cv_folds,
                on_fold=_on_fold,
                on_fold_start=_on_fold_start,
            )
            cv_elapsed = time.time() - cv_t0
            _logger.info(
                "RFE %s: iteration %d - CV AUC mean=%.4f (%.2fs), ranking features",
                job_id, iteration_idx, cv_auc_mean, cv_elapsed,
            )
            self._publish_status(
                job_id,
                f"Iteration {iteration_idx}: CV AUC {cv_auc_mean:.4f} - ranking features...",
                current_iteration=iteration_idx,
                total_features=len(retained_cols),
            )

            # Per-iteration Test AUC: score the single full-data XGB fit
            # returned by fit_and_cv() (line above) on the held-out test
            # partition when available. Falls back to CV AUC otherwise.
            test_auc_val: Optional[float] = _compute_test_auc(model, retained_cols)
            test_auc_final = float(test_auc_val) if test_auc_val is not None else float(cv_auc_mean)

            rank_t0 = time.time()
            shap_ordered = ranker.rank(model, Xi)
            rank_elapsed = time.time() - rank_t0
            iter_elapsed = time.time() - iter_t0
            _logger.info(
                "RFE %s: iteration %d completed in %.2fs (CV %.2fs + ranking %.2fs, %d features) test_auc=%s",
                job_id, iteration_idx, iter_elapsed, cv_elapsed, rank_elapsed, len(retained_cols),
                f"{test_auc_final:.4f}" if test_auc_val is not None else "cv-fallback",
            )
            # If the model is essentially perfect, surface the top SHAP drivers
            # so the user can spot the leaky feature without digging into the
            # SHAP JSON. 0.9975 threshold chosen so real "very separable"
            # problems (0.985-0.995) do not false-trigger every iteration.
            if cv_auc_mean >= 0.9975 and shap_ordered:
                top_drivers = [
                    f"{name} (SHAP={shap:.4f})"
                    for name, shap, _ in shap_ordered[:3]
                ]
                _logger.warning(
                    "RFE %s: iteration %d CV AUC=%.4f looks artificially perfect — "
                    "top SHAP drivers: %s. If any of these are post-outcome fields "
                    "or target proxies, exclude them in Step 2 and re-run; the "
                    "elimination loop will otherwise converge immediately.",
                    job_id, iteration_idx, cv_auc_mean, top_drivers,
                )
            importances = [
                FeatureImportance(
                    variable=name,
                    shap_importance=shap,
                    native_importance=native,
                    shap_rank=rank,
                )
                for rank, (name, shap, native) in enumerate(shap_ordered, start=1)
            ]

            # Update rank trajectory for this iteration for all originally-tracked vars.
            importance_rank_map = {imp.variable: imp.shap_rank for imp in importances}
            for col in feature_cols:
                rank_trajectory[col].append(importance_rank_map.get(col))

            # Pick drop list. Iteration 0 is the baseline - never drop anything
            # there, so the user always sees a full "0 (Base)" row with Drop="-"
            # and the first real elimination happens in iteration 1.
            if iteration_idx == 0:
                to_drop: List[str] = []
                band_label = "-"
            else:
                to_drop = self._policy.select_to_drop(shap_ordered=shap_ordered, locked=locked)
                band_label = self._policy.band_for(len(retained_cols)).label

            is_best = cv_auc_mean > best_auc + 1e-9
            if is_best:
                best_auc = cv_auc_mean
                best_iter = iteration_idx
            cv_history.append(cv_auc_mean)

            locked_zero = [
                imp.variable for imp in importances
                if imp.variable in locked and imp.shap_importance <= 1e-12
            ]

            rel_delta = None
            if len(cv_history) >= 2:
                prev = cv_history[-2]
                rel_delta = float((cv_auc_mean - prev) / max(prev, 1e-9))

            rec = IterationRecord(
                iteration=iteration_idx,
                feature_count=len(retained_cols),
                features_in=list(retained_cols),
                features_dropped=list(to_drop),
                elimination_band_label=band_label,
                cv_auc=float(cv_auc_mean),
                test_auc=test_auc_final,
                relative_delta_from_prev=rel_delta,
                importances=importances,
                locked_zero_importance_flags=locked_zero,
                stop_reason=None,
                is_best=is_best,
                timestamp_epoch=time.time(),
            )
            iterations.append(rec)
            self._storage.put_json(job_id, f"iteration_{iteration_idx:04d}.json", _to_plain(rec))
            self._audit(job_id, {"event": "iteration", **{k: _to_plain(v) for k, v in rec.__dict__.items() if k != "importances"}})
            self._job_state.update(job_id, latest_cv_auc=float(cv_auc_mean), best_iteration=best_iter)
            slim_rec = {k: v for k, v in _to_plain(rec).items() if k not in ("importances", "locked_zero_importance_flags")}
            self._event_bus.publish(job_id, {"job_id": job_id, "status": "running", "iteration": slim_rec})

            # Iteration 0 is baseline-only: always continue into iteration 1
            # without consulting the stop rule (it has only one CV sample so
            # the policy can't form a meaningful delta yet).
            if iteration_idx == 0:
                iteration_idx += 1
                continue

            # Stop checks - evaluate after recording this iteration.
            retained_after_drop = [c for c in retained_cols if c not in set(to_drop)]

            # Business rule: CV AUC drop > 5% vs previous iteration stops the
            # loop (we keep the best iteration, rollback marker handled below).
            if rel_delta is not None and rel_delta < -0.05:
                stop_reason = StopReason.AUC_DEGRADATION
                _logger.info(
                    "RFE %s: stopping after iteration %d — CV AUC dropped %.2f%% vs previous (> 5%% threshold).",
                    job_id, iteration_idx, rel_delta * 100,
                )
                break

            # Business rule: at most 20 real elimination iterations on top of
            # the baseline. Once iter 20 has been recorded, stop.
            if iteration_idx >= max_real_iterations:
                stop_reason = StopReason.NATURAL_CONVERGENCE
                _logger.info(
                    "RFE %s: stopping after iteration %d — max %d iterations reached.",
                    job_id, iteration_idx, max_real_iterations,
                )
                break

            stop, reason = self._policy.should_stop(
                cv_auc_history=cv_history, feature_count_after_drop=len(retained_after_drop)
            )
            if stop:
                stop_reason = {
                    "floor_reached": StopReason.FLOOR_REACHED,
                    "auc_degradation": StopReason.AUC_DEGRADATION,
                    "natural_convergence": StopReason.NATURAL_CONVERGENCE,
                }.get(reason or "", StopReason.NATURAL_CONVERGENCE)
                break
            if not to_drop:
                stop_reason = StopReason.NATURAL_CONVERGENCE
                break

            retained_cols = retained_after_drop
            iteration_idx += 1

        stop_reason = stop_reason or StopReason.NATURAL_CONVERGENCE

        # Rollback marker: if we stopped on AUC degradation and the best
        # iteration is not the last iteration we actually ran, record the
        # iteration index we're rolling back FROM. The UI shows this as the
        # "Rolled back from iteration N" trailer on the completion banner.
        last_iter_idx = iterations[-1].iteration if iterations else 0
        rolled_back_from: Optional[int] = None
        if (
            stop_reason == StopReason.AUC_DEGRADATION
            and iterations
            and best_iter < last_iter_idx
        ):
            rolled_back_from = last_iter_idx

        raw_df = self._data._fetch_train_dataframe(cfg.dataset_id)
        if raw_df is not None:
            true_categorical_columns = set(raw_df.select_dtypes(include=['object', 'category', 'string']).columns)
        else:
            true_categorical_columns = set()

        final = self._build_final_result(
            cfg=cfg,
            X=X, y=y,
            iterations=iterations,
            rank_trajectory=rank_trajectory,
            baseline_metrics=baseline_metrics,
            best_iter=best_iter,
            stop_reason=stop_reason,
            feature_cols=feature_cols,
            rolled_back_from=rolled_back_from,
            true_categorical_columns=true_categorical_columns,
        )
        self._storage.put_json(job_id, "final_result.json", _to_plain(final))
        self._job_state.update(
            job_id,
            status=RfeStatus.COMPLETED.value if stop_reason != StopReason.CANCELLED else RfeStatus.CANCELLED.value,
            message="RFE completed" if stop_reason != StopReason.CANCELLED else "Cancelled by user",
            best_iteration=best_iter,
        )
        self._event_bus.publish(
            job_id,
            {
                "job_id": job_id,
                "status": "completed" if stop_reason != StopReason.CANCELLED else "cancelled",
                "final": {
                    "best_iteration": best_iter,
                    "total_iterations": len(iterations),
                    "final_feature_count": final.final_feature_count,
                    "stop_reason": stop_reason.value,
                },
            },
        )
        self._audit(job_id, {"event": "job_completed", "stop_reason": stop_reason.value, "best_iteration": best_iter, "ts": time.time()})
        self._event_bus.close_channel(job_id)

    # -------------------- helpers --------------------

    def _load_config(self, job_id: str) -> RfeJobConfig:
        payload = self._storage.get_json(job_id, "config.json")
        if payload is None:
            raise RuntimeError(f"Job {job_id}: config.json missing from storage")
        ws = payload.get("working_set") or {}
        precomputed_raw = ws.get("precomputed_metrics") or {}
        precomputed_typed: Dict[str, Dict[str, Any]] = {}  # noqa
        for var, metrics in precomputed_raw.items():
            precomputed_typed[var] = metrics
        return RfeJobConfig(
            job_id=payload["job_id"],
            dataset_id=payload["dataset_id"],
            target=payload["target"],
            working_set=WorkingFeatureSet(
                locked=list(ws.get("locked") or []),
                screened=list(ws.get("screened") or []),
                precomputed_metrics=precomputed_raw or {},
            ),
            weight_col=payload.get("weight_col"),
            problem_type=payload.get("problem_type", "binary_classification"),
            user_id=payload.get("user_id"),
            created_at_epoch=float(payload.get("created_at_epoch") or 0.0),
            train_parquet_available=bool(payload.get("train_parquet_available") or False),
        )

    def _unwrap_precomputed(self, ws: WorkingFeatureSet) -> Dict[str, Dict[str, float]]:
        """
        WorkingFeatureSet.precomputed_metrics may come from JSON as raw dicts or as
        PrecomputedMetric objects. Coerce everything to a simple {var: {metric: value}} map.
        """
        out: Dict[str, Dict[str, float]] = {}
        for var, vals in (ws.precomputed_metrics or {}).items():
            flat: Dict[str, float] = {}
            for k, v in (vals or {}).items():
                if isinstance(v, dict) and "value" in v:
                    flat[k] = v["value"]
                else:
                    flat[k] = v
            out[var] = flat
        return out

    def _build_final_result(
        self,
        *,
        cfg: RfeJobConfig,
        X: pd.DataFrame,
        y: pd.Series,
        iterations: List[IterationRecord],
        rank_trajectory: Dict[str, List[Optional[int]]],
        baseline_metrics: Dict[str, Dict[str, float]],
        best_iter: int,
        stop_reason: StopReason,
        feature_cols: List[str],
        rolled_back_from: Optional[int] = None,
        true_categorical_columns: Optional[set] = None,
    ) -> RfeFinalResult:
        if not iterations:
            raise RuntimeError("No iterations recorded - cannot build final result")

        best = iterations[best_iter] if 0 <= best_iter < len(iterations) else iterations[-1]
        retained = list(best.features_in)
        dropped = [c for c in feature_cols if c not in set(retained)]

        # N-var VIF computed on the retained set (guide dual-VIF display Section 5.2).
        nvar_vif_map = self._metrics.compute_vif(X[retained]) if retained else {}

        # drop_iteration: first iteration where the variable is in `features_dropped`.
        drop_map: Dict[str, int] = {}
        for itn in iterations:
            for d in itn.features_dropped:
                drop_map.setdefault(d, itn.iteration)

        # Best-iteration SHAP importance per variable.
        best_shap_map = {imp.variable: imp.shap_importance for imp in best.importances}

        # Fallback SHAP importance (last known) for dropped variables.
        last_shap_map: Dict[str, float] = {}
        for itn in iterations:
            for imp in itn.importances:
                last_shap_map[imp.variable] = imp.shap_importance

        rows: List[VariableRow] = []
        for col in feature_cols:
            bm = baseline_metrics.get(col, {})
            signed_corr = bm.get("signed_corr")
            # Guide rule: numeric features -> sign of bivariate correlation;
            # categorical-origin features (WoE-encoded or one-hot) -> 0.
            is_categorical = self._is_categorical_origin(col, X[col] if col in X.columns else None, true_categorical_columns)
            suggested = 0 if is_categorical else self._suggested_monotone(signed_corr)
            rows.append(
                VariableRow(
                    variable=col,
                    locked=col in set(cfg.working_set.locked),
                    status="retained" if col in set(retained) else "dropped",
                    drop_iteration=drop_map.get(col),
                    iv=bm.get("iv"),
                    orig_vif=bm.get("orig_vif"),
                    nvar_vif=float(nvar_vif_map.get(col)) if col in nvar_vif_map and not _is_bad_float(nvar_vif_map.get(col)) else None,
                    abs_corr_target=bm.get("abs_corr"),
                    shap_importance_best=best_shap_map.get(col, last_shap_map.get(col)),
                    rank_trajectory=list(rank_trajectory.get(col, [])),
                    suggested_monotone=suggested,
                    bivariate_corr=signed_corr,
                )
            )

        return RfeFinalResult(
            job_id=cfg.job_id,
            dataset_id=cfg.dataset_id,
            target=cfg.target,
            starting_feature_count=len(feature_cols),
            final_feature_count=len(retained),
            best_iteration=best_iter,
            total_iterations=len(iterations),
            stop_reason=stop_reason,
            best_cv_auc=float(best.cv_auc),
            best_test_auc=float(best.test_auc),
            iterations=iterations,
            rows=rows,
            rolled_back_from_iteration=rolled_back_from,
        )

    @staticmethod
    def _suggested_monotone(signed_corr: Optional[float]) -> int:
        """Pure sign of the bivariate correlation with the target.

        Per the Model Training Agent Developer Guide: numeric features get
        the sign of the bivariate correlation as the suggested monotone
        direction; categorical-origin features default to 0 and are
        short-circuited upstream.
        """
        if signed_corr is None or np.isnan(signed_corr):
            return 0
        if signed_corr > 0:
            return 1
        if signed_corr < 0:
            return -1
        return 0

    @staticmethod
    def _is_categorical_origin(col: str, series: Optional[pd.Series], true_categorical_columns: Optional[set] = None) -> bool:
        """Heuristic for categorical-origin features (WoE-encoded or one-hot).

        Conservative signals:
          - explicitly provided true_categorical_columns from raw data
          - Column name suffix ``_woe`` / ``_ohe`` (case-insensitive).
          - ``__`` separator pattern used by pandas.get_dummies output.
          - Post-encoded series has at most 2 unique non-null values (binary
            indicator from one-hot encoding).
        Any single match is enough to treat the feature as categorical-origin
        and default its suggested monotone to 0.
        """
        if true_categorical_columns and col in true_categorical_columns:
            return True
        name = (col or "").lower()
        if name.endswith("_woe") or name.endswith("_ohe"):
            return True
        if "__" in name:
            return True
        if series is None:
            return False
        try:
            nunique = int(series.dropna().nunique())
        except Exception:
            return False
        if nunique <= 2:
            return True
        return False

    def _audit(self, job_id: str, row: Dict[str, object]) -> None:
        try:
            self._storage.append_jsonl(job_id, "audit.jsonl", row)
        except Exception as e:
            _logger.debug("audit.jsonl append failed for %s: %s", job_id, e)

    def _publish_status(
        self,
        job_id: str,
        message: str,
        *,
        current_iteration: Optional[int] = None,
        total_features: Optional[int] = None,
    ) -> None:
        """
        Emit a lightweight status tick to the SSE bus. This is how we keep the
        Step 3 UI responsive during the long XGBoost + SHAP steps inside an
        iteration (5-fold CV on 500 trees can easily take 30s on a laptop).
        The payload shape matches ``RfeStatusResponse`` so the frontend can
        classify it as ``kind: "status"`` without any special-casing.
        """
        row = self._job_state.get(job_id)
        if row is not None:
            self._job_state.update(job_id, message=message, heartbeat_at=time.time())
        payload = {
            "job_id": job_id,
            "status": (row.status if row is not None else "running"),
            "message": message,
            "current_iteration": int(
                current_iteration
                if current_iteration is not None
                else (row.current_iteration if row is not None else 0)
            ),
            "total_features": int(
                total_features
                if total_features is not None
                else (row.total_features if row is not None else 0)
            ),
            "best_iteration": int(row.best_iteration if row is not None else 0),
            "latest_cv_auc": (row.latest_cv_auc if row is not None else None),
            "iteration_count": 0,  # real iteration_count lives in storage; not needed for status tick
            "heartbeat_at": time.time(),
            "error": None,
        }
        try:
            self._event_bus.publish(job_id, payload)
        except Exception as e:
            _logger.debug("status publish failed for %s: %s", job_id, e)


def _is_bad_float(v) -> bool:
    try:
        return v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v)))
    except Exception:
        return True
