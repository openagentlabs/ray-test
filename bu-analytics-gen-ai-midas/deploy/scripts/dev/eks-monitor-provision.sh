#!/usr/bin/env bash
# Poll AWS until an EKS cluster and its managed node group settle, then summarize EC2
# workers, Auto Scaling activity, and CloudWatch control-plane logs. AWS CLI only.
#
# While waiting, periodically pulls **new** lines from /aws/eks/<cluster>/cluster to spot
# errors vs. benign progress (creates, health checks, etc.).
#
# If the cluster stays in CREATING for many minutes, that is normal (often 10-20+ minutes).
# This script only *observes* AWS; Terraform/Jenkins creates the resources.
#
# Order of what you will see: (1) control plane CREATING→ACTIVE - no EC2 workers yet.
# (2) Node group CREATING→ACTIVE - ASG launches instances. (3) Instances register with the API.
# `kubectl get nodes` only works after (1)-(2) and only if your network can reach the private API.
#
# Typical MIDAS names: cluster midas-eks-dev, node group midas-eks-dev-ng, region us-east-1.
#
# Usage:
#   chmod +x deploy/scripts/eks-monitor-provision.sh
#   ./deploy/scripts/eks-monitor-provision.sh
#   CLUSTER_NAME=midas-eks-uat ./deploy/scripts/eks-monitor-provision.sh
#
# Environment:
#   CLUSTER_NAME           (default: midas-eks-dev)
#   NODE_GROUP_NAME        (default: ${CLUSTER_NAME}-ng)
#   AWS_REGION             (default: us-east-1)
#   POLL_INTERVAL          seconds between polls (default: 30)
#   MAX_WAIT_SECONDS       stop waiting after this (default: 7200)
#   LOG_LOOKBACK_MINUTES   final summary window (default: 15)
#   LOG_TICK_MAX_EVENTS    max events per periodic log sample (default: 80)
#   LOG_LINE_MAX_CHARS     truncate long lines in log output (default: 220)
#
# Requires `jq` for periodic log parsing (brew install jq / apt install jq).

set -uo pipefail

CLUSTER_NAME="${CLUSTER_NAME:-midas-eks-dev}"
NODE_GROUP_NAME="${NODE_GROUP_NAME:-${CLUSTER_NAME}-ng}"
AWS_REGION="${AWS_REGION:-us-east-1}"
POLL_INTERVAL="${POLL_INTERVAL:-30}"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-7200}"
LOG_LOOKBACK_MINUTES="${LOG_LOOKBACK_MINUTES:-15}"
LOG_TICK_MAX_EVENTS="${LOG_TICK_MAX_EVENTS:-80}"
LOG_LINE_MAX_CHARS="${LOG_LINE_MAX_CHARS:-220}"

LOG_GROUP="/aws/eks/${CLUSTER_NAME}/cluster"

RED='\033[0;31m'
GRN='\033[0;32m'
YLW='\033[0;33m'
DIM='\033[0;36m'
NC='\033[0m'

log() { echo -e "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*"; }
log_err() { echo -e "${RED}[ERROR]${NC} $*" >&2; }
log_ok() { echo -e "${GRN}[OK]${NC} $*"; }
log_warn() { echo -e "${YLW}[WARN]${NC} $*"; }

START_TS=$(date +%s)
# Millisecond cursor for incremental CloudWatch reads (only advance on new events).
LOG_CURSOR_MS=$(( START_TS * 1000 - 60000 ))
LOG_TICK_COUNT=0
LOG_GROUP_MISSING_NOTIFIED=0

deadline_reached() {
  local now
  now=$(date +%s)
  (( now > START_TS + MAX_WAIT_SECONDS ))
}

# --- CloudWatch: incremental samples (called every poll_until iteration) ---
log_group_exists() {
  aws logs describe-log-groups \
    --region "${AWS_REGION}" \
    --log-group-name-prefix "/aws/eks/${CLUSTER_NAME}" \
    --query 'logGroups[].logGroupName' --output text 2>/dev/null | tr '\t' '\n' | grep -Fxq "${LOG_GROUP}"
}

truncate_line() {
  local s=$1
  local max=${LOG_LINE_MAX_CHARS}
  if ((${#s} > max)); then
    echo "${s:0:max}…"
  else
    echo "${s}"
  fi
}

classify_log_line() {
  # Prints one of: error | warn | progress | noise
  local line=$1
  # Kubernetes audit JSON (audit.k8s.io) often contains words like "error" in benign fields or false-positive
  # substring matches. Treat as noise unless the API call actually failed.
  if grep -qiE 'audit\.k8s\.io' <<<"${line}"; then
    if grep -qE '"status":"Failure"|"code":(4|5)[0-9]{2}' <<<"${line}"; then
      echo error
      return
    fi
    echo noise
    return
  fi
  # Transient during control plane / webhook startup (not data-plane nodes)
  if grep -qiE 'Failed to make webhook authenticator request' <<<"${line}"; then
    echo warn
    return
  fi
  if grep -qiE 'fatal|panic|unauthorized|access denied|denied|invalidclientrequest|validationerror|failed to| failure | error:' <<<"${line}"; then
    echo error
    return
  fi
  if grep -qiE '\berror\b|\bfail(ed|ure)?\b|exception' <<<"${line}"; then
    echo error
    return
  fi
  if grep -qiE 'warn(ing)?' <<<"${line}"; then
    echo warn
    return
  fi
  if grep -qiE 'success|healthy|ready|registered|created|started|attached|authorized|ok\b|complete' <<<"${line}"; then
    echo progress
    return
  fi
  echo noise
}

log_snapshot_tick() {
  (( LOG_TICK_COUNT++ )) || true
  if ! log_group_exists; then
    if (( LOG_GROUP_MISSING_NOTIFIED < 3 )); then
      log "${DIM}[logs]${NC} log group not present yet: ${LOG_GROUP} (appears after control plane logging is active)"
      ((LOG_GROUP_MISSING_NOTIFIED++)) || true
    fi
    return 0
  fi

  local raw max_ts
  raw=$(mktemp)
  if ! aws logs filter-log-events \
    --region "${AWS_REGION}" \
    --log-group-name "${LOG_GROUP}" \
    --start-time "${LOG_CURSOR_MS}" \
    --limit "${LOG_TICK_MAX_EVENTS}" \
    --output json 2>/dev/null > "${raw}"; then
    log_warn "[logs] filter-log-events failed (permissions?)"
    rm -f "${raw}"
    return 0
  fi

  local n ev_err ev_warn ev_prog
  n=$(jq -r '.events | length' "${raw}" 2>/dev/null || echo "0")
  if [[ "${n}" == "0" ]] || [[ -z "${n}" ]]; then
    rm -f "${raw}"
    return 0
  fi

  max_ts=$(jq -r '[.events[].timestamp] | max' "${raw}")
  if [[ "${max_ts}" =~ ^[0-9]+$ ]] && [[ "${max_ts}" -gt "${LOG_CURSOR_MS}" ]]; then
    LOG_CURSOR_MS=$((max_ts + 1))
  fi

  ev_err=0
  ev_warn=0
  ev_prog=0
  # One CloudWatch event per line via jq -c; then extract .message so multi-line JSON is not split by bash read.
  local ev line
  while IFS= read -r ev; do
    [[ -z "${ev}" ]] && continue
    line=$(jq -r '.message' <<<"${ev}" 2>/dev/null) || line=""
    [[ -z "${line}" ]] && continue
    cls=$(classify_log_line "${line}")
    case "${cls}" in
      error) ((ev_err++)) || true ;;
      warn) ((ev_warn++)) || true ;;
      progress) ((ev_prog++)) || true ;;
    esac
  done < <(jq -c '.events[]?' "${raw}" 2>/dev/null)

  log "${DIM}[logs]${NC} tick #${LOG_TICK_COUNT}: +${n} event(s) in window - ${RED}err~${ev_err}${NC} ${YLW}warn~${ev_warn}${NC} ${GRN}progress~${ev_prog}${NC}"

  local shown=0
  while IFS= read -r ev; do
    [[ -z "${ev}" ]] && continue
    line=$(jq -r '.message' <<<"${ev}" 2>/dev/null) || line=""
    [[ -z "${line}" ]] && continue
    cls=$(classify_log_line "${line}")
    if [[ "${cls}" == "error" ]] && ((shown < 5)); then
      echo -e "  ${RED}ERR${NC} $(truncate_line "${line}")"
      ((shown++)) || true
    fi
  done < <(jq -c '.events[]?' "${raw}" 2>/dev/null)

  shown=0
  while IFS= read -r ev; do
    [[ -z "${ev}" ]] && continue
    line=$(jq -r '.message' <<<"${ev}" 2>/dev/null) || line=""
    [[ -z "${line}" ]] && continue
    cls=$(classify_log_line "${line}")
    if [[ "${cls}" == "warn" ]] && ((shown < 3)); then
      echo -e "  ${YLW}WRN${NC} $(truncate_line "${line}")"
      ((shown++)) || true
    fi
  done < <(jq -c '.events[]?' "${raw}" 2>/dev/null)

  if ((ev_err == 0 && ev_warn == 0 && ev_prog > 0)); then
    while IFS= read -r ev; do
      [[ -z "${ev}" ]] && continue
      line=$(jq -r '.message' <<<"${ev}" 2>/dev/null) || line=""
      [[ -z "${line}" ]] && continue
      cls=$(classify_log_line "${line}")
      if [[ "${cls}" == "progress" ]]; then
        echo -e "  ${GRN}…${NC} $(truncate_line "${line}")"
        break
      fi
    done < <(jq -c '.events[]?' "${raw}" 2>/dev/null)
  fi

  rm -f "${raw}"
}

poll_until() {
  # $1 = human label; rest = command that returns 0 when condition met
  local label=$1
  shift
  log "Waiting: ${label} (logs sampled each ${POLL_INTERVAL}s)"
  while true; do
    if deadline_reached; then
      log_err "Timeout after ${MAX_WAIT_SECONDS}s while: ${label}"
      return 1
    fi
    log_snapshot_tick
    if "$@"; then
      return 0
    fi
    sleep "${POLL_INTERVAL}"
  done
}

cluster_exists() {
  aws eks describe-cluster --region "${AWS_REGION}" --name "${CLUSTER_NAME}" &>/dev/null
}

cluster_status() {
  aws eks describe-cluster --region "${AWS_REGION}" --name "${CLUSTER_NAME}" --query 'cluster.status' --output text 2>/dev/null || echo "MISSING"
}

cluster_is_active() {
  local s ver ep plat elapsed line
  elapsed=$(( $(date +%s) - START_TS ))
  line=$(aws eks describe-cluster --region "${AWS_REGION}" --name "${CLUSTER_NAME}" \
    --query 'cluster.[status,version,endpoint,platformVersion]' --output text 2>/dev/null) || line=""
  if [[ -z "${line}" ]]; then
    s="MISSING"
    ver=""; ep=""; plat=""
  else
    IFS=$'\t' read -r s ver ep plat <<< "${line}"
  fi
  echo "  cluster: status=${s}  k8s=${ver:-n/a}  platform=${plat:-n/a}  (elapsed ${elapsed}s / max ${MAX_WAIT_SECONDS}s)"
  if [[ -n "${ep}" && "${ep}" != "None" ]]; then
    echo "  cluster API endpoint: ${ep}"
  else
    echo "  cluster API endpoint: (not ready yet - normal during CREATING)"
  fi
  if [[ "${s}" == "CREATING" ]] || [[ "${s}" == "UPDATING" ]]; then
    echo "  note: No worker nodes yet - EKS creates the control plane first. Managed nodes launch after status=ACTIVE, then the node group (and EC2) provisions."
  fi
  [[ "${s}" == "ACTIVE" ]]
}

nodegroup_status() {
  aws eks describe-nodegroup \
    --region "${AWS_REGION}" \
    --cluster-name "${CLUSTER_NAME}" \
    --nodegroup-name "${NODE_GROUP_NAME}" \
    --query 'nodegroup.status' --output text 2>/dev/null || echo "MISSING"
}

nodegroup_is_active() {
  local s elapsed ver
  elapsed=$(( $(date +%s) - START_TS ))
  s=$(nodegroup_status)
  ver=$(
    aws eks describe-nodegroup \
      --region "${AWS_REGION}" \
      --cluster-name "${CLUSTER_NAME}" \
      --nodegroup-name "${NODE_GROUP_NAME}" \
      --query 'nodegroup.version' --output text 2>/dev/null || echo "n/a"
  )
  echo "  node group: status=${s}  kubelet=${ver}  (elapsed ${elapsed}s)"
  if [[ "${s}" == "MISSING" ]]; then
    echo "  (node group not visible yet - created after control plane; wait for Terraform/EKS to register it)"
  fi
  [[ "${s}" == "ACTIVE" ]]
}

running_worker_count() {
  aws ec2 describe-instances --region "${AWS_REGION}" \
    --filters \
      "Name=tag:eks:cluster-name,Values=${CLUSTER_NAME}" \
      "Name=instance-state-name,Values=running" \
    --query 'length(Reservations[].Instances[])' --output text 2>/dev/null || echo "0"
}

desired_node_count() {
  aws eks describe-nodegroup \
    --region "${AWS_REGION}" \
    --cluster-name "${CLUSTER_NAME}" \
    --nodegroup-name "${NODE_GROUP_NAME}" \
    --query 'nodegroup.scalingConfig.desiredSize' --output text 2>/dev/null || echo "0"
}

workers_meet_desired() {
  local want got
  want=$(desired_node_count)
  got=$(running_worker_count)
  echo "  desired=${want} running=${got}"
  [[ "${want}" =~ ^[0-9]+$ ]] && [[ "${got}" =~ ^[0-9]+$ ]] && [[ "${want}" -gt 0 ]] && [[ "${got}" -ge "${want}" ]]
}

ec2_nodes_table() {
  aws ec2 describe-instances --region "${AWS_REGION}" \
    --filters \
      "Name=tag:eks:cluster-name,Values=${CLUSTER_NAME}" \
      "Name=instance-state-name,Values=pending,running,stopping,stopped" \
    --query 'Reservations[].Instances[].{Id:InstanceId,State:State.Name,Az:Placement.AvailabilityZone,Type:InstanceType}' \
    --output table 2>/dev/null || true
}

asg_name() {
  aws eks describe-nodegroup \
    --region "${AWS_REGION}" \
    --cluster-name "${CLUSTER_NAME}" \
    --nodegroup-name "${NODE_GROUP_NAME}" \
    --query 'nodegroup.resources.autoScalingGroups[0].name' --output text 2>/dev/null || echo ""
}

scaling_activities() {
  local asg
  asg=$(asg_name)
  if [[ -z "${asg}" || "${asg}" == "None" ]]; then
    log_warn "Could not resolve Auto Scaling group from node group."
    return 0
  fi
  log "Recent Auto Scaling activities for ${asg}:"
  aws autoscaling describe-scaling-activities \
    --region "${AWS_REGION}" \
    --auto-scaling-group-name "${asg}" \
    --max-items 10 \
    --query 'Activities[].{Time:StartTime,Status:StatusCode,Desc:Description}' \
    --output table 2>/dev/null || log_warn "Could not read scaling activities."
}

scan_control_plane_logs_final() {
  log "Final CloudWatch pass: ${LOG_GROUP} (last ${LOG_LOOKBACK_MINUTES} min), full error/warn grep…"
  if ! log_group_exists; then
    log_warn "Log group not found. (Control plane logging may be disabled.)"
    return 0
  fi
  local start_ms raw
  start_ms=$(( $(date +%s) * 1000 - LOG_LOOKBACK_MINUTES * 60 * 1000 ))
  raw=$(mktemp)
  if ! aws logs filter-log-events \
    --region "${AWS_REGION}" \
    --log-group-name "${LOG_GROUP}" \
    --start-time "${start_ms}" \
    --limit 200 \
    --query 'events[].message' --output text 2>/dev/null > "${raw}"; then
    log_warn "filter-log-events failed (check logs:FilterLogEvents on the role)."
    rm -f "${raw}"
    return 0
  fi
  if [[ ! -s "${raw}" ]]; then
    log_ok "No log events in the final lookback window."
    rm -f "${raw}"
    return 0
  fi
  if grep -iE 'error|fail|fatal|exception' "${raw}" | head -60; then
    log_warn "Found error/fail/fatal/exception lines above (review; some audit lines are benign)."
  else
    log_ok "No error/fail/fatal/exception substring matches in final sample."
  fi
  rm -f "${raw}"
}

main() {
  log "EKS monitor - region=${AWS_REGION} cluster=${CLUSTER_NAME} nodeGroup=${NODE_GROUP_NAME} poll=${POLL_INTERVAL}s max_wait=${MAX_WAIT_SECONDS}s"
  if ! command -v jq &>/dev/null; then
    log_err "This script needs \`jq\` installed for periodic log parsing (brew install jq / apt install jq)."
    exit 2
  fi
  if ! aws sts get-caller-identity &>/dev/null; then
    log_err "AWS CLI is not authenticated."
    exit 2
  fi
  log "Caller: $(aws sts get-caller-identity --query Arn --output text)"

  poll_until "cluster resource exists" cluster_exists || exit 1

  local cs
  cs=$(cluster_status)
  if [[ "${cs}" == "FAILED" ]] || [[ "${cs}" == "DELETE_FAILED" ]]; then
    log_err "Cluster is in failure state: ${cs}"
    exit 1
  fi

  poll_until "cluster status ACTIVE" cluster_is_active || exit 1
  local ver
  ver=$(aws eks describe-cluster --region "${AWS_REGION}" --name "${CLUSTER_NAME}" --query 'cluster.version' --output text)
  log_ok "Cluster ACTIVE (version ${ver})."

  poll_until "node group exists and status ACTIVE" nodegroup_is_active || exit 1
  local health
  health=$(aws eks describe-nodegroup \
    --region "${AWS_REGION}" \
    --cluster-name "${CLUSTER_NAME}" \
    --nodegroup-name "${NODE_GROUP_NAME}" \
    --query 'nodegroup.health' --output json 2>/dev/null || echo "{}")
  log "Node group health JSON: ${health}"
  log_ok "Node group ACTIVE."

  poll_until "running EC2 workers >= desired size" workers_meet_desired || {
    log_warn "Workers did not reach desired count in time; showing instances."
  }

  echo ""
  log "EC2 instances (tag eks:cluster-name=${CLUSTER_NAME}):"
  ec2_nodes_table
  echo ""
  scaling_activities
  echo ""
  scan_control_plane_logs_final

  if command -v kubectl >/dev/null 2>&1; then
    log "Optional: kubectl view (needs reachable Kubernetes API; private clusters often fail from a laptop):"
    if aws eks update-kubeconfig --region "${AWS_REGION}" --name "${CLUSTER_NAME}" &>/dev/null; then
      kubectl get nodes -o wide 2>/dev/null && log_ok "Nodes reported Ready by API." || log_warn "kubectl could not reach the API (expected if endpoint is private and you are off-network)."
    fi
    echo ""
  fi

  local final_ng run_cnt
  final_ng=$(nodegroup_status)
  run_cnt=$(running_worker_count)
  if [[ "${final_ng}" == "ACTIVE" ]] && [[ "${run_cnt}" =~ ^[0-9]+$ ]] && [[ "${run_cnt}" -gt 0 ]]; then
    log_ok "RESULT: SUCCESS - cluster ACTIVE, node group ACTIVE, ${run_cnt} running worker(s)."
    exit 0
  fi
  log_err "RESULT: FAILED or INCOMPLETE - node_group=${final_ng} running_workers=${run_cnt}"
  exit 1
}

main "$@"
