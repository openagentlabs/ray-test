#!/usr/bin/env bash
# Local smoke test: same PyPI download as Jenkins EC2 MT Test wheelhouse stage.
# Wheels land under test/ec2-pip-wheelhouse-local/wheels/ — delete the whole
# test/ec2-pip-wheelhouse-local/ folder when done.
#
# Usage (from repo root):
#   ./test/ec2-pip-wheelhouse-local/run-download.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WHEEL_OUT="${TEST_DIR}/wheels"
REQ="deploy/scripts/ci/requirements-ec2-wheelhouse.txt"

mkdir -p "$WHEEL_OUT"

pypi_index_base() {
  local configured
  configured="$(python3 -m pip config get global.index-url 2>/dev/null || true)"
  if [[ -n "$configured" ]]; then
    printf '%s' "${configured%/}"
    return
  fi
  printf '%s' "https://pypi.org/simple"
}

# PEP 503-ish name: lowercase, runs of [-_.] become a single hyphen
normalize_pypi_name() {
  local raw="${1%%[<>=!~;#]*}"
  raw="${raw// /}"
  raw="$(printf '%s' "$raw" | tr '[:upper:]' '[:lower:]')"
  printf '%s' "$raw" | sed -E 's/[-_.]+/-/g'
}

print_requirement_index_urls() {
  local req_file="$1"
  local base
  base="$(pypi_index_base)"
  echo "[local-test] PyPI simple index base: ${base}/"
  echo "[local-test] Top-level packages — metadata URLs (fetched before each wheel):"
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="${line%%#*}"
    line="${line// /}"
    [[ -z "$line" ]] && continue
    local name
    name="$(normalize_pypi_name "$line")"
    echo "[local-test]   • ${name}"
    echo "[local-test]       index : ${base}/${name}/"
    echo "[local-test]       json  : https://pypi.org/pypi/${name}/json"
  done < "$req_file"
  echo ""
}

# Echo pip -vv lines and highlight HTTP URLs before each fetch/download.
filter_pip_url_log() {
  while IFS= read -r line; do
    printf '%s\n' "$line"
    if [[ "$line" =~ (https://files\.pythonhosted\.org[^[:space:]]+) ]]; then
      echo "[local-test] ↳ wheel file URL: ${BASH_REMATCH[1]}"
    elif [[ "$line" =~ ^[[:space:]]*(GET|HEAD)[[:space:]]+(https://[^[:space:]]+) ]]; then
      echo "[local-test] ↳ HTTP ${BASH_REMATCH[1]} ${BASH_REMATCH[2]}"
    elif [[ "$line" =~ ^[[:space:]]*Downloading[[:space:]].*\ from[[:space:]]+(https://[^[:space:]]+) ]]; then
      echo "[local-test] ↳ downloading from: ${BASH_REMATCH[1]}"
    fi
  done
}

echo "[local-test] Repo root:     $ROOT"
echo "[local-test] Requirements:  $REQ"
echo "[local-test] Wheel output:  $WHEEL_OUT"
echo "[local-test] Python:        $(python3 --version 2>&1) ($(command -v python3))"
echo ""

python3 -m pip install --upgrade pip setuptools wheel

pip_download_with_retry() {
  local attempt max_attempts delay_s
  max_attempts="${PIP_RETRY_ATTEMPTS:-3}"
  delay_s="${PIP_RETRY_DELAY_SECONDS:-10}"
  for attempt in $(seq 1 "$max_attempts"); do
    echo "[local-test] pip download attempt ${attempt}/${max_attempts}: $*"
    echo "[local-test] (pip -vv — URLs printed as [local-test] ↳ lines below)"
    if python3 -m pip download "$@" \
      --retries 10 \
      --timeout 120 \
      --no-cache-dir \
      -vv 2>&1 | filter_pip_url_log; then
      return 0
    fi
    if [[ "$attempt" -lt "$max_attempts" ]]; then
      echo "[local-test] pip download failed; retrying in ${delay_s}s..." >&2
      sleep "$delay_s"
      delay_s=$((delay_s * 2))
    fi
  done
  echo "[local-test] ERROR: pip download failed after ${max_attempts} attempts" >&2
  return 1
}

COMMON_PIP_ARGS=(
  -d "$WHEEL_OUT"
  --python-version 310
  --platform manylinux2014_x86_64
  --platform manylinux_2_17_x86_64
  --platform manylinux_2_28_x86_64
  --implementation cp
  --abi cp310
  --only-binary=:all:
)

print_requirement_index_urls "$REQ"
echo "[local-test] Extra bootstrap packages: pip, setuptools, wheel"
echo "[local-test]   • pip        → $(pypi_index_base)/pip/"
echo "[local-test]   • setuptools → $(pypi_index_base)/setuptools/"
echo "[local-test]   • wheel      → $(pypi_index_base)/wheel/"
echo ""

pip_download_with_retry -r "$REQ" "${COMMON_PIP_ARGS[@]}"
pip_download_with_retry pip setuptools wheel "${COMMON_PIP_ARGS[@]}"

cp "$REQ" "$WHEEL_OUT/requirements-ec2.txt"
echo ""
echo "[local-test] Done. Wheel count: $(find "$WHEEL_OUT" -maxdepth 1 -name '*.whl' | wc -l | tr -d ' ')"
echo "[local-test] To remove: rm -rf test/ec2-pip-wheelhouse-local/wheels"
