#!/bin/bash
# Environment protection script for UAT/PROD deploys.

set -e

ACTION=${1:-"deploy"}
ENVIRONMENT=${ENVIRONMENT:-"dev"}

if [ "$ENVIRONMENT" = "dev" ]; then
  echo "Dev environment - no protection needed"
  exit 0
fi

BUILD_USER="${BUILD_USER_ID:-unknown}"

if [ "$BUILD_USER" = "unknown" ]; then
  echo "ERROR: Unable to determine build user"
  exit 1
fi

APPROVERS_FILE="resources/approvers/${ENVIRONMENT}.txt"

if [ ! -f "$APPROVERS_FILE" ]; then
  echo "ERROR: Approvers file not found: $APPROVERS_FILE"
  exit 1
fi

if grep -q "^${BUILD_USER}$" "$APPROVERS_FILE"; then
  echo "Authorized: ${BUILD_USER} can ${ACTION} to ${ENVIRONMENT}"
  exit 0
fi

echo "ERROR: ${BUILD_USER} is not authorized for ${ENVIRONMENT} ${ACTION}"
echo "Authorized users:"
awk 'NF && $1 !~ /^#/' "$APPROVERS_FILE"
exit 1
