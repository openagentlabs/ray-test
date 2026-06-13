"""
Standalone RFE worker entrypoint.

Use one of:
    python -m app.services.model_training_rfe.worker
    python rfe_worker.py

Either form BLPOPs the Redis queue (when RFE_SCALING_MODE=redis) and runs
RFE jobs to completion. Stateless - scale `replicas: N` via the k8s
`rfe-worker-deployment.yaml`.
"""

from app.services.model_training_rfe.worker import main

if __name__ == "__main__":
    main()
