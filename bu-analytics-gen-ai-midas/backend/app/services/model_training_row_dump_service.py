import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from app.core.config import settings
from app.core.logging_config import get_logger


logger = get_logger(__name__)


class ModelTrainingRowDumpService:
    """Optional row-level dump utility for phase1 training outputs."""

    def __init__(self) -> None:
        self.enabled = bool(getattr(settings, "MODEL_TRAINING_DUMP_ENABLED", False))
        base_dir = Path(getattr(settings, "MODEL_TRAINING_DUMP_DIR", "models/training_dumps"))
        self.base_dir = base_dir / "results"

    @staticmethod
    def _safe_scalar(value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if hasattr(value, "item"):
            try:
                return value.item()
            except Exception:
                return str(value)
        return str(value)

    @staticmethod
    def _as_array(values: Any) -> Optional[np.ndarray]:
        if values is None:
            return None
        try:
            if isinstance(values, np.ndarray):
                return values
            if hasattr(values, "to_numpy"):
                return values.to_numpy()
            if isinstance(values, (list, tuple)):
                return np.asarray(values)
            return np.asarray(values)
        except Exception:
            return None

    @staticmethod
    def _row_indices(y_true: Any) -> List[Any]:
        idx = getattr(y_true, "index", None)
        if idx is not None:
            try:
                return [ModelTrainingRowDumpService._safe_scalar(v) for v in list(idx)]
            except Exception:
                pass
        y_arr = ModelTrainingRowDumpService._as_array(y_true)
        if y_arr is None:
            return []
        return list(range(int(y_arr.shape[0])))

    @staticmethod
    def _write_csv(path: Path, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> None:
        if not rows:
            return
        if fieldnames is None:
            fieldnames = []
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
    def _flatten_metric_rows(model_id: str, split: str, metrics: Dict[str, Any]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for key, value in metrics.items():
            safe_value = value
            if isinstance(value, (dict, list)):
                safe_value = json.dumps(value, ensure_ascii=True)
            elif value is not None:
                safe_value = ModelTrainingRowDumpService._safe_scalar(value)
            rows.append(
                {
                    "model_id": model_id,
                    "split": split,
                    "metric_name": key,
                    "value": safe_value,
                }
            )
        return rows

    @staticmethod
    def _extract_split_metrics(performance_metrics: Dict[str, Any], split: str) -> Dict[str, Any]:
        prefix = f"{split}_"
        extracted: Dict[str, Any] = {}
        for key, value in performance_metrics.items():
            if key.startswith(prefix):
                extracted[key[len(prefix) :]] = value
        if not extracted and split == "test":
            # Keep backward compatibility where legacy fields represent test metrics.
            for key, value in performance_metrics.items():
                if key.startswith("train_"):
                    continue
                extracted[key] = value
        return extracted

    @staticmethod
    def _build_prediction_rows(
        *,
        split: str,
        y_true: Any,
        y_pred: Any,
        y_proba: Any,
        algorithm_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        y_true_arr = ModelTrainingRowDumpService._as_array(y_true)
        y_pred_arr = ModelTrainingRowDumpService._as_array(y_pred)
        if y_true_arr is None or y_pred_arr is None:
            return []
        if y_true_arr.shape[0] != y_pred_arr.shape[0]:
            return []

        row_indices = ModelTrainingRowDumpService._row_indices(y_true)
        proba_arr = ModelTrainingRowDumpService._as_array(y_proba)
        if proba_arr is not None and proba_arr.shape[0] != y_true_arr.shape[0]:
            proba_arr = None

        rows: List[Dict[str, Any]] = []
        for i in range(int(y_true_arr.shape[0])):
            row: Dict[str, Any] = {
                "split": split,
                "row_index": row_indices[i] if i < len(row_indices) else i,
                "y_true": ModelTrainingRowDumpService._safe_scalar(y_true_arr[i]),
                "y_pred": ModelTrainingRowDumpService._safe_scalar(y_pred_arr[i]),
            }
            if algorithm_name:
                row["algorithm_name"] = algorithm_name

            if proba_arr is not None:
                if proba_arr.ndim == 1:
                    row["y_proba_class_1"] = ModelTrainingRowDumpService._safe_scalar(proba_arr[i])
                elif proba_arr.ndim == 2:
                    for cls_idx in range(int(proba_arr.shape[1])):
                        row[f"y_proba_class_{cls_idx}"] = ModelTrainingRowDumpService._safe_scalar(
                            proba_arr[i, cls_idx]
                        )

            rows.append(row)
        return rows

    @staticmethod
    def _load_training_results(model_id: str) -> Dict[str, Any]:
        path = Path("models") / f"{model_id}_training_results.json"
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def dump_phase1_row_artifacts(
        self,
        *,
        model_id: str,
        algorithm_name: str,
        dataset_id: Optional[str],
        target_column: Optional[str],
        problem_type: str,
        y_train: Any,
        y_pred_train: Any,
        y_proba_train: Any,
        y_test: Any,
        y_pred_test: Any,
        y_proba_test: Any,
        performance_metrics: Dict[str, Any],
    ) -> Optional[str]:
        if not self.enabled:
            return None

        try:
            model_dir = self.base_dir / str(model_id)
            hp_dir = model_dir / "hyperparameter_iterations"
            model_dir.mkdir(parents=True, exist_ok=True)
            hp_dir.mkdir(parents=True, exist_ok=True)

            train_rows = self._build_prediction_rows(
                split="train",
                y_true=y_train,
                y_pred=y_pred_train,
                y_proba=y_proba_train,
            )
            test_rows = self._build_prediction_rows(
                split="test",
                y_true=y_test,
                y_pred=y_pred_test,
                y_proba=y_proba_test,
            )
            all_rows = train_rows + test_rows

            self._write_csv(
                model_dir / "predictions_train.csv",
                train_rows,
                fieldnames=[
                    "split",
                    "row_index",
                    "y_true",
                    "y_pred",
                    "y_proba_class_0",
                    "y_proba_class_1",
                ],
            )
            self._write_csv(
                model_dir / "predictions_test.csv",
                test_rows,
                fieldnames=[
                    "split",
                    "row_index",
                    "y_true",
                    "y_pred",
                    "y_proba_class_0",
                    "y_proba_class_1",
                ],
            )
            # Keep compatibility with consumers that expect this file.
            self._write_csv(
                model_dir / "test_predictions_post_training.csv",
                test_rows,
                fieldnames=[
                    "split",
                    "row_index",
                    "y_true",
                    "y_pred",
                    "y_proba_class_0",
                    "y_proba_class_1",
                ],
            )
            self._write_csv(
                model_dir / "predictions_all_splits.csv",
                all_rows,
                fieldnames=[
                    "split",
                    "row_index",
                    "y_true",
                    "y_pred",
                    "y_proba_class_0",
                    "y_proba_class_1",
                ],
            )

            split_metric_rows: List[Dict[str, Any]] = []
            train_metrics = self._extract_split_metrics(performance_metrics, "train")
            test_metrics = self._extract_split_metrics(performance_metrics, "test")
            split_metric_rows.extend(self._flatten_metric_rows(model_id, "train", train_metrics))
            split_metric_rows.extend(self._flatten_metric_rows(model_id, "test", test_metrics))
            self._write_csv(model_dir / "metrics_on_dumped_splits.csv", split_metric_rows)

            phase1_metric_rows = []
            for key, value in performance_metrics.items():
                safe_value = value
                if isinstance(value, (dict, list)):
                    safe_value = json.dumps(value, ensure_ascii=True)
                phase1_metric_rows.append(
                    {"model_id": model_id, "metric_name": key, "value": self._safe_scalar(safe_value)}
                )
            self._write_csv(model_dir / "meea_phase1_performance_metrics.csv", phase1_metric_rows)

            train_vs_test_rows = []
            for metric_name, train_value in train_metrics.items():
                if metric_name not in test_metrics:
                    continue
                test_value = test_metrics.get(metric_name)
                delta = None
                if isinstance(train_value, (int, float)) and isinstance(test_value, (int, float)):
                    delta = float(train_value) - float(test_value)
                train_vs_test_rows.append(
                    {
                        "model_id": model_id,
                        "metric_name": metric_name,
                        "train_value": self._safe_scalar(train_value),
                        "test_value": self._safe_scalar(test_value),
                        "delta": self._safe_scalar(delta),
                    }
                )
            self._write_csv(model_dir / "meea_phase1_train_vs_test_metrics.csv", train_vs_test_rows)

            training_snapshot = self._load_training_results(model_id)
            best_iteration_payload = {
                "phase": "random_search",
                "iteration": training_snapshot.get("best_iteration"),
                "best_iteration": training_snapshot.get("best_iteration"),
                "iteration_dump_best_only": True,
                "algorithm": training_snapshot.get("algorithm") or algorithm_name,
                "algorithm_name": algorithm_name,
                "dataset_id": dataset_id,
                "target_column": target_column,
                "problem_type": problem_type,
                "score": None,
                "improvement": 0.0,
                "hyperparameters": training_snapshot.get("hyperparameters", {}),
                "metrics": training_snapshot.get("metrics", {}),
                "feature_importance_count": (
                    training_snapshot.get("metrics", {}) or {}
                ).get("feature_importance_count"),
                "cv_folds_scores": training_snapshot.get("cv_scores", []),
            }
            self._write_csv(
                hp_dir / "best_iteration_train_predictions.csv",
                self._build_prediction_rows(
                    split="train",
                    y_true=y_train,
                    y_pred=y_pred_train,
                    y_proba=y_proba_train,
                    algorithm_name=algorithm_name,
                ),
            )
            with (hp_dir / "best_iteration.json").open("w", encoding="utf-8") as handle:
                json.dump(best_iteration_payload, handle, indent=2, default=str)
            with (hp_dir / ".session_meta.json").open("w", encoding="utf-8") as handle:
                json.dump(
                    {"written_at": datetime.utcnow().isoformat(), "model_id": model_id},
                    handle,
                    indent=2,
                    default=str,
                )

            dump_summary = {
                "model_id": model_id,
                "algorithm_name": algorithm_name,
                "dataset_id": dataset_id,
                "target_column": target_column,
                "problem_type": problem_type,
                "dump_dir": str(model_dir.resolve()),
                "splits": {
                    "train": {
                        "written_rows": len(train_rows),
                        "truncated": False,
                    },
                    "test": {
                        "written_rows": len(test_rows),
                        "truncated": False,
                        "post_training_csv": "test_predictions_post_training.csv",
                        "source": "model_evaluation_phase1",
                    },
                },
                "phase1_meea_sampling": {},
                "metrics_on_dumped_rows": {
                    "train": train_metrics,
                    "test": test_metrics,
                },
                "training_results_snapshot": {
                    "metrics": training_snapshot.get("metrics", {}),
                    "cv_scores": training_snapshot.get("cv_scores", []),
                    "used_features": training_snapshot.get("used_features", []),
                },
            }
            with (model_dir / "dump_summary.json").open("w", encoding="utf-8") as handle:
                json.dump(dump_summary, handle, indent=2, default=str)

            logger.info(f"[RowDump] Wrote row-level artifacts for {model_id} at {model_dir}")
            return str(model_dir)
        except Exception as exc:
            logger.warning(f"[RowDump] Failed to write row-level artifacts for {model_id}: {exc}")
            return None


model_training_row_dump_service = ModelTrainingRowDumpService()
