"""
API routes for Step 3 (XGBoost-SHAP RFE) and Step 4 (Feature review + override).

All endpoints live under a dedicated `rfe_router` so they don't collide with
the large existing `routes.py` file - avoids merge conflicts with parallel dev
work on other steps.

Data-scope rule: every endpoint here assumes the RFE service will read the
**whole training partition only**. `segment_id` in the request is accepted and
logged but never used.
"""

from __future__ import annotations

import asyncio
import json
import math
import time
from typing import Any, Dict, List, Optional


def _sanitize_json_floats(obj: Any) -> Any:
    """Recursively replace NaN/Inf floats with None so responses are JSON-compliant.

    FastAPI/Starlette uses `json.dumps(..., allow_nan=False)` for responses, which
    raises ValueError on NaN/Inf. RFE result payloads loaded from persisted JSON can
    contain NaN for missing metrics (IV, VIF, SHAP, corr); we coerce those to null.
    """
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    if isinstance(obj, dict):
        return {k: _sanitize_json_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_json_floats(v) for v in obj]
    if isinstance(obj, tuple):
        return [_sanitize_json_floats(v) for v in obj]
    return obj

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from app.api.auth_routes import get_current_user_dependency
from app.core.logging_config import get_logger
from app.models.schemas import (
    RfeFinalizeRequest,
    RfeFinalizeResponse,
    RfeMonotoneResponse,
    RfeResultResponse,
    RfeStartRequest,
    RfeStartResponse,
    RfeStatusResponse,
)
from app.services.dataframe_state_manager import dataframe_state_manager
from app.services.model_training_rfe import (
    RfeStatus,
    WorkingFeatureSet,
    get_job_manager,
)
from app.services.model_training_rfe.backends import get_backends

rfe_router = APIRouter(prefix="/rfe", tags=["model-training-rfe"])
_logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# POST /rfe/start
# ---------------------------------------------------------------------------


@rfe_router.post("/start", response_model=RfeStartResponse)
async def start_rfe(
    req: RfeStartRequest,
    current_user=Depends(get_current_user_dependency),
):
    """
    Enqueue a new RFE (Step 3) run. Validates working-set shape and that the
    dataset has a train partition. Locked vars must be a subset of the full
    working set.
    """
    locked = list(req.working_set.locked)
    screened = list(req.working_set.screened)
    all_features = locked + [v for v in screened if v not in set(locked)]
    if not all_features:
        raise HTTPException(status_code=400, detail="working_set is empty")

    # Soft check: dataset + target + train partition exist before we bother queueing.
    try:
        dataframe_state_manager.set_scope(req.dataset_id, scope="train")
    except Exception as e:
        _logger.warning("set_scope(train) failed pre-start for %s: %s", req.dataset_id, e)
    train_df = dataframe_state_manager.get_dataframe(req.dataset_id)
    if train_df is None or train_df.shape[0] == 0:
        raise HTTPException(
            status_code=400,
            detail=f"No train partition available for dataset_id={req.dataset_id}. "
                   "Configure the train/test/validation split before running RFE.",
        )
    if req.target not in train_df.columns:
        raise HTTPException(status_code=400, detail=f"Target column '{req.target}' not in dataset")
    missing = [v for v in all_features if v not in train_df.columns]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Features not found in dataset: {missing[:8]}"
                   + (" ... (truncated)" if len(missing) > 8 else ""),
        )

    # The working_set carries Pydantic models; convert to plain dicts for the service.
    precomputed_plain: Dict[str, Dict[str, float]] = {}
    for var, vals in (req.working_set.precomputed_metrics or {}).items():
        if vals is None:
            continue
        plain = {k: v for k, v in vals.model_dump().items() if v is not None}
        if plain:
            precomputed_plain[var] = plain

    ws = WorkingFeatureSet(
        locked=locked,
        screened=screened,
        precomputed_metrics=precomputed_plain,
    )

    user_id = None
    try:
        user_id = getattr(current_user, "user_id", None) or getattr(current_user, "email", None)
    except Exception:
        pass

    manager = get_job_manager()
    job_id = manager.start(
        dataset_id=req.dataset_id,
        target=req.target,
        working_set=ws,
        weight_col=req.weight_col,
        user_id=user_id,
    )

    _, _, _, _, mode = get_backends()
    manager.audit(job_id, {
        "event": "rfe_start",
        "user_id": user_id,
        "dataset_id": req.dataset_id,
        "target": req.target,
        "n_locked": len(locked),
        "n_screened": len(screened),
        "weight_col": req.weight_col,
        "segment_id_ignored": bool(req.segment_id),
        "ts": time.time(),
    })
    return RfeStartResponse(job_id=job_id, mode=mode)


# ---------------------------------------------------------------------------
# GET /rfe/status/{job_id}
# ---------------------------------------------------------------------------


@rfe_router.get("/status/{job_id}", response_model=RfeStatusResponse)
async def get_rfe_status(
    job_id: str,
    current_user=Depends(get_current_user_dependency),
):
    manager = get_job_manager()
    payload = manager.get_status(job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Job not found")
    # Map to strict response schema (ignore fields we don't surface).
    return RfeStatusResponse(
        job_id=payload["job_id"],
        status=payload["status"],
        message=payload.get("message", ""),
        current_iteration=payload.get("current_iteration", 0),
        total_features=payload.get("total_features", 0),
        best_iteration=payload.get("best_iteration", -1),
        latest_cv_auc=payload.get("latest_cv_auc"),
        iteration_count=payload.get("iteration_count", 0),
        heartbeat_at=payload.get("heartbeat_at", 0.0),
        error=payload.get("error"),
    )


# ---------------------------------------------------------------------------
# GET /rfe/stream/{job_id}
# ---------------------------------------------------------------------------


def _snapshot_payload(job_id: str) -> Optional[Dict[str, Any]]:
    manager = get_job_manager()
    payload = manager.get_status(job_id)
    return payload


@rfe_router.get("/stream/{job_id}")
async def stream_rfe_status(
    job_id: str,
    current_user=Depends(get_current_user_dependency),
):
    """
    Server-Sent Events stream mirroring the /auto-training/stream pattern.

    Strategy:
    - On connect, emit the current status once.
    - Subscribe to the EventBus for live iteration ticks.
    - Every ~1.5s (whichever is sooner: new event or poll tick) emit a
      status snapshot so the client sees progress even if the bus is idle.
    - Emit a keepalive comment every ~21s to keep proxies from dropping.
    """
    manager = get_job_manager()
    if manager.get_status(job_id) is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_gen():
        yield ": stream-open\n\n"

        # IMPORTANT: subscribe to the live event bus BEFORE replaying snapshot/iterations.
        # Otherwise the worker thread (which runs synchronously in local mode) can publish
        # iteration ticks between the time the SSE handler starts and the time it actually
        # subscribes, causing the InProcessEventBus to silently drop those events
        # (no subscribers => publish() is a no-op). After subscribing, we (a) emit the
        # current status snapshot, (b) replay any iteration files already saved on disk,
        # then (c) start consuming live ticks from the bus, deduplicating against the
        # iterations we already replayed.
        bus_iter = manager.subscribe(job_id).__aiter__()

        # Initial snapshot (status only - no iteration body)
        snap = _snapshot_payload(job_id)
        if snap is not None:
            yield f"data: {json.dumps(snap, default=str)}\n\n"

        # Replay any iterations already persisted to storage by the worker. This handles
        # the race where the worker has already produced 1+ iterations before the SSE
        # client connected, and also handles the case where the user reloaded the page
        # mid-run and is reattaching to a long-running job.
        replayed_max_iter = -1
        try:
            for key in manager.list_iteration_keys(job_id):
                rec = manager.get_iteration(job_id, key)
                if rec is None:
                    continue
                idx = int(rec.get("iteration", -1))
                if idx > replayed_max_iter:
                    replayed_max_iter = idx
                yield f"data: {json.dumps({'job_id': job_id, 'status': 'running', 'iteration': rec, 'replayed': True}, default=str)}\n\n"
        except Exception as e:
            _logger.debug("Iteration replay failed for %s: %s", job_id, e)

        # If the job already finished (e.g. very fast run, or user is reattaching to a
        # completed job), emit the final result and exit.
        snap_after = _snapshot_payload(job_id)
        if snap_after is not None and snap_after.get("status") in ("completed", "failed", "cancelled"):
            result = manager.get_result(job_id)
            if result is not None:
                yield f"data: {json.dumps({'job_id': job_id, 'status': snap_after.get('status'), 'result': result}, default=str)}\n\n"
            return

        last_snapshot = time.time()
        last_keepalive = time.time()
        while True:
            try:
                event = await asyncio.wait_for(bus_iter.__anext__(), timeout=1.5)
                # Skip iteration events that we already emitted via the replay step.
                if isinstance(event, dict):
                    iter_payload = event.get("iteration")
                    if isinstance(iter_payload, dict):
                        idx = int(iter_payload.get("iteration", -1))
                        if idx >= 0 and idx <= replayed_max_iter:
                            continue
                        if idx > replayed_max_iter:
                            replayed_max_iter = idx
                yield f"data: {json.dumps(event, default=str)}\n\n"
                st = event.get("status") if isinstance(event, dict) else None
                if st in ("completed", "failed", "cancelled"):
                    result = manager.get_result(job_id)
                    if result is not None:
                        yield f"data: {json.dumps({'job_id': job_id, 'status': st, 'result': result}, default=str)}\n\n"
                    return
            except asyncio.TimeoutError:
                now = time.time()
                if now - last_snapshot >= 1.5:
                    snap = _snapshot_payload(job_id)
                    last_snapshot = now
                    if snap is None:
                        yield f"data: {json.dumps({'job_id': job_id, 'status': 'failed', 'error': 'Job disappeared'}, default=str)}\n\n"
                        return
                    yield f"data: {json.dumps(snap, default=str)}\n\n"
                    if snap.get("status") in ("completed", "failed", "cancelled"):
                        result = manager.get_result(job_id)
                        if result is not None:
                            yield f"data: {json.dumps({'job_id': job_id, 'status': snap.get('status'), 'result': result}, default=str)}\n\n"
                        return
                if now - last_keepalive >= 21.0:
                    yield ": keepalive\n\n"
                    last_keepalive = now
            except StopAsyncIteration:
                return
            except Exception as e:
                _logger.warning("RFE stream error for %s: %s", job_id, e)
                yield f"data: {json.dumps({'job_id': job_id, 'status': 'failed', 'error': str(e)}, default=str)}\n\n"
                return

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


# ---------------------------------------------------------------------------
# POST /rfe/cancel/{job_id}
# ---------------------------------------------------------------------------


@rfe_router.post("/cancel/{job_id}")
async def cancel_rfe(
    job_id: str,
    current_user=Depends(get_current_user_dependency),
):
    manager = get_job_manager()
    row = manager.get_status(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found")
    current = row.get("status")
    if current in ("completed", "failed", "cancelled"):
        return {"success": False, "cancelled": False, "status": current, "message": f"Job already {current}"}
    cancelled = manager.cancel(job_id)
    manager.audit(job_id, {"event": "rfe_cancel_requested", "ts": time.time()})
    return {"success": True, "cancelled": cancelled, "status": "cancelling", "message": "Cancel flag set"}


# ---------------------------------------------------------------------------
# GET /rfe/result/{job_id}
# ---------------------------------------------------------------------------


@rfe_router.get("/result/{job_id}", response_model=RfeResultResponse)
async def get_rfe_result(
    job_id: str,
    current_user=Depends(get_current_user_dependency),
):
    manager = get_job_manager()
    status_payload = manager.get_status(job_id)
    if status_payload is None:
        raise HTTPException(status_code=404, detail="Job not found")
    result = manager.get_result(job_id)
    if result is None:
        raise HTTPException(
            status_code=409,
            detail=f"Result not available yet (status={status_payload.get('status')})",
        )
    return RfeResultResponse(**_sanitize_json_floats(result))


# ---------------------------------------------------------------------------
# POST /rfe/finalize
# ---------------------------------------------------------------------------


@rfe_router.post("/finalize", response_model=RfeFinalizeResponse)
async def finalize_rfe(
    req: RfeFinalizeRequest,
    current_user=Depends(get_current_user_dependency),
):
    """
    HITL gate for Step 4. Merges user overrides with the RFE-selected features,
    recomputes N-var VIF if the selection changed, and persists the final
    feature set + monotone constraints for Step 5 to pick up.

    Audit row is always written per guide Section 11 (this is the HITL action).
    """
    manager = get_job_manager()
    status_payload = manager.get_status(req.job_id)
    if status_payload is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if status_payload.get("status") not in ("completed", "interrupted", "cancelled"):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot finalize: job status is '{status_payload.get('status')}'. Wait for completion.",
        )
    result = manager.get_result(req.job_id)
    if result is None:
        raise HTTPException(status_code=409, detail="Result not available yet")

    retained = [row["variable"] for row in result["rows"] if row.get("status") == "retained"]
    locked = [row["variable"] for row in result["rows"] if row.get("locked")]
    all_feats = [row["variable"] for row in result["rows"]]

    excluded = set(req.overrides.exclude or [])
    included = set(req.overrides.include or [])

    # The UI allows users to uncheck locked variables at Step 4 (explicit
    # product decision). We still audit the exception so the decision is
    # traceable, but we do NOT hard-reject the finalize request.
    unlocked_excluded = excluded & set(locked)
    if unlocked_excluded:
        _logger.warning(
            "RFE finalize: user unchecked locked variables job=%s vars=%s",
            req.job_id,
            sorted(unlocked_excluded),
        )
    # Include/exclude must come from the RFE feature universe
    unknown = (included | excluded) - set(all_feats)
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown variables in overrides: {sorted(unknown)}")

    final_features = sorted(
        (set(retained) - excluded) | included,
        key=lambda v: (v not in set(locked), v),  # locked first, alphabetic within
    )
    if not final_features:
        raise HTTPException(status_code=400, detail="Final feature set is empty after overrides")

    # Recompute N-var VIF if selection differs from RFE retained (otherwise reuse from result rows).
    final_vifs: Dict[str, float] = {}
    if set(final_features) != set(retained):
        # Pull train partition again and recompute VIF for the final selection.
        cfg = manager.get_config(req.job_id)
        if cfg is None:
            raise HTTPException(status_code=500, detail="Missing job config")
        try:
            dataframe_state_manager.set_scope(cfg["dataset_id"], scope="train")
        except Exception:
            pass
        train_df = dataframe_state_manager.get_dataframe(cfg["dataset_id"])
        if train_df is None:
            raise HTTPException(status_code=500, detail="Train partition not available to recompute VIF")
        from app.services.model_training_rfe.metrics import MetricEngine

        vif_map = MetricEngine().compute_vif(train_df[[c for c in final_features if c in train_df.columns]])
        final_vifs = {k: float(v) for k, v in vif_map.items() if v is not None and math.isfinite(v)}
    else:
        for row in result["rows"]:
            if row["variable"] in set(final_features) and row.get("nvar_vif") is not None:
                val = float(row["nvar_vif"])
                if math.isfinite(val):
                    final_vifs[row["variable"]] = val

    monotone_in = {k: int(v) for k, v in (req.monotone or {}).items() if int(v) in (-1, 0, 1)}
    # Ensure every final feature has a monotone entry (0 by default)
    monotone = {feat: int(monotone_in.get(feat, 0)) for feat in final_features}

    features_payload = {
        "job_id": req.job_id,
        "dataset_id": result["dataset_id"],
        "target": result["target"],
        "features": final_features,
        "locked": [v for v in locked if v in set(final_features)],
        "finalized_at_epoch": time.time(),
    }
    manager.write_monotone_and_features(
        job_id=req.job_id,
        monotone=monotone,
        features=features_payload,
    )
    manager.audit(
        req.job_id,
        {
            "event": "rfe_finalize",
            "user_id": getattr(current_user, "user_id", None) or getattr(current_user, "email", None),
            "retained_rfe": retained,
            "final_features": final_features,
            "includes": sorted(list(included)),
            "excludes": sorted(list(excluded)),
            "unlocked_excluded": sorted(list(unlocked_excluded)),
            "monotone_nonzero": {k: v for k, v in monotone.items() if v != 0},
            "ts": time.time(),
        },
    )
    payload = RfeFinalizeResponse(
        success=True,
        job_id=req.job_id,
        dataset_id=result["dataset_id"],
        target=result["target"],
        features=final_features,
        locked=[v for v in locked if v in set(final_features)],
        monotone=monotone,
        final_vifs=final_vifs,
        finalized_at_epoch=features_payload["finalized_at_epoch"],
    )
    return _sanitize_json_floats(payload.model_dump())


# ---------------------------------------------------------------------------
# GET /rfe/monotone/{dataset_id}  (Step 5 pickup, read-only)
# ---------------------------------------------------------------------------


@rfe_router.get("/monotone/{dataset_id}", response_model=RfeMonotoneResponse)
async def get_monotone_for_dataset(
    dataset_id: str,
    current_user=Depends(get_current_user_dependency),
):
    manager = get_job_manager()
    payload = manager.read_monotone_by_dataset(dataset_id)
    if not payload:
        return RfeMonotoneResponse(dataset_id=dataset_id)
    feats = payload.get("final_features") or {}
    monotone = payload.get("monotone") or {}
    return RfeMonotoneResponse(
        dataset_id=dataset_id,
        job_id=payload.get("job_id"),
        features=list(feats.get("features") or []),
        locked=list(feats.get("locked") or []),
        monotone={k: int(v) for k, v in monotone.items()},
        finalized_at_epoch=feats.get("finalized_at_epoch"),
    )
