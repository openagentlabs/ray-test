#!/usr/bin/env bash
# Smoke-test the local routing stack (expects compose already up).
# Usage:
#   ./infra/docker/test-local.sh
#   ./infra/docker/test-local.sh --sub alice@example.com
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-pod-manager-local}"
COMPOSE_FILE="${ROOT}/infra/docker/docker-compose.local.yml"

ENVOY_URL="${ENVOY_URL:-http://localhost:10000}"
ENVOY_HEALTH_URL="${ENVOY_HEALTH_URL:-http://localhost:8080}"
POD_MANAGER_HOST="${POD_MANAGER_HOST:-localhost}"
POD_MANAGER_PORT="${POD_MANAGER_PORT:-8804}"
PREFIX="${POD_MANAGER_POSTGRES_TABLE_PREFIX:-pm_}"
SCHEMA="${POD_MANAGER_POSTGRES_SCHEMA_NAME:-pod_manager}"
PGUSER="${POSTGRES_USER:-postgres}"
PGDB="${POSTGRES_DB:-midas}"
TEST_SUB="${TEST_SUB:-test-local-$(date +%s)@example.com}"

psql_q() {
  docker compose -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" exec -T postgres \
    psql -tA -U "$PGUSER" -d "$PGDB" -c "$1" 2>/dev/null || true
}

PASS=0
FAIL=0
SKIP=0

usage() {
  cat <<EOF
Usage: $0 [--sub EMAIL]

Runs HTTP + gRPC smoke tests against the local stack started by start-local.sh.

Environment:
  ENVOY_URL, POD_MANAGER_HOST, POD_MANAGER_PORT, COMPOSE_PROJECT, TEST_SUB
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --sub) TEST_SUB="$2"; shift 2 ;;
    -h | --help) usage; exit 0 ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

ok() {
  echo "  OK: $*"
  PASS=$((PASS + 1))
}

bad() {
  echo "  FAIL: $*" >&2
  FAIL=$((FAIL + 1))
}

skip() {
  echo "  SKIP: $*"
  SKIP=$((SKIP + 1))
}

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    bad "required command not found: $cmd"
    return 1
  fi
  return 0
}

wait_for_port() {
  local port="$1"
  local label="$2"
  local attempts="${3:-30}"
  local i
  for i in $(seq 1 "$attempts"); do
    if bash -c "echo >/dev/tcp/127.0.0.1/${port}" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  bad "timed out waiting for ${label} on port ${port}"
  return 1
}

http_code() {
  curl -s -o /dev/null -w '%{http_code}' "$@" 2>/dev/null || echo "000"
}

http_body() {
  curl -s "$@" 2>/dev/null || true
}

compose_ps_running() {
  local service="$1"
  local id
  id="$(docker compose -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" ps -q "$service" 2>/dev/null || true)"
  [[ -n "$id" ]] && docker inspect -f '{{.State.Running}}' "$id" 2>/dev/null | grep -qx true
}

grpc_claim() {
  local sub="$1"
  cd "$ROOT/pod_manager_cli"
  uv run pod-manager claim --sub "$sub" >/dev/null
}

grpc_release() {
  local sub="$1"
  cd "$ROOT/pod_manager_cli"
  uv run pod-manager release --sub "$sub" >/dev/null
}

echo "==> Local stack smoke tests (sub=${TEST_SUB})"
echo ""

require_cmd curl || exit 1
require_cmd docker || exit 1

echo "==> Ports and compose services"
for port in 5432 8804 10000 8080 18080 18081 18082; do
  if wait_for_port "$port" "port ${port}" 5; then
    ok "port ${port} open"
  fi
done

for svc in postgres router envoy backend-pool-node-0 backend-pool-node-1 login-pod; do
  if compose_ps_running "$svc"; then
    ok "compose service ${svc} running"
  else
    bad "compose service ${svc} not running (project ${COMPOSE_PROJECT})"
  fi
done

echo ""
echo "==> Postgres tables and seed"
BACKEND_TABLE="${SCHEMA}.${PREFIX}backend_pool"
LOGIN_TABLE="${SCHEMA}.${PREFIX}login_pod_pool"
for table in "$BACKEND_TABLE" "$LOGIN_TABLE" "${SCHEMA}.${PREFIX}user_assignments"; do
  exists="$(psql_q "SELECT to_regclass('${table}') IS NOT NULL;")"
  if [[ "$exists" == "t" ]]; then
    ok "table ${table} exists"
  else
    bad "table ${table} missing (run start-local.sh -r -s -d)"
  fi
done

backend_ids="$(psql_q "SELECT string_agg(pod_id, ' ' ORDER BY pod_id) FROM ${BACKEND_TABLE};")"
if [[ "$backend_ids" == *"no-pod-available"* ]] || [[ "$backend_ids" == *"no_pod"* ]]; then
  bad "stale overflow pod in ${BACKEND_TABLE}; restart with: ./infra/docker/start-local.sh -r -s -d"
elif [[ "$backend_ids" == *"backend-pool-node-0"* ]] && [[ "$backend_ids" == *"backend-pool-node-1"* ]]; then
  ok "backend pool seeded (${backend_ids})"
else
  bad "unexpected backend pool pods: ${backend_ids:-<empty>}"
fi

login_ids="$(psql_q "SELECT string_agg(pod_id, ' ' ORDER BY pod_id) FROM ${LOGIN_TABLE};")"
if [[ "$login_ids" == *"login-pod"* ]]; then
  ok "login pod pool seeded (${login_ids})"
else
  bad "login pod pool missing login-pod entry: ${login_ids:-<empty>}"
fi

echo ""
echo "==> Direct pod health"
if [[ "$(http_code http://localhost:18080/healthz)" == "200" ]]; then
  ok "backend-pool-node-0 /healthz"
else
  bad "backend-pool-node-0 /healthz"
fi
if [[ "$(http_code http://localhost:18082/healthz)" == "200" ]]; then
  ok "login-pod /healthz"
else
  bad "login-pod /healthz"
fi
if [[ "$(http_code "${ENVOY_HEALTH_URL}/healthz")" == "200" ]]; then
  ok "Envoy health listener ${ENVOY_HEALTH_URL}/healthz"
else
  bad "Envoy health listener (got $(http_code "${ENVOY_HEALTH_URL}/healthz"))"
fi

echo ""
echo "==> Routing (login pool vs backend lease)"
unleased_code="$(http_code -H "x-test-sub: ${TEST_SUB}" "${ENVOY_URL}/api/v1/me")"
unleased_body="$(http_body -H "x-test-sub: ${TEST_SUB}" "${ENVOY_URL}/api/v1/me")"
if [[ "$unleased_code" == "403" ]] && [[ "$unleased_body" == *"no_backend_lease"* ]]; then
  ok "unleased GET /api/v1/me → 403 no_backend_lease"
else
  bad "unleased GET /api/v1/me expected 403 no_backend_lease (got HTTP ${unleased_code})"
fi

login_direct_code="$(http_code -X POST "http://localhost:18082/login" \
  -H 'Content-Type: application/json' \
  -d "{\"user_name\":\"${TEST_SUB}\",\"user_password\":\"\"}")"
if [[ "$login_direct_code" == "200" ]]; then
  ok "POST /login on login-pod:18082 → 200"
else
  bad "POST /login on login-pod (got HTTP ${login_direct_code})"
fi

# Envoy ext_authz requires identity (cookie or dev x-test-sub) before routing.
login_envoy_code="$(http_code -X POST "${ENVOY_URL}/login" \
  -H 'Content-Type: application/json' \
  -H "x-test-sub: ${TEST_SUB}" \
  -d "{\"user_name\":\"${TEST_SUB}\",\"user_password\":\"\"}")"
if [[ "$login_envoy_code" == "200" ]]; then
  ok "POST /login via Envoy (dev x-test-sub) → 200"
else
  bad "POST /login via Envoy with x-test-sub (got HTTP ${login_envoy_code})"
fi

if ! command -v uv >/dev/null 2>&1 || [[ ! -d "$ROOT/pod_manager_cli" ]]; then
  skip "gRPC lease tests (uv or pod_manager_cli missing)"
else
  echo ""
  echo "==> gRPC acquire / route / release"
  if grpc_claim "$TEST_SUB"; then
    ok "AcquireLease ${TEST_SUB}"
  else
    bad "AcquireLease ${TEST_SUB}"
  fi

  leased_code="$(http_code -H "x-test-sub: ${TEST_SUB}" "${ENVOY_URL}/api/v1/me")"
  leased_body="$(http_body -H "x-test-sub: ${TEST_SUB}" "${ENVOY_URL}/api/v1/me")"
  if [[ "$leased_code" == "200" ]] && [[ "$leased_body" == *"backend_pool_node"* ]]; then
    ok "leased GET /api/v1/me → 200 JSON"
  else
    bad "leased GET /api/v1/me (HTTP ${leased_code})"
  fi

  root_body="$(http_body -H "x-test-sub: ${TEST_SUB}" "${ENVOY_URL}/")"
  if [[ "$root_body" == *"BACKEND_POOL_NODE_NAME"* ]]; then
    ok "leased GET / → backend HTML"
  else
    bad "leased GET / did not reach backend pool node"
  fi

  if cd "$ROOT/pod_manager_cli" && uv run pod-manager e2e --sub "$TEST_SUB" --repeats 2 >/dev/null; then
    ok "pod-manager e2e sticky routing (releases lease)"
  else
    bad "pod-manager e2e --sub ${TEST_SUB}"
    grpc_release "$TEST_SUB" 2>/dev/null || true
  fi

  after_code="$(http_code -H "x-test-sub: ${TEST_SUB}" "${ENVOY_URL}/api/v1/me")"
  if [[ "$after_code" == "403" ]]; then
    ok "after release GET /api/v1/me → 403"
  else
    bad "after release expected 403 (got HTTP ${after_code})"
  fi
fi

echo ""
echo "==> Summary: ${PASS} passed, ${FAIL} failed, ${SKIP} skipped"
if [[ "$FAIL" -gt 0 ]]; then
  echo "Hint: fresh stack: ./infra/docker/start-local.sh -r -s -d && $0" >&2
  exit 1
fi
echo "All smoke tests passed."

if command -v uv >/dev/null 2>&1 && [[ -d "$ROOT/dev_testing" ]]; then
  echo ""
  echo "==> dev_testing (optional unified runner)"
  (cd "$ROOT/dev_testing" && uv run dev-test all --target local --sub "$TEST_SUB") || true
fi
