#!/usr/bin/env bash
# TLS + AUTH check against Amazon ElastiCache for Redis (replication group with
# transit_encryption_enabled). Runs one non-interactive PING (or pass-through args).
#
# With REDIS_IP set: TCP targets the private IP while --sni sends the endpoint hostname
# for certificate verification (redis-cli 6.2+).
#
# Read-only except downloading the public CA PEM (same RDS global bundle AWS commonly
# documents for Redis TLS; override with MIDAS_REDIS_CACERT if your org uses another file).
#
# Prerequisites: curl, redis-cli (or valkey-cli) built with OpenSSL/TLS, route to :6379,
# AUTH token when the cluster enforces auth (MIDAS module always sets auth_token).
#
# Usage (repo root):
#   export REDIS_NAME='master.midas-dev-redis.xxxxxx.use1.cache.amazonaws.com'
#   export REDIS_AUTH='your-auth-token'   # or export REDISCLI_AUTH='...'
#   export REDIS_IP='10.x.x.x'             # optional; primary node IP for TCP target
#   ./deploy/scripts/util/elasticache-redis-cli-tls-ping.sh
#
#   REDIS_CLI=valkey-cli ./deploy/scripts/util/elasticache-redis-cli-tls-ping.sh INFO server

set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Run redis-cli (TLS, CA bundle, optional AUTH) against ElastiCache Redis. Default command: PING.

Usage:
  export REDIS_NAME='master.<replication-group-id>.xxxxxx.use1.cache.amazonaws.com'
  export REDIS_AUTH='...'              # or REDISCLI_AUTH (not printed by redis-cli -a in argv)
  export REDIS_IP='10.x.x.x'           # optional; uses --sni REDIS_NAME for cert name
  ./deploy/scripts/util/elasticache-redis-cli-tls-ping.sh [extra redis-cli args...]

Environment:
  REDIS_NAME     - Primary (or configuration) endpoint hostname (required)
  REDIS_IP       - If set, -h uses this IP and --sni uses REDIS_NAME (needs redis-cli 6.2+)
  REDIS_PORT     - default 6379
  REDIS_AUTH     - sets REDISCLI_AUTH for AUTH over TLS
  REDIS_CLI      - default redis-cli (try valkey-cli if redis-cli has no --tls)
  MIDAS_REDIS_CACERT - PEM path for --cacert (default: download to $TMPDIR)
  REDIS_CA_URL   - default https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem

If connect times out, run from a VPC-reachable host (same idea as RDS util script).

Default command is PING if you pass no extra args. Any args are forwarded to redis-cli
after the TLS options (e.g. .../elasticache-redis-cli-tls-ping.sh INFO server).
EOF
  exit 0
fi

REDIS_CLI="${REDIS_CLI:-redis-cli}"
REDIS_PORT="${REDIS_PORT:-6379}"
REDIS_CA_URL="${REDIS_CA_URL:-https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem}"
_tmpdir="${TMPDIR:-/tmp}"
_tmpdir="${_tmpdir%/}"
CERT_FILE="${MIDAS_REDIS_CACERT:-${_tmpdir}/midas-elasticache-redis-ca-bundle.pem}"

if [[ -z "${REDIS_NAME:-}" ]]; then
  echo "ERROR: Set REDIS_NAME to the ElastiCache primary (or config) endpoint hostname." >&2
  echo "Example: master.midas-dev-redis.abcd1234.use1.cache.amazonaws.com" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is not installed or not on PATH." >&2
  exit 1
fi

if ! command -v "${REDIS_CLI}" >/dev/null 2>&1; then
  echo "ERROR: ${REDIS_CLI} is not installed or not on PATH." >&2
  exit 1
fi

if ! "${REDIS_CLI}" --help 2>&1 | grep -qE '[[:space:]]--tls([[:space:]]|$)'; then
  echo "ERROR: ${REDIS_CLI} has no --tls flag (need OpenSSL/TLS build). On macOS try: brew install redis" >&2
  exit 1
fi

has_sni=false
if "${REDIS_CLI}" --help 2>&1 | grep -qE '[[:space:]]--sni([[:space:]]|$)'; then
  has_sni=true
fi

if [[ -n "${REDIS_AUTH:-}" ]]; then
  export REDISCLI_AUTH="${REDIS_AUTH}"
fi

if [[ -z "${REDISCLI_AUTH:-}" ]]; then
  echo "WARNING: REDIS_AUTH / REDISCLI_AUTH unset; PING may fail with NOAUTH if the cluster requires AUTH." >&2
fi

# Reuse PEM if present; otherwise download to CERT_FILE (default or MIDAS_REDIS_CACERT path).
if [[ ! -s "${CERT_FILE}" ]]; then
  mkdir -p "$(dirname "${CERT_FILE}")"
  curl -fsSLo "${CERT_FILE}" "${REDIS_CA_URL}"
  chmod a+r "${CERT_FILE}" 2>/dev/null || true
fi

REDIS_IP="${REDIS_IP:-}"

echo "ElastiCache Redis TLS check (${REDIS_CLI})"
if [[ -n "${REDIS_IP}" ]]; then
  echo "  TCP (-h): ${REDIS_IP}:${REDIS_PORT}"
  echo "  TLS SNI (--sni): ${REDIS_NAME}"
  if [[ "${has_sni}" != true ]]; then
    echo "ERROR: ${REDIS_CLI} has no --sni; cannot connect by IP with verified TLS. Upgrade redis-cli (6.2+) or omit REDIS_IP and use DNS to ${REDIS_NAME}." >&2
    exit 1
  fi
else
  echo "  TCP/TLS (-h): ${REDIS_NAME}:${REDIS_PORT}"
fi
echo "  --cacert: ${CERT_FILE}"
echo ""
echo "If this times out, there is likely no network path to the cache from this host (private SG/VPC). See deploy/README.md §9.4."
echo ""

if [[ "$#" -eq 0 ]]; then
  set -- PING
fi

if [[ -n "${REDIS_IP}" ]]; then
  exec "${REDIS_CLI}" \
    -h "${REDIS_IP}" -p "${REDIS_PORT}" \
    --tls --sni "${REDIS_NAME}" --cacert "${CERT_FILE}" \
    "$@"
else
  exec "${REDIS_CLI}" \
    -h "${REDIS_NAME}" -p "${REDIS_PORT}" \
    --tls --cacert "${CERT_FILE}" \
    "$@"
fi
