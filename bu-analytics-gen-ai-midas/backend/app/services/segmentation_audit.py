"""
Segmentation audit trail (plan Section 15) and Modeler Notebook insight pins (Section 12.2 / 15).

- Audit events append to dataset metadata via DatasetManager (append-only list).
- Duplicate audit rows and duplicate pins are suppressed when the same idempotency_key
  is reused (e.g. client retries POST /segmentation/add-to-data).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("midas.app.services.segmentation_audit")


def find_prior_add_to_data(
    dataset_manager: Any,
    dataset_id: str,
    idempotency_key: str,
) -> Optional[Dict[str, Any]]:
    """Return data payload from a prior successful add_to_data with this idempotency_key, if any."""
    key = (idempotency_key or "").strip()
    if not key:
        return None
    log: List[Dict[str, Any]] = dataset_manager.get_segmentation_audit_log(dataset_id)
    for event in reversed(log):
        if event.get("event_type") != "add_to_data":
            continue
        data = event.get("data") or {}
        if data.get("idempotency_key") != key:
            continue
        if data.get("completed") is True and data.get("scheme_id") is not None and data.get("column_name"):
            return dict(data)
    return None


def append_audit_event(
    dataset_manager: Any,
    dataset_id: str,
    event_type: str,
    data: Dict[str, Any],
    *,
    actor: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> bool:
    """
    Append one audit row. If idempotency_key matches a prior event with the same event_type,
    the append is skipped (returns True as no-op success).
    """
    key = idempotency_key or (data or {}).get("idempotency_key")
    if key:
        key = str(key).strip()
    payload = dict(data or {})
    if key and "idempotency_key" not in payload:
        payload["idempotency_key"] = key

    if key:
        log = dataset_manager.get_segmentation_audit_log(dataset_id)
        for event in reversed(log[-300:]):
            if event.get("event_type") != event_type:
                continue
            prev = event.get("data") or {}
            if (prev.get("idempotency_key") or "").strip() == key:
                logger.info(
                    "segmentation audit dedupe: skip duplicate event_type=%s key=%s dataset=%s",
                    event_type,
                    key,
                    dataset_id,
                )
                return True

    evt = {
        "event_type": event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "data": payload,
    }
    ok = dataset_manager.append_segmentation_audit_event(dataset_id, evt)
    if not ok:
        logger.warning("segmentation audit append returned false dataset=%s type=%s", dataset_id, event_type)
    return bool(ok)


def append_insight_pin(dataset_id: str, pin: Dict[str, Any]) -> None:
    """
    Append a segmentation insight pin to MessageState (Modeler's Notebook).
    Skips if a pin with the same idempotency_key and pin_type already exists.
    """
    from app.services.message_state_service import message_state_manager

    try:
        state = message_state_manager.create_or_load_state(dataset_id, "")
    except Exception as exc:
        logger.warning("Insight pin skipped (MessageState unavailable) for %s: %s", dataset_id, exc)
        return
    if state is None:
        return

    pins = list(state.get("segmentation_insight_pins") or [])
    ik = (pin.get("idempotency_key") or "").strip() if pin.get("idempotency_key") else ""
    ptype = pin.get("pin_type")
    if ik and ptype:
        for existing in pins:
            if not isinstance(existing, dict):
                continue
            if (
                (existing.get("idempotency_key") or "").strip() == ik
                and existing.get("pin_type") == ptype
            ):
                logger.info(
                    "segmentation insight pin dedupe: skip duplicate pin_type=%s key=%s dataset=%s",
                    ptype,
                    ik,
                    dataset_id,
                )
                return

    pins.append(pin)
    if len(pins) > 500:
        pins = pins[-500:]
    state["segmentation_insight_pins"] = pins
    try:
        message_state_manager.save_state(dataset_id, state)
    except Exception as exc:
        logger.warning("Failed to save segmentation insight pins for %s: %s", dataset_id, exc)
