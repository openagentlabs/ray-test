# DEPRECATED — use per-service Dockerfiles (e.g. iam.svc/server/Dockerfile).
# Prefer: make build-dockers
#
# Legacy shared image (build from repository root):
#   docker build -f infra/containers/images/python-grpc-service/Dockerfile \
#     --build-arg SERVICE_DIR=iam.svc/server ...

ARG SERVICE_DIR
ARG CONSOLE_SCRIPT
ARG APP_CONFIG_ENV
ARG EXPOSE_PORT

FROM python:3.12-slim-bookworm AS builder

ARG SERVICE_DIR
ARG CONSOLE_SCRIPT

WORKDIR /build
COPY ${SERVICE_DIR}/pyproject.toml ${SERVICE_DIR}/README.md ./
COPY ${SERVICE_DIR}/src ./src
RUN pip install --no-cache-dir --upgrade pip \
  && pip install --no-cache-dir .

FROM python:3.12-slim-bookworm

ARG SERVICE_DIR
ARG CONSOLE_SCRIPT
ARG APP_CONFIG_ENV
ARG EXPOSE_PORT

ENV PYTHONUNBUFFERED=1 \
  CONSOLE_SCRIPT=${CONSOLE_SCRIPT} \
  LISTEN_PORT=${EXPOSE_PORT} \
  ${APP_CONFIG_ENV}=/app/app_config.toml

WORKDIR /app
COPY --from=builder /usr/local /usr/local
COPY ${SERVICE_DIR}/app_config.toml ./app_config.toml

EXPOSE ${EXPOSE_PORT}

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,socket; p=int(os.environ['LISTEN_PORT']); s=socket.socket(); s.settimeout(2); s.connect(('127.0.0.1', p)); s.close()"

CMD ["/bin/sh", "-c", "exec $CONSOLE_SCRIPT"]
