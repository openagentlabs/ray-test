import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from app.core.config import settings
from app.core.logging_config import get_logger


logger = get_logger(__name__)


class ModelTrainingDumpService:
    """Optional CSV dump utility for model-training intermediate artifacts."""

    def __init__(self) -> None:
        self.enabled = bool(getattr(settings, "MODEL_TRAINING_DUMP_ENABLED", False))
        self.base_dir = Path(getattr(settings, "MODEL_TRAINING_DUMP_DIR", "models/training_dumps"))

    @staticmethod
    def _safe_value(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, (list, tuple, set)):
            return [ModelTrainingDumpService._safe_value(v) for v in value]
        if isinstance(value, dict):
            return {str(k): ModelTrainingDumpService._safe_value(v) for k, v in value.items()}
        if hasattr(value, "item"):
            try:
                return value.item()  # numpy scalar-like values
            except Exception:
                pass
        return str(value)

    def _build_run_dir(self, training_type: str, dataset_id: str) -> Tuple[str, Path]:
        now = datetime.now()
        ts = now.strftime("%Y%m%d_%H%M%S")
        safe_type = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(training_type or "unknown")).strip("_") or "unknown"
        safe_dataset = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(dataset_id or "unknown")).strip("_") or "unknown"
        run_id = f"{ts}_{safe_type}_{safe_dataset}_{uuid4().hex[:6]}"
        run_dir = self.base_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        return run_id, run_dir

    @staticmethod
    def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
        if not rows:
            return
        fieldnames: List[str] = []
        seen = set()
        for row in rows:
            for key in row.keys():
                if key not in seen:
                    seen.add(key)
                    fieldnames.append(key)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow(row)

    @staticmethod
    def _iter_models(payload: Dict[str, Any]) -> Iterable[Tuple[Optional[str], Dict[str, Any]]]:
        global_results = payload.get("results")
        if isinstance(global_results, list):
            for model in global_results:
                if isinstance(model, dict):
                    yield None, model

        segment_results = payload.get("segment_results")
        if isinstance(segment_results, dict):
            for seg_key, seg_payload in segment_results.items():
                segment_id = str(seg_key).replace("segment_", "")
                if not isinstance(seg_payload, dict):
                    continue
                seg_models = seg_payload.get("results")
                if isinstance(seg_models, list):
                    for model in seg_models:
                        if isinstance(model, dict):
                            yield segment_id, model

    @staticmethod
    def _get_iterations(model: Dict[str, Any]) -> List[Dict[str, Any]]:
        history = model.get("iteration_history", [])
        if isinstance(history, list):
            return [h for h in history if isinstance(h, dict)]
        if isinstance(history, dict):
            nested = history.get("iterations", [])
            if isinstance(nested, list):
                return [h for h in nested if isinstance(h, dict)]
        return []

    def dump_training_payload(
        self,
        *,
        training_type: str,
        dataset_id: str,
        payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        if not self.enabled:
            return None

        try:
            safe_payload = self._safe_value(payload)
            if not isinstance(safe_payload, dict):
                safe_payload = {"payload": safe_payload}

            run_id, run_dir = self._build_run_dir(training_type, dataset_id)
            now_iso = datetime.now().isoformat()
            ctx = self._safe_value(context or {})
            if not isinstance(ctx, dict):
                ctx = {"context": str(ctx)}

            model_rows: List[Dict[str, Any]] = []
            iter_rows: List[Dict[str, Any]] = []
            hparam_rows: List[Dict[str, Any]] = []
            comparison_rows: List[Dict[str, Any]] = []

            for segment_id, model in self._iter_models(safe_payload):
                model_id = str(model.get("model_id") or "")
                algorithm = str(model.get("algorithm") or "")
                metrics = model.get("metrics") if isinstance(model.get("metrics"), dict) else {}
                cv_scores = model.get("cv_scores") if isinstance(model.get("cv_scores"), list) else []
                iterations = self._get_iterations(model)
                used_features = model.get("used_features") if isinstance(model.get("used_features"), list) else []

                cv_mean = None
                cv_std = None
                if cv_scores:
                    numeric_scores = [float(s) for s in cv_scores if isinstance(s, (int, float))]
                    if numeric_scores:
                        cv_mean = sum(numeric_scores) / len(numeric_scores)
                        variance = sum((x - cv_mean) ** 2 for x in numeric_scores) / len(numeric_scores)
                        cv_std = variance ** 0.5

                model_rows.append(
                    {
                        "run_id": run_id,
                        "timestamp": now_iso,
                        "dataset_id": dataset_id,
                        "training_type": training_type,
                        "segment_id": segment_id,
                        "model_id": model_id,
                        "algorithm": algorithm,
                        "best_iteration": model.get("best_iteration"),
                        "optimization_method": model.get("optimization_method"),
                        "cv_mean": cv_mean,
                        "cv_std": cv_std,
                        "feature_count": len(used_features) if used_features else None,
                        "feature_importance_count": metrics.get("feature_importance_count"),
                        "artifact_path": model.get("artifact_path"),
                        "metrics_json": json.dumps(metrics, ensure_ascii=True),
                    }
                )

                hyperparameters = model.get("hyperparameters")
                if isinstance(hyperparameters, dict):
                    for hp_name, hp_value in hyperparameters.items():
                        hparam_rows.append(
                            {
                                "run_id": run_id,
                                "timestamp": now_iso,
                                "dataset_id": dataset_id,
                                "training_type": training_type,
                                "segment_id": segment_id,
                                "model_id": model_id,
                                "algorithm": algorithm,
                                "parameter": hp_name,
                                "value": hp_value,
                            }
                        )

                for it in iterations:
                    it_metrics = it.get("metrics") if isinstance(it.get("metrics"), dict) else {}
                    iter_rows.append(
                        {
                            "run_id": run_id,
                            "timestamp": now_iso,
                            "dataset_id": dataset_id,
                            "training_type": training_type,
                            "segment_id": segment_id,
                            "model_id": model_id,
                            "algorithm": algorithm,
                            "iteration": it.get("iteration"),
                            "score": it.get("score"),
                            "improvement": it.get("improvement"),
                            "status": it.get("status"),
                            "feature_importance_count": it.get("feature_importance_count"),
                            "metrics_json": json.dumps(it_metrics, ensure_ascii=True),
                            "hyperparameters_json": json.dumps(it.get("hyperparameters"), ensure_ascii=True),
                        }
                    )

            best_model_selection = safe_payload.get("best_model_selection")
            if isinstance(best_model_selection, dict):
                metrics_comparison = best_model_selection.get("metrics_comparison")
                if isinstance(metrics_comparison, list):
                    for row in metrics_comparison:
                        if not isinstance(row, dict):
                            continue
                        comparison_rows.append(
                            {
                                "run_id": run_id,
                                "timestamp": now_iso,
                                "dataset_id": dataset_id,
                                "training_type": training_type,
                                "rank": row.get("rank"),
                                "algorithm": row.get("algorithm"),
                                "model_id": row.get("model_id"),
                                "is_best": row.get("is_best"),
                                "metrics_json": json.dumps(row.get("metrics", {}), ensure_ascii=True),
                            }
                        )

            metadata_row = {
                "run_id": run_id,
                "timestamp": now_iso,
                "dataset_id": dataset_id,
                "training_type": training_type,
                "total_models": len(model_rows),
                "total_iterations": len(iter_rows),
                "has_segment_results": isinstance(safe_payload.get("segment_results"), dict),
                "payload_keys": json.dumps(sorted(list(safe_payload.keys())), ensure_ascii=True),
                "context_json": json.dumps(ctx, ensure_ascii=True),
            }

            self._write_csv(run_dir / "run_metadata.csv", [metadata_row])
            self._write_csv(run_dir / "model_final_results.csv", model_rows)
            self._write_csv(run_dir / "model_iteration_results.csv", iter_rows)
            self._write_csv(run_dir / "model_hyperparameters.csv", hparam_rows)
            self._write_csv(run_dir / "model_comparison.csv", comparison_rows)
            self._write_csv(
                run_dir / "payload_snapshot.csv",
                [{"run_id": run_id, "timestamp": now_iso, "payload_json": json.dumps(safe_payload, ensure_ascii=True)}],
            )

            logger.info(f"Training dump saved for run {run_id} at {run_dir}")
            return str(run_dir)
        except Exception as exc:
            logger.warning(f"Failed to write training dump for dataset {dataset_id}: {exc}")
            return None


model_training_dump_service = ModelTrainingDumpService()
