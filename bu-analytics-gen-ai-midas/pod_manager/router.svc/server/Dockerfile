# Build from router.svc/ (canonical — used by docker-compose):
#   docker build -t router-svc:local -f ../Dockerfile ..
#
# Or from this directory (same image):
#   docker build -t router-svc:local .

FROM python:3.12-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.7 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    SOLUTIONS_APP_CONFIG_PATH=/app/app_config.toml

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY app_config.toml /app/app_config.toml

EXPOSE 8804 9000

HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD python -c "import socket; [socket.create_connection(('127.0.0.1', p), 2).close() for p in (8804, 9000)]"

CMD ["solutions-service"]
