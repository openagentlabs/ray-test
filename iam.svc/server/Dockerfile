# IAM gRPC microservice — build from repository root:
#   docker build -f iam.svc/server/Dockerfile -t arb-iam-service:local .

FROM python:3.12-slim-bookworm AS builder

WORKDIR /build
COPY iam.svc/server/pyproject.toml iam.svc/server/README.md ./
COPY iam.svc/server/src ./src
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir .

FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
  CONSOLE_SCRIPT=iam-service \
  LISTEN_PORT=8803 \
  IAM_APP_CONFIG_PATH=/app/app_config.toml

WORKDIR /app
COPY --from=builder /usr/local /usr/local
COPY iam.svc/server/app_config.toml ./app_config.toml

EXPOSE 8803

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,socket; p=int(os.environ['LISTEN_PORT']); s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', p)); s.close()"

CMD ["/bin/sh", "-c", "exec $CONSOLE_SCRIPT"]
