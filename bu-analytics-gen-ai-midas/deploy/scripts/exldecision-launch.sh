#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# exldecision-launch.sh
#
# Bootstraps the EXLdecision companion app on a MacBook.
#
#   1. Verifies macOS (Darwin).
#   2. Verifies git, node (>= 20), npm.
#   3. Wipes /tmp/exldecision-atlas if present, then git clones this repo there.
#   4. Runs `npm install` + `npm run dev` inside <tmp>/atlas/.
#   5. Captures the http://localhost:<port> URL that Next.js prints and
#      opens it in the default browser.
#   6. Foregrounds the dev server so Ctrl-C stops it cleanly.
#
# Usage:
#   bash exldecision-launch.sh                # standard run
#   bash exldecision-launch.sh --help         # show this help
#
# Typical invocation (from the repo README):
#   bash <(curl -fsSL https://ucgithub.exlservice.com/Unified-Cloud-DevOps/bu-analytics-gen-ai-midas/raw/branch/main/deploy/scripts/exldecision-launch.sh)
# -----------------------------------------------------------------------------

set -euo pipefail

REPO_URL="https://ucgithub.exlservice.com/Unified-Cloud-DevOps/bu-analytics-gen-ai-midas.git"
TMP_ROOT="/tmp/exldecision-atlas"
ATLAS_DIR="${TMP_ROOT}/atlas"
DEV_LOG="${TMP_ROOT}/.atlas-dev.log"
INSTALL_LOG="${TMP_ROOT}/.atlas-install.log"
NODE_MIN_MAJOR=20

DEV_PID=""

# ---- pretty output ----------------------------------------------------------
if [[ -t 1 ]]; then
  C_RED=$'\033[31m'; C_GRN=$'\033[32m'; C_YEL=$'\033[33m'
  C_BLU=$'\033[34m'; C_BLD=$'\033[1m';  C_RST=$'\033[0m'
else
  C_RED=""; C_GRN=""; C_YEL=""; C_BLU=""; C_BLD=""; C_RST=""
fi
say()  { printf "%s%s%s\n" "${C_BLU}" "▶ $*" "${C_RST}"; }
ok()   { printf "%s%s%s\n" "${C_GRN}" "✓ $*" "${C_RST}"; }
warn() { printf "%s%s%s\n" "${C_YEL}" "! $*" "${C_RST}"; }
die()  { printf "%s%s%s\n" "${C_RED}" "✗ $*" "${C_RST}" >&2; exit 1; }

show_help() {
  sed -n '2,22p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

[[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && show_help

cleanup() {
  local code=$?
  if [[ -n "${DEV_PID}" ]] && kill -0 "${DEV_PID}" 2>/dev/null; then
    say "Stopping companion app (pid ${DEV_PID})..."
    kill "${DEV_PID}" 2>/dev/null || true
    wait "${DEV_PID}" 2>/dev/null || true
  fi
  exit "${code}"
}
trap cleanup EXIT INT TERM

# ---- 1. macOS check ---------------------------------------------------------
say "Checking platform..."
host_os="$(uname -s)"
if [[ "${host_os}" != "Darwin" ]]; then
  die "EXLdecision launcher requires a MacBook (macOS). Detected: ${host_os}.
   Please run this on a macOS laptop. The companion app is a developer-only
   tool and is intentionally not packaged for Linux or Windows."
fi
ok "macOS detected ($(sw_vers -productVersion 2>/dev/null || echo 'unknown'))"

# ---- 2. tooling check -------------------------------------------------------
say "Checking required tools..."
missing=()
command -v git  >/dev/null 2>&1 || missing+=("git (install via Xcode CLT: xcode-select --install)")
command -v node >/dev/null 2>&1 || missing+=("node >= ${NODE_MIN_MAJOR} (install via 'brew install node' or nvm)")
command -v npm  >/dev/null 2>&1 || missing+=("npm (ships with node)")

if (( ${#missing[@]} > 0 )); then
  printf "%sMissing required tools:%s\n" "${C_RED}" "${C_RST}" >&2
  for m in "${missing[@]}"; do printf "  - %s\n" "${m}" >&2; done
  die "Install the tools above and re-run."
fi

node_major="$(node -p 'process.versions.node.split(".")[0]')"
if (( node_major < NODE_MIN_MAJOR )); then
  die "node ${node_major}.x detected; ${NODE_MIN_MAJOR}.x or newer required.
   Try:  brew upgrade node   (or use nvm to install Node ${NODE_MIN_MAJOR})."
fi
ok "git $(git --version | awk '{print $3}'), node $(node -v), npm $(npm -v)"

# ---- 3. clone ---------------------------------------------------------------
if [[ -e "${TMP_ROOT}" ]]; then
  warn "Removing existing ${TMP_ROOT}"
  rm -rf "${TMP_ROOT}"
fi
mkdir -p "${TMP_ROOT}"

say "Cloning ${REPO_URL} → ${TMP_ROOT}"
if ! git clone --depth 1 "${REPO_URL}" "${TMP_ROOT}"; then
  die "git clone failed. Are you on the EXL VPN / network that can reach ucgithub.exlservice.com?"
fi
ok "Repository cloned"

[[ -d "${ATLAS_DIR}" ]] || die "Expected companion app at ${ATLAS_DIR} but it is missing."

# ---- 4. install -------------------------------------------------------------
say "Installing companion app dependencies (logged to ${INSTALL_LOG})..."
( cd "${ATLAS_DIR}" && npm install --no-audit --no-fund ) >"${INSTALL_LOG}" 2>&1 \
  || die "npm install failed. See ${INSTALL_LOG}"
ok "Dependencies installed"

# ---- 5. dev server + capture URL --------------------------------------------
: > "${DEV_LOG}"
say "Starting Next.js dev server (logged to ${DEV_LOG})..."
( cd "${ATLAS_DIR}" && npm run dev ) >"${DEV_LOG}" 2>&1 &
DEV_PID=$!

URL=""
# Wait up to ~60s for the dev server to print its local URL.
for _ in $(seq 1 60); do
  if ! kill -0 "${DEV_PID}" 2>/dev/null; then
    printf "%sDev server exited prematurely. Last 40 lines of log:%s\n" "${C_RED}" "${C_RST}" >&2
    tail -n 40 "${DEV_LOG}" >&2 || true
    die "Companion app failed to start."
  fi
  # Next.js prints lines like:  - Local:        http://localhost:3000
  if URL=$(grep -Eo 'https?://(localhost|127\.0\.0\.1)(:[0-9]+)?(/[^[:space:]]*)?' "${DEV_LOG}" | head -n 1) \
     && [[ -n "${URL}" ]]; then
    break
  fi
  sleep 1
done

if [[ -z "${URL}" ]]; then
  warn "Could not detect the dev server URL within 60s; defaulting to http://localhost:3000"
  URL="http://localhost:3000"
fi

ok "Companion app is up at ${C_BLD}${URL}${C_RST}"
say "Opening ${URL} in your default browser..."
open "${URL}" || warn "Could not auto-open the browser; please visit ${URL} manually."

printf "\n%sCompanion app is running. Press Ctrl-C in this terminal to stop it.%s\n\n" \
  "${C_BLD}" "${C_RST}"

# Foreground: keep streaming dev-server output so the user sees compile errors live.
tail -n +1 -f "${DEV_LOG}" &
TAIL_PID=$!
wait "${DEV_PID}"
kill "${TAIL_PID}" 2>/dev/null || true
