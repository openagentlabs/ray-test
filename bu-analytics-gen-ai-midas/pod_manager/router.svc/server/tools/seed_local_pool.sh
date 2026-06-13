#!/usr/bin/env bash
# Seed free pool nodes for local testing when Kubernetes reconciliation is disabled.
# Bootstraps the pm_* schema (idempotent) and inserts pool rows directly into Postgres,
# so it can run before router.svc starts. Uses psql inside the compose `postgres` service.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
COMPOSE_FILE="${ROOT}/infra/docker/docker-compose.local.yml"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-pod-manager-local}"
PREFIX="${POD_MANAGER_POSTGRES_TABLE_PREFIX:-pm_}"
SCHEMA="${POD_MANAGER_POSTGRES_SCHEMA_NAME:-pod_manager}"
PGUSER="${POSTGRES_USER:-postgres}"
PGDB="${POSTGRES_DB:-midas}"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

psql_exec() {
  docker compose -f "$COMPOSE_FILE" -p "$COMPOSE_PROJECT" exec -T postgres \
    psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDB" "$@"
}

psql_exec <<SQL
CREATE SCHEMA IF NOT EXISTS ${SCHEMA};
SET search_path TO ${SCHEMA};
CREATE TABLE IF NOT EXISTS ${PREFIX}backend_pool (
  pod_id TEXT PRIMARY KEY, pod_dns TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'free',
  assigned_sub TEXT NOT NULL DEFAULT '', assignment_epoch BIGINT NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ${PREFIX}login_pod_pool (
  pod_id TEXT PRIMARY KEY, pod_dns TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'free',
  assigned_sub TEXT NOT NULL DEFAULT '', assignment_epoch BIGINT NOT NULL DEFAULT 0,
  updated_at TEXT NOT NULL
);

INSERT INTO ${PREFIX}backend_pool (pod_id, pod_dns, state, updated_at)
VALUES ('backend-pool-node-0', 'backend-pool-node-0:8080', 'free', '${NOW}'),
       ('backend-pool-node-1', 'backend-pool-node-1:8080', 'free', '${NOW}')
ON CONFLICT (pod_id) DO UPDATE SET pod_dns = EXCLUDED.pod_dns, state = 'free',
  assigned_sub = '', assignment_epoch = 0, updated_at = EXCLUDED.updated_at;

INSERT INTO ${PREFIX}login_pod_pool (pod_id, pod_dns, state, updated_at)
VALUES ('login-pod', 'login-pod:8080', 'available', '${NOW}')
ON CONFLICT (pod_id) DO UPDATE SET pod_dns = EXCLUDED.pod_dns, state = 'available',
  updated_at = EXCLUDED.updated_at;
SQL

echo "Seeded ${SCHEMA}.${PREFIX}backend_pool and ${SCHEMA}.${PREFIX}login_pod_pool"
