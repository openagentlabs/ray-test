#!/usr/bin/env bash
# Download the Amazon RDS global CA bundle and start psql with TLS verify-full:
# TCP to RDS_IP while the server certificate is checked against RDS_NAME (libpq
# host + hostaddr - works on older clients; avoids sslhost which needs libpq 15+).
#
# Read-only against AWS except downloading the public CA PEM from AWS PKI.
#
# Prerequisites: curl, psql (libpq), Layer-3 path to host:5432 from this machine,
# and credentials (set PGPASSWORD or use ~/.pgpass - see psql docs).
#
# Usage (from repo root):
#   export PGPASSWORD='your-db-password'
#   ./deploy/scripts/util/rds-psql-ssl-verify-full.sh
#
#   RDS_NAME=mydb.xxx.us-east-1.rds.amazonaws.com RDS_IP=10.0.1.2 \
#     RDS_DB=postgres RDS_USER=myuser ./deploy/scripts/util/rds-psql-ssl-verify-full.sh
#
# Env (defaults match a typical MIDAS dev endpoint; override per environment):
#   RDS_NAME   - RDS endpoint hostname (TLS name / SNI; must match server cert)
#   RDS_IP     - TCP hostaddr (often primary private IP); optional if DNS resolves
#   RDS_PORT   - default 5432
#   RDS_DB     - default postgres
#   RDS_USER   - default midaspostgres
#   MIDAS_RDS_SSLROOTCERT - path for the downloaded CA bundle (default: TMPDIR)

set -euo pipefail

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<'EOF'
Download the Amazon RDS global CA bundle and run psql with sslmode=verify-full
(TCP to RDS_IP via hostaddr; certificate hostname checked against RDS_NAME).

Usage:
  export PGPASSWORD='...'
  ./deploy/scripts/util/rds-psql-ssl-verify-full.sh

Environment (all optional; sensible MIDAS dev defaults for RDS_*):
  RDS_NAME, RDS_IP, RDS_PORT, RDS_DB, RDS_USER
  MIDAS_RDS_SSLROOTCERT - path for the CA PEM (default: $TMPDIR/midas-rds-global-bundle.pem)
  PGGSSENCMODE - set to disable by this script before psql
  PGCONNECT_TIMEOUT - optional libpq connect timeout (seconds), e.g. 10

Requires: curl, psql, network to RDS_IP:5432, DB credentials.
  RDS_IP is usually a private RFC1918 address: run from a VPC-reachable host
  (SSM jump box, VPN, pod), not a random corporate laptop without that path.
EOF
  exit 0
fi

RDS_NAME="${RDS_NAME:-midas.cuzwqoeau6l8.us-east-1.rds.amazonaws.com}"
RDS_IP="${RDS_IP:-10.72.134.166}"
RDS_PORT="${RDS_PORT:-5432}"
RDS_DB="${RDS_DB:-postgres}"
RDS_USER="${RDS_USER:-midaspostgres}"

CERT_URL="https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem"
_tmpdir="${TMPDIR:-/tmp}"
_tmpdir="${_tmpdir%/}"
CERT_FILE="${MIDAS_RDS_SSLROOTCERT:-${_tmpdir}/midas-rds-global-bundle.pem}"

if ! command -v curl >/dev/null 2>&1; then
  echo "ERROR: curl is not installed or not on PATH." >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "ERROR: psql (PostgreSQL client) is not installed or not on PATH." >&2
  exit 1
fi

mkdir -p "$(dirname "${CERT_FILE}")"
curl -fsSLo "${CERT_FILE}" "${CERT_URL}"
chmod a+r "${CERT_FILE}" 2>/dev/null || true

if [[ -z "${PGPASSWORD:-}" && ! -t 0 ]]; then
  echo "WARNING: PGPASSWORD is unset and stdin is not a TTY; psql may fail without ~/.pgpass." >&2
fi

echo "RDS TLS verify-full psql"
echo "  hostaddr (TCP): ${RDS_IP}:${RDS_PORT}"
echo "  host (TLS name): ${RDS_NAME}"
echo "  db/user: ${RDS_DB} / ${RDS_USER}"
echo "  sslrootcert: ${CERT_FILE}"
echo ""
echo "If connect fails with \"Operation timed out\", this machine has no route to ${RDS_IP} (private RDS). Run the same script from the VPC (e.g. SSM test instance) or another approved path - see deploy/README.md §8."
echo ""

export PGGSSENCMODE=disable
if [[ -n "${PGCONNECT_TIMEOUT:-}" ]]; then
  export PGCONNECT_TIMEOUT
fi

# host + hostaddr: connect to IP but verify cert/SNI for RDS_NAME (libpq < 15 has no sslhost).
# gssencmode=disable avoids GSSAPI negotiation when Kerberos is irrelevant.
exec psql \
  "host=${RDS_NAME} hostaddr=${RDS_IP} port=${RDS_PORT} dbname=${RDS_DB} user=${RDS_USER} \
   sslmode=verify-full sslrootcert=${CERT_FILE} \
   gssencmode=disable"
