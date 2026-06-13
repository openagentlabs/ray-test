# API endpoint latency inventory

This table lists **every registered HTTP route** on the MIDAS FastAPI app and a **qualitative latency profile**.

**Important:** There are **no fixed millisecond guarantees** in code for most routes. Actual times depend on dataset size, concurrency, Bedrock/RDS latency, and cache state. For measured p50/p95/p99 per route, run CloudWatch Logs Insights on `event = "http_request"` — see [`docs/observability-runbook-slow-endpoints.md`](../../docs/observability-runbook-slow-endpoints.md).

| Method | Path | Typical latency profile |
|---|---|---|
| GET | `/` | Fast — health / root (typically <500 ms) |
| POST | `/api/v1/analyze-dataset` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/auth/cognito/exchange` | Medium — token mint / user lookup (often sub-second to a few seconds) |
| GET | `/api/v1/auth/cognito/login-url` | Fast — auth metadata / validation (usually <1 s) |
| POST | `/api/v1/auth/cognito/logout` | Fast–medium — auth/session (typically <2 s) |
| POST | `/api/v1/auth/cognito/logout-everywhere` | Fast–medium — auth/session (typically <2 s) |
| POST | `/api/v1/auth/cognito/refresh` | Medium — token mint / user lookup (often sub-second to a few seconds) |
| POST | `/api/v1/auth/login` | Medium — token mint / user lookup (often sub-second to a few seconds) |
| POST | `/api/v1/auth/logout` | Fast–medium — auth/session (typically <2 s) |
| GET | `/api/v1/auth/me` | Fast — auth metadata / validation (usually <1 s) |
| POST | `/api/v1/auth/refresh` | Medium — token refresh (often sub-second to a few seconds) |
| POST | `/api/v1/auth/register` | Medium — token mint / user lookup (often sub-second to a few seconds) |
| GET | `/api/v1/auth/users` | Fast–medium — auth/session (typically <2 s) |
| DELETE | `/api/v1/auth/users/{user_id}` | Fast–medium — auth/session (typically <2 s) |
| PUT | `/api/v1/auth/users/{user_id}` | Fast–medium — auth/session (typically <2 s) |
| POST | `/api/v1/auth/verify-token` | Fast — auth metadata / validation (usually <1 s) |
| POST | `/api/v1/auto-train-model` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/auto-training/analyze` | Training pipeline — long-running when not */start (see route) |
| POST | `/api/v1/auto-training/analyze/start` | Job kickoff — HTTP usually <1 s; work continues async |
| GET | `/api/v1/auto-training/analyze/status/{job_id}` | Fast — job status poll (usually <1 s) |
| POST | `/api/v1/auto-training/cancel/{job_id}` | Fast–medium — control / selection APIs |
| GET | `/api/v1/auto-training/meea-status/{dataset_id}` | Fast–medium — control / selection APIs |
| POST | `/api/v1/auto-training/run` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/auto-training/select-algorithms` | Fast–medium — control / selection APIs |
| POST | `/api/v1/auto-training/select-best-model` | Fast–medium — control / selection APIs |
| POST | `/api/v1/auto-training/select-variables` | Fast–medium — control / selection APIs |
| GET | `/api/v1/auto-training/status/{job_id}` | Fast — job status poll (usually <1 s) |
| GET | `/api/v1/auto-training/stream/{job_id}` | Long-lived — SSE/stream; not one HTTP completion time |
| POST | `/api/v1/calculate-vif-correlation/start` | Job kickoff — HTTP usually <1 s; work continues async |
| GET | `/api/v1/calculate-vif-correlation/status/{job_id}` | Fast — job status poll (usually <1 s) |
| POST | `/api/v1/chat` | LLM / agent — typically multi-second; can exceed 1 minute |
| GET | `/api/v1/chat/states` | Fast–medium — reads stored chat state |
| GET | `/api/v1/chat/{dataset_id}/history` | Fast–medium — reads stored chat state |
| DELETE | `/api/v1/chat/{dataset_id}/reset` | Fast–medium — clears chat history |
| POST | `/api/v1/combine-presplit` | Heavy compute / training — seconds to tens of minutes |
| GET | `/api/v1/dataset-preview/{dataset_id}` | Medium — dataframe preview head |
| POST | `/api/v1/dataset-type-classification-by-id` | Heavy compute / training — seconds to tens of minutes |
| GET | `/api/v1/dataset-type-classification/status/{job_id}` | Fast — job status poll (usually <1 s) |
| POST | `/api/v1/dataset/scope` | Variable — depends on payload; often <2 s for small datasets |
| GET | `/api/v1/datasets` | Variable — depends on payload; often <2 s for small datasets |
| DELETE | `/api/v1/datasets/{dataset_id}` | Medium — delete + cleanup |
| POST | `/api/v1/datasets/{dataset_id}/classify-variables` | Heavy — full-dataset pass; often >1 s |
| GET | `/api/v1/datasets/{dataset_id}/classify-variables/status` | Heavy — full-dataset pass; often >1 s |
| GET | `/api/v1/datasets/{dataset_id}/column-distribution-by-scope/{column_name}` | Medium–heavy — depends on column cardinality and rows |
| GET | `/api/v1/datasets/{dataset_id}/column-distribution/{column_name}` | Medium–heavy — depends on column cardinality and rows |
| GET | `/api/v1/datasets/{dataset_id}/column-info` | Medium — schema/stats aggregation |
| GET | `/api/v1/datasets/{dataset_id}/column-info-by-scope` | Medium — schema/stats aggregation |
| POST | `/api/v1/datasets/{dataset_id}/column-insights` | Heavy — multi-column analysis; often >1 s |
| GET | `/api/v1/datasets/{dataset_id}/compare-column-stats` | Heavy I/O — scales with rows/columns; can be many seconds |
| PUT | `/api/v1/datasets/{dataset_id}/config` | Fast–medium — metadata update |
| POST | `/api/v1/datasets/{dataset_id}/cross-algorithm-recommendation` | Medium–heavy — scales with dataset size |
| GET | `/api/v1/datasets/{dataset_id}/download-column-stats` | Heavy I/O — scales with rows/columns; can be many seconds |
| GET | `/api/v1/datasets/{dataset_id}/download-processed` | Heavy I/O — scales with rows/columns; can be many seconds |
| GET | `/api/v1/datasets/{dataset_id}/dqs` | Heavy — DQS scan; often multi-second on large datasets |
| GET | `/api/v1/datasets/{dataset_id}/dqs-by-scope` | Heavy — DQS scan; often multi-second on large datasets |
| POST | `/api/v1/datasets/{dataset_id}/dqs-recommendations` | Heavy — DQS scan; often multi-second on large datasets |
| GET | `/api/v1/datasets/{dataset_id}/eda-snapshot` | Heavy I/O — scales with rows/columns; can be many seconds |
| GET | `/api/v1/datasets/{dataset_id}/export` | Heavy I/O — scales with rows/columns; can be many seconds |
| POST | `/api/v1/datasets/{dataset_id}/identify-duplicates` | Heavy — row scan; scales with dataset size |
| GET | `/api/v1/datasets/{dataset_id}/overview-bundle` | Heavy I/O — scales with rows/columns; can be many seconds |
| GET | `/api/v1/datasets/{dataset_id}/raw-data` | Heavy I/O — scales with rows/columns; can be many seconds |
| POST | `/api/v1/datasets/{dataset_id}/remove-duplicates` | Heavy — row scan; scales with dataset size |
| GET | `/api/v1/datasets/{dataset_id}/stats` | Medium — scales with dataset size (often <2 s small data) |
| POST | `/api/v1/detect-problem-type` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/detect-segments` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/documentation/calculate-event-rate` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/download` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/generate-ai-explainability-writeup` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/generate-data-quality-summary` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/generate-data-summary` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/generate-decile-progression-writeup` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/generate-feature-engineering-writeup` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/generate-model-objective` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/generate-model-validation-writeup` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/generate-monotonicity-summary` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/generate-quality-changes-writeup` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/generate-sampling-plan-writeup` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/generate-segmentation-understanding` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/generate-target-definition` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/get-column-stats` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/get-data-insights` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/get-model-performance` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/get-quality-check-plan` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/get-sampling-plan` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/get-transformed-variables` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/documentation/get-variable-analysis` | LLM — typically multi-second to minutes per section |
| POST | `/api/v1/exclusion-preview` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/exclusion-preview-by-id` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/execute-code` | LLM / agent — typically multi-second; can exceed 1 minute |
| GET | `/api/v1/export-model/{model_id}` | Variable — depends on payload; often <2 s for small datasets |
| GET | `/api/v1/export-segment-model/{model_id}/{segment_id}` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/feature-transformation/start` | Job kickoff — HTTP usually <1 s; work continues async |
| GET | `/api/v1/feature-transformation/status/{job_id}` | Fast — job status poll (usually <1 s) |
| POST | `/api/v1/finalize-presplit` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/generate-knowledge-graph` | Heavy — KG build; commonly many seconds to minutes |
| POST | `/api/v1/generate-qc-template/{template_type}` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/get-available-variables` | Variable — depends on payload; often <2 s for small datasets |
| GET | `/api/v1/get-codebook/{training_mode}/{training_type}` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/get-recommended-metrics` | Variable — depends on payload; often <2 s for small datasets |
| GET | `/api/v1/ingest-stream/{dataset_id}` | Long-lived — SSE/stream; not one HTTP completion time |
| POST | `/api/v1/ingest-stream/{dataset_id}/test-publish` | Long-lived — SSE/stream; not one HTTP completion time |
| POST | `/api/v1/insights/bivariate/all` | Heavy compute / training — seconds to tens of minutes |
| GET | `/api/v1/insights/bivariate/{dataset_id}/variable/{variable_name}` | Medium — single-variable analysis |
| POST | `/api/v1/insights/correlation-matrix` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/insights/correlation-ratio-analysis` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/insights/correlation/analyze` | Heavy compute / training — seconds to tens of minutes |
| GET | `/api/v1/insights/correlation/{dataset_id}/heatmap` | Medium–heavy — image payload; depends on matrix size |
| GET | `/api/v1/insights/correlation/{dataset_id}/heatmap/categorical` | Medium–heavy — image payload; depends on matrix size |
| GET | `/api/v1/insights/correlation/{dataset_id}/variable/{variable_name}` | Medium — single-variable analysis |
| POST | `/api/v1/insights/iv-analysis` | Heavy compute / training — seconds to tens of minutes |
| GET | `/api/v1/insights/jobs/status/{job_id}` | Fast — job status poll (usually <1 s) |
| POST | `/api/v1/insights/vif-analysis` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/insights/vif-analysis-dedicated` | Heavy compute / training — seconds to tens of minutes |
| GET | `/api/v1/keepalive` | Fast — keepalive |
| GET | `/api/v1/knowledge-graph-progress/{dataset_id}` | Variable — depends on payload; often <2 s for small datasets |
| GET | `/api/v1/knowledge-graph-stream/{dataset_id}` | Long-lived — streaming progress |
| GET | `/api/v1/llm-config` | Fast |
| GET | `/api/v1/model-codebook/{algorithm}` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/model-evaluation/compare` | Heavy — evaluation / compare jobs |
| POST | `/api/v1/model-evaluation/evaluate-all-existing` | Heavy — evaluation / compare jobs |
| POST | `/api/v1/model-evaluation/evaluate-existing/{model_id}` | Heavy — evaluation / compare jobs |
| GET | `/api/v1/model-evaluation/list/all` | Medium — reads precomputed artifacts; usually 1–10 s |
| GET | `/api/v1/model-evaluation/list/by-dataset` | Medium — reads precomputed artifacts; usually 1–10 s |
| DELETE | `/api/v1/model-evaluation/{model_id}` | Medium — reads precomputed artifacts; usually 1–10 s |
| GET | `/api/v1/model-evaluation/{model_id}` | Medium — reads precomputed artifacts; usually 1–10 s |
| GET | `/api/v1/model-evaluation/{model_id}/chat-summary` | Medium — reads precomputed artifacts; usually 1–10 s |
| GET | `/api/v1/model-evaluation/{model_id}/error-patterns` | Medium — reads precomputed artifacts; usually 1–10 s |
| GET | `/api/v1/model-evaluation/{model_id}/explainability` | Medium — reads precomputed artifacts; usually 1–10 s |
| GET | `/api/v1/model-evaluation/{model_id}/feature-importance` | Medium — reads precomputed artifacts; usually 1–10 s |
| GET | `/api/v1/model-evaluation/{model_id}/granular-accuracy` | Medium — reads precomputed artifacts; usually 1–10 s |
| GET | `/api/v1/model-evaluation/{model_id}/granular-accuracy/by-segments` | Medium — reads precomputed artifacts; usually 1–10 s |
| GET | `/api/v1/model-evaluation/{model_id}/pdp-data` | Medium — reads precomputed artifacts; usually 1–10 s |
| GET | `/api/v1/model-evaluation/{model_id}/performance` | Medium — reads precomputed artifacts; usually 1–10 s |
| GET | `/api/v1/model-evaluation/{model_id}/phase/{phase_num}` | Medium — reads precomputed artifacts; usually 1–10 s |
| GET | `/api/v1/model-evaluation/{model_id}/prediction-confidence` | Medium — reads precomputed artifacts; usually 1–10 s |
| POST | `/api/v1/model-evaluation/{model_id}/recalculate-explainability` | Heavy — model re-run; often many seconds+ |
| GET | `/api/v1/model-evaluation/{model_id}/samples` | Medium — reads precomputed artifacts; usually 1–10 s |
| POST | `/api/v1/model-evaluation/{original_model_id}/evaluate-pruned` | Heavy — evaluation / compare jobs |
| POST | `/api/v1/model-training/lr-backward-elimination` | Heavy compute / training — seconds to tens of minutes |
| GET | `/api/v1/models/{model_id}/download-artifacts` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/partition-preview` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/partition-preview-by-id` | Heavy compute / training — seconds to tens of minutes |
| GET | `/api/v1/projects` | Fast — CRUD on project metadata |
| POST | `/api/v1/projects` | Fast — CRUD on project metadata |
| DELETE | `/api/v1/projects/{project_id}` | Fast — CRUD on project metadata |
| GET | `/api/v1/projects/{project_id}` | Fast — CRUD on project metadata |
| PUT | `/api/v1/projects/{project_id}` | Fast — CRUD on project metadata |
| POST | `/api/v1/qc/next-step` | LLM / QC flow — typically multi-second+ |
| POST | `/api/v1/qc/regenerate-code` | LLM / QC flow — typically multi-second+ |
| POST | `/api/v1/qc/skip-treatment` | LLM / QC flow — typically multi-second+ |
| POST | `/api/v1/rfe/cancel/{job_id}` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/rfe/finalize` | Variable — depends on payload; often <2 s for small datasets |
| GET | `/api/v1/rfe/monotone/{dataset_id}` | Variable — depends on payload; often <2 s for small datasets |
| GET | `/api/v1/rfe/result/{job_id}` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/rfe/start` | Job kickoff — HTTP usually <1 s; work continues async |
| GET | `/api/v1/rfe/status/{job_id}` | Fast — job status poll (usually <1 s) |
| GET | `/api/v1/rfe/stream/{job_id}` | Long-lived — SSE/stream; not one HTTP completion time |
| POST | `/api/v1/run-auto-segmentation` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/run-segmentation` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/segment-auto-training/cancel/{job_id}` | Fast–medium — control / selection APIs |
| POST | `/api/v1/segment-auto-training/run` | Heavy compute / training — seconds to tens of minutes |
| GET | `/api/v1/segment-auto-training/status/{job_id}` | Fast — job status poll (usually <1 s) |
| GET | `/api/v1/segment-auto-training/{model_id}/segment/{segment_id}` | Training pipeline — long-running when not */start (see route) |
| GET | `/api/v1/segment-auto-training/{model_id}/unified-results` | Training pipeline — long-running when not */start (see route) |
| POST | `/api/v1/segment-profiling/start` | Job kickoff — HTTP usually <1 s; work continues async |
| GET | `/api/v1/segment-profiling/status/{job_id}` | Fast — job status poll (usually <1 s) |
| POST | `/api/v1/segment-training/cancel/{job_id}` | Variable — depends on payload; often <2 s for small datasets |
| GET | `/api/v1/segment-training/preview` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/segment-training/run` | Heavy compute / training — seconds to tens of minutes |
| GET | `/api/v1/segment-training/status/{job_id}` | Fast — job status poll (usually <1 s) |
| GET | `/api/v1/segment-training/{model_id}/compare` | Variable — depends on payload; often <2 s for small datasets |
| GET | `/api/v1/segment-training/{model_id}/history` | Variable — depends on payload; often <2 s for small datasets |
| GET | `/api/v1/segment-training/{model_id}/results` | Variable — depends on payload; often <2 s for small datasets |
| GET | `/api/v1/segment-training/{model_id}/screen` | Variable — depends on payload; often <2 s for small datasets |
| GET | `/api/v1/segment-training/{model_id}/unified-results` | Variable — depends on payload; often <2 s for small datasets |
| GET | `/api/v1/segmentation-model-evaluation/segments/{dataset_id}` | Variable — depends on payload; often <2 s for small datasets |
| GET | `/api/v1/segmentation-model-evaluation/{dataset_id}/{segment_id}` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/segmentation/add-to-data` | Medium–heavy — segmentation writes + recompute |
| GET | `/api/v1/segmentation/audit-log/{dataset_id}` | Fast–medium — reads schemes / audit data |
| POST | `/api/v1/segmentation/edit-cutoff` | Medium–heavy — segmentation writes + recompute |
| POST | `/api/v1/segmentation/generate-narrative` | LLM — typically multi-second+ |
| GET | `/api/v1/segmentation/insight-pins/{dataset_id}` | Fast–medium — reads schemes / audit data |
| POST | `/api/v1/segmentation/merge-segments` | Medium–heavy — segmentation writes + recompute |
| POST | `/api/v1/segmentation/move-categorical-value` | Medium–heavy — segmentation writes + recompute |
| POST | `/api/v1/segmentation/run` | Heavy compute / training — seconds to tens of minutes |
| GET | `/api/v1/segmentation/schemes/{dataset_id}` | Fast–medium — reads schemes / audit data |
| GET | `/api/v1/segmentation/schemes/{dataset_id}/{scheme_id}` | Fast–medium — reads schemes / audit data |
| GET | `/api/v1/segmentation/top-variables/{dataset_id}` | Fast–medium — reads schemes / audit data |
| POST | `/api/v1/segmentation/validate-rules` | Medium–heavy — segmentation writes + recompute |
| GET | `/api/v1/segmented-dataset-preview/{dataset_id}` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/train-global-model` | Heavy compute / training — seconds to tens of minutes |
| GET | `/api/v1/train-global-model/status/{job_id}` | Fast — job status poll (usually <1 s) |
| POST | `/api/v1/train-multiple-models` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/train-multiple-models/cancel/{job_id}` | Heavy compute / training — seconds to tens of minutes |
| GET | `/api/v1/train-multiple-models/status/{job_id}` | Fast — job status poll (usually <1 s) |
| GET | `/api/v1/training-logs/{model_id}` | Medium — log volume dependent |
| POST | `/api/v1/training/lock-variables` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/update-custom-treatments` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/upload` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/upload-chunked/init` | Heavy compute / training — seconds to tens of minutes |
| DELETE | `/api/v1/upload-chunked/{upload_id}` | Heavy compute / training — seconds to tens of minutes |
| PATCH | `/api/v1/upload-chunked/{upload_id}` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/upload-chunked/{upload_id}/finalize` | Heavy compute / training — seconds to tens of minutes |
| GET | `/api/v1/upload-chunked/{upload_id}/status` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/user-knowledge/preferences` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/user-knowledge/upload` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/validate-unique-ids-by-id` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/validate-variable-selection` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/variable-review/apply` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/variable-review/preview` | Variable — depends on payload; often <2 s for small datasets |
| POST | `/api/v1/variable-review/run` | Heavy compute / training — seconds to tens of minutes |
| POST | `/api/v1/vector-store/reinitialize` | Heavy compute / training — seconds to tens of minutes |
| GET | `/docs` | Fast — OpenAPI / docs (typically <200 ms) |
| GET | `/docs/oauth2-redirect` | Fast — OpenAPI / docs (typically <200 ms) |
| GET | `/health` | Fast — health / root (typically <500 ms) |
| GET | `/openapi.json` | Fast — OpenAPI / docs (typically <200 ms) |
| GET | `/redoc` | Fast — OpenAPI / docs (typically <200 ms) |

**Total routes:** 217
