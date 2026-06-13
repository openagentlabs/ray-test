# ADR 0004 — pod_manager shares the backend Postgres (replaces DynamoDB)

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-06-08 |
| Author | MIDAS Platform Team |
| Affects layers | Data, Platform/Infra, Orchestration |

---

## Context

The `pod_manager` routing tier (`pod_manager/router.svc`) originally persisted its
control-plane state (backend/login pools, user→pod assignments, assignment events,
solution documents, service config) in **DynamoDB**, using conditional
`TransactWriteItems` for atomic, exclusive pod-lease acquisition.

The `backend` analytics service uses **Postgres** (RDS, in the MIDAS VPC
`vpc-0c4d673f3e95a93eb`). Operationally we want one database technology and one
managed instance instead of two. The request was to replace `pod_manager`'s
DynamoDB usage with the backend's existing Postgres by adding `pod_manager`-owned
tables.

## Decision

1. `pod_manager` persists all routing state in the **same Postgres database** the
   backend uses, but in its **own dedicated schema** (`pod_manager`, configurable
   via `schema_name`) so it is namespace-isolated from the backend's `public`
   schema and never touches backend-owned tables (e.g. `message_states`). Tables
   keep the `pm_` prefix: `pm_backend_pool`, `pm_login_pod_pool`,
   `pm_user_assignments`, `pm_assignment_events`, `pm_solution_documents`,
   `pm_service_config`. The connection pool pins `search_path` to this schema, so
   application SQL stays unqualified while resolving only into `pod_manager`.
2. DynamoDB GSIs become plain B-tree indexes (`state`, `pod_id`, `solution_id`).
3. The DynamoDB conditional `TransactWriteItems` lease is replaced by a single
   Postgres transaction: insert the assignment (`ON CONFLICT DO NOTHING`) and a
   guarded `UPDATE ... WHERE pod_id = $p AND state = 'free'`; a unique-violation
   or a 0-row update maps to `ErrorCodes.CONFLICT`, preserving the exclusive-lease
   contract `PoolRpcHandler` already expects.
4. The driver uses `asyncpg` with a shared connection pool (`PostgresContext`),
   keeping the service fully async. The schema and its tables are bootstrapped at
   startup with `CREATE SCHEMA IF NOT EXISTS` + `CREATE TABLE IF NOT EXISTS`,
   matching the backend's style. This requires the DB role to hold `CREATE` on the
   database (to create the schema on first run) or for the schema to be
   pre-provisioned.
5. Connectivity: deploy `pod_manager` into the MIDAS VPC and reach the shared RDS
   over a `DATABASE_URL` secret. A dedicated DB user with privileges scoped to the
   `pod_manager` schema is recommended.

## Consequences

### Trade-off (this ADR intentionally reverses a prior principle)

This couples `pod_manager` and `backend` onto one database instance, contrary to
`architecture.mdc`'s "each data store has one owning service" and the original
service-independence design. Their failure domains and deploy lifecycles are now
linked: a Postgres incident affects both services, and connection-pool sizing must
account for both workloads. We mitigate blast radius via a dedicated `pod_manager`
schema (plus `pm_` table prefix) and a least-privilege DB user scoped to that
schema, but the coupling is real and accepted per the explicit request.

### Positive

- One database technology and one managed instance to operate, back up, and patch.
- Strong relational guarantees and a single transactional lease (no cross-table
  eventual-consistency reasoning); standard SQL indexes replace GSIs.
- Removes the DynamoDB Terraform module, IAM data-plane policy, and `aioboto3`
  dependency from the routing tier.

### Negative / follow-ups

- Shared failure domain and pool contention (above).
- `pod_manager` must run where it can reach the RDS endpoint (MIDAS VPC). Stop
  creating a separate VPC for it (`create_vpc = false`) and open the RDS security
  group to the routing-tier security group on 5432.
- A dedicated, least-privilege DB role scoped to the `pod_manager` schema should be
  provisioned (not yet automated here). The role needs `CREATE` on the database for
  first-run schema creation, or the `pod_manager` schema must be pre-created and the
  role granted `USAGE`/`CREATE` on it.
