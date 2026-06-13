#!/usr/bin/env bash
# Local routing-tier stack helper (Postgres → seed → compose).
# Run from anywhere; resolves repo root from this script's location.
#
# Usage:
#   ./infra/docker/start-local.sh -s          # start (foreground logs)
#   ./infra/docker/start-local.sh -s -d       # start detached
#   ./infra/docker/start-local.sh -r          # stop/remove, then start fresh
#   ./infra/docker/start-local.sh -r -d       # restart detached
#   ./infra/docker/start-local.sh -s -d -t    # start detached, then run smoke tests
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${ROOT}/infra/docker/docker-compose.local.yml"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-pod-manager-local}"
# Older runs used the default project name "docker" when compose was invoked from infra/docker.
LEGACY_COMPOSE_PROJECT="${LEGACY_COMPOSE_PROJECT:-docker}"
DETACH=false
RESTART=false
START=false
RUN_TESTS=false

usage() {
  cat <<EOF
Usage: $0 -s|--start [-d|--detach] [-t|--test]
       $0 -r|--restart [-d|--detach] [-t|--test]

  -s  Start stack: Postgres → seed → docker compose up --build
  -r  Tear down this stack (and legacy project), then start fresh
  -d  Run compose in detached mode (with -s or -r)
  -t  After detached start, run infra/docker/test-local.sh

Examples:
  $0 -s
  $0 -s -d
  $0 -r -d
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -s | --start) START=true; shift ;;
    -d | --detach) DETACH=true; shift ;;
    -r | --restart) RESTART=true; START=true; shift ;;
    -t | --test) RUN_TESTS=true; shift ;;
    -h | --help) usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if [[ "$RUN_TESTS" == true && "$DETACH" != true ]]; then
  echo "Error: -t/--test requires -d/--detach (tests run after detached start)." >&2
  exit 1
fi

if [[ "$START" != true ]]; then
  echo "Error: no action specified. Use -s to start or -r to restart." >&2
  echo "" >&2
  usage >&2
  exit 1
fi

cd "$ROOT"

for cmd in docker; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Required command not found: $cmd" >&2
    exit 1
  fi
done

compose() {
  docker compose -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" "$@"
}

export POD_MANAGER_APP_SERVICE_NAME="${POD_MANAGER_APP_SERVICE_NAME:-router-svc}"
export COMPOSE_PROJECT

wait_for_port() {
  local port="$1"
  local label="$2"
  local attempts="${3:-60}"
  local i
  for i in $(seq 1 "$attempts"); do
    if bash -c "echo >/dev/tcp/127.0.0.1/${port}" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  echo "Timed out waiting for ${label} on port ${port}" >&2
  return 1
}

wait_for_stack_ready() {
  echo "==> Waiting for router.svc (8804) and Envoy (10000)"
  wait_for_port 8804 "router.svc gRPC" 90
  wait_for_port 10000 "Envoy HTTP" 90

  local envoy_id
  envoy_id="$(compose ps -q envoy 2>/dev/null || true)"
  if [[ -n "$envoy_id" ]]; then
    local i
    for i in $(seq 1 30); do
      if docker inspect -f '{{.State.Running}}' "$envoy_id" 2>/dev/null | grep -qx true; then
        break
      fi
      if docker inspect -f '{{.State.Status}}' "$envoy_id" 2>/dev/null | grep -qx exited; then
        echo "Envoy container exited; logs:" >&2
        compose logs --tail=30 envoy >&2 || true
        return 1
      fi
      sleep 1
    done
  fi

  if command -v curl >/dev/null 2>&1; then
    local code
    code="$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/healthz 2>/dev/null || echo 000)"
    if [[ "$code" != "200" ]]; then
      echo "Warning: Envoy health listener returned HTTP ${code} (expected 200)" >&2
    fi
  fi
}

# Stop other Docker containers publishing host ports this stack needs.
release_compose_ports() {
  local port
  for port in 5432 8804 9000 10000 8080 18080 18081 18082; do
    local name
    while IFS= read -r name; do
      [[ -z "$name" ]] && continue
      local project
      project="$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project" }}' "$name" 2>/dev/null || true)"
      if [[ "$project" == "$COMPOSE_PROJECT" ]]; then
        continue
      fi
      echo "Port ${port} in use by ${name}; stopping container so this stack can bind..."
      docker stop "$name" >/dev/null
    done < <(docker ps --filter "publish=${port}" --format '{{.Names}}')
  done
}

teardown_stack() {
  echo "==> Stopping and removing stack (project: ${COMPOSE_PROJECT})"
  compose down --remove-orphans --timeout 10 2>/dev/null || true

  if [[ "$LEGACY_COMPOSE_PROJECT" != "$COMPOSE_PROJECT" ]]; then
    echo "==> Stopping legacy stack (project: ${LEGACY_COMPOSE_PROJECT})"
    docker compose -f "$COMPOSE_FILE" -p "$LEGACY_COMPOSE_PROJECT" down --remove-orphans --timeout 10 2>/dev/null || true
  fi
}

if [[ "$RESTART" == true ]]; then
  teardown_stack
fi

echo "==> Releasing host ports if another compose project holds them"
release_compose_ports

echo "==> Starting Postgres (${COMPOSE_PROJECT})"
compose up -d postgres
echo "==> Waiting for Postgres to accept connections"
for i in $(seq 1 60); do
  if compose exec -T postgres pg_isready -U postgres -d midas >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

echo "==> Seeding pod pool (bootstraps pm_* schema)"
"${ROOT}/router.svc/server/tools/seed_local_pool.sh"

echo "==> Starting routing stack (project: ${COMPOSE_PROJECT})"
if [[ "$DETACH" == true ]]; then
  compose up --build -d
  wait_for_stack_ready
  echo ""
  echo "Stack is ready (detached)."
  echo "  Envoy (API):     http://localhost:10000"
  echo "  router.svc API: localhost:8804 (POD_MANAGER_PORT=8804)"
  echo "  Postgres:        localhost:5432 (db midas, user postgres)"
  echo ""
  echo "CLI (second terminal):"
  echo "  cd pod_manager_cli && export POD_MANAGER_HOST=localhost POD_MANAGER_PORT=8804 ENVOY_URL=http://localhost:10000"
  echo "  uv run pod-manager pool && uv run pod-manager e2e --sub alice@example.com"
  echo ""
  echo "  Smoke tests: ./infra/docker/test-local.sh"
  echo "  Logs: docker compose -f infra/docker/docker-compose.local.yml -p ${COMPOSE_PROJECT} logs -f"
  if [[ "$RUN_TESTS" == true ]]; then
    echo ""
    "${ROOT}/infra/docker/test-local.sh"
  fi
else
  compose up --build
fi
