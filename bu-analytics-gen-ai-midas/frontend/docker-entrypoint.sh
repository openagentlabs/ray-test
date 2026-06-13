#!/bin/sh
set -eu

# Runtime-configurable backend upstream for nginx proxy.
# Docker Compose default resolves service name "backend".
# In Kubernetes/EKS set BACKEND_UPSTREAM to your backend service URL.
: "${BACKEND_UPSTREAM:=http://backend:8000}"

envsubst '${BACKEND_UPSTREAM}' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf
exec nginx -g 'daemon off;'
