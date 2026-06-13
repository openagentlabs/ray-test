# MIDAS ec2-mt-test one-shot batch pod.
#
# Build from the repository root (build context = repo root):
#   docker build --platform linux/amd64 \
#     -f deploy/ecs-app/docker/midas-ec2-mt-test-svc/Dockerfile \
#     -t midas-ec2-mt-test-svc:local .
#
# The ec2-mt-test/ app code is copied in at build time. The entrypoint
# script is written inline (via heredoc in a RUN layer) so it is never
# subject to .dockerignore exclusions.
#
# Runtime environment variables (injected by the Helm Job spec):
#   AWS_REGION          - us-east-1
#   S3_RESULTS_BUCKET   - e.g. keith-bucket-test-001
#   S3_RESULTS_PREFIX   - e.g. results
#
# IRSA: the pod ServiceAccount carries an EKS IRSA annotation; the AWS CLI
# picks up the web-identity token automatically. No credentials in the image.

FROM python:3.11-slim-bookworm

WORKDIR /workspace/ec2-mt-test

# Install OS dependencies: build tools for native wheels (catboost, lightgbm),
# plus the AWS CLI v1 from Debian's package repo.
RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        build-essential \
        awscli \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching.
COPY ec2-mt-test/requirements-ec2.txt /tmp/requirements-ec2.txt
RUN pip install --no-cache-dir -r /tmp/requirements-ec2.txt

# Copy application code (ec2-mt-test/ is not excluded by .dockerignore).
COPY ec2-mt-test/ /workspace/ec2-mt-test/

# Create the data directory so generate_smoke_data.py and run_batch.py can write into it.
RUN mkdir -p /workspace/ec2-mt-test/data

# Write the entrypoint inline so .dockerignore (which excludes deploy/) cannot
# prevent it reaching the build context.
RUN cat > /usr/local/bin/entrypoint.sh <<'ENTRYPOINT_EOF'
#!/usr/bin/env bash
# Entrypoint for the midas-ec2-mt-test-svc Job pod.
# 1. Generate smoke CSV   (scripts/generate_smoke_data.py -> data/smoke_ml.csv)
# 2. Time run_batch.py    (--data-dir data)
# 3. Write data/timing.txt
# 4. Upload data/ tree to S3 via IRSA credentials
set -euo pipefail
: "${AWS_REGION:?AWS_REGION is required}"
: "${S3_RESULTS_BUCKET:?S3_RESULTS_BUCKET is required}"
: "${S3_RESULTS_PREFIX:?S3_RESULTS_PREFIX is required}"
cd /workspace/ec2-mt-test
echo "[ec2-mt-test] Generating smoke CSV..."
python3 scripts/generate_smoke_data.py --out data/smoke_ml.csv
echo "[ec2-mt-test] Starting run_batch.py --data-dir data ..."
T0=$(date +%s)
python3 run_batch.py --data-dir data
EXIT_CODE=$?
T1=$(date +%s)
WALL=$((T1 - T0))
echo "[ec2-mt-test] run_batch.py finished (exit=${EXIT_CODE}) in ${WALL}s"
printf 'run_batch_exit_code=%s\nrun_batch_wall_seconds=%s\nfinished_at=%s\n' \
    "${EXIT_CODE}" "${WALL}" "$(date -Iseconds)" > data/timing.txt
echo "[ec2-mt-test] Wrote data/timing.txt"
S3_DEST="s3://${S3_RESULTS_BUCKET}/${S3_RESULTS_PREFIX}/"
echo "[ec2-mt-test] Uploading data/ -> ${S3_DEST}"
aws s3 cp data/ "${S3_DEST}" --recursive --region "${AWS_REGION}"
echo "[ec2-mt-test] Upload complete."
exit "${EXIT_CODE}"
ENTRYPOINT_EOF
RUN chmod +x /usr/local/bin/entrypoint.sh

# Fortify "Dockerfile Default User Privilege" remediation.
# Create a dedicated non-root user that owns the workspace and the entrypoint.
# The Helm Job spec will additionally force runAsNonRoot at the pod
# securityContext, so this pod never runs as root regardless.
RUN groupadd --system app \
    && useradd --system --gid app --home /workspace --shell /sbin/nologin app \
    && chown -R app:app /workspace /usr/local/bin/entrypoint.sh
USER app

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
