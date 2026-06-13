resource "kubernetes_config_map" "shared_mount_health" {
  count = local.shared_mount_health_enabled ? 1 : 0

  provider = kubernetes.eks

  metadata {
    name      = "${local.cluster_release_name}-shared-mount-health"
    namespace = var.namespace
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
      "app.kubernetes.io/name"       = "ray-shared-mount-health"
      solution                       = var.solution.name
    }
  }

  data = {
    "probe-mounts.sh" = <<-EOT
      #!/bin/sh
      set -eu

      MAX_ATTEMPTS="$${PROBE_MAX_ATTEMPTS:-5}"
      BASE_DELAY_MS=400
      MOUNT_PATHS="$${MOUNT_PATHS:-}"

      probe_one() {
        path="$1"
        attempt=1
        while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
          if [ -d "$path" ] && ls "$path" >/dev/null 2>&1; then
            probe_file="$${path}/.mount-health-probe"
            if touch "$probe_file" 2>/dev/null; then
              rm -f "$probe_file"
              return 0
            fi
            # Mountpoint S3 may reject root writes; listable directory is sufficient.
            return 0
          fi
          attempt=$((attempt + 1))
          sleep "$(awk -v attempt="$attempt" -v base="$BASE_DELAY_MS" 'BEGIN {printf "%.3f", attempt * base / 1000}')"
        done
        echo "mount probe failed: $path" >&2
        return 1
      }

      OLDIFS="$IFS"
      IFS=','
      for path in $MOUNT_PATHS; do
        if [ -n "$path" ]; then
          probe_one "$path" || exit 1
        fi
      done
      IFS="$OLDIFS"
      exit 0
    EOT

    "wait-for-mounts.sh" = <<-EOT
      #!/bin/sh
      set -eu

      MAX_WAIT_SEC="$${MAX_WAIT_SEC:-600}"
      INTERVAL=10
      elapsed=0

      while [ "$elapsed" -lt "$MAX_WAIT_SEC" ]; do
        if /scripts/probe-mounts.sh; then
          echo "shared mounts ready"
          exit 0
        fi
        sleep "$INTERVAL"
        elapsed=$((elapsed + INTERVAL))
      done

      echo "shared mounts not ready after $${MAX_WAIT_SEC}s" >&2
      exit 1
    EOT

    "watchdog.sh" = <<-EOT
      #!/bin/sh
      set -eu

      INTERVAL="$${WATCHDOG_INTERVAL_SEC:-30}"

      while true; do
        if /scripts/probe-mounts.sh; then
          sleep "$INTERVAL"
          continue
        fi

        echo "shared mount unhealthy; restarting Ray pod" >&2
        kill -TERM 1 || true
        exit 1
      done
    EOT
  }
}
