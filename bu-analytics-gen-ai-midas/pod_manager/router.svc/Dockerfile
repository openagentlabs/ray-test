# router.svc — gRPC control plane (solutions-service)
#
# Build (from this directory):
#   docker build -t router-svc:local .
#
# Run (requires a reachable Postgres; pass its DSN via DATABASE_URL):
#   docker run --rm -p 8804:8804 \
#     -e DATABASE_URL=postgresql://postgres:postgres@host.docker.internal:5432/midas \
#     -e POD_MANAGER_KUBERNETES_ENABLED=false \
#     -e POD_MANAGER_RECONCILIATION_ENABLED=false \
#     router-svc:local
#
# Smoke test (grpcurl):
#   grpcurl -plaintext localhost:8804 list pod_manager.v1.PodManagerService

FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install locked runtime dependencies (layer cache when only src changes).
COPY server/pyproject.toml server/uv.lock server/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY server/src ./src
RUN uv sync --frozen --no-dev --no-editable

# ---------------------------------------------------------------------------
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    SOLUTIONS_APP_CONFIG_PATH=/app/app_config.toml

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY server/app_config.toml /app/app_config.toml

EXPOSE 8804 9000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import socket; [socket.create_connection(('127.0.0.1', p), 2).close() for p in (8804, 9000)]"

CMD ["solutions-service"]
