locals {
  shared_mount_health_enabled = var.lustre_mount_enabled || var.s3_shared_mount_enabled

  shared_mount_paths = compact([
    var.lustre_mount_enabled ? var.lustre_mount_path : "",
    var.s3_shared_mount_enabled ? var.s3_shared_mount_path : "",
  ])

  shared_mount_paths_csv = join(",", local.shared_mount_paths)

  shared_pvc_volume_mounts = concat(
    var.lustre_mount_enabled ? [
      {
        name      = var.lustre_volume_name
        mountPath = var.lustre_mount_path
      },
    ] : [],
    var.s3_shared_mount_enabled ? [
      {
        name      = var.s3_shared_volume_name
        mountPath = var.s3_shared_mount_path
      },
    ] : [],
  )

  shared_mount_probe_volume_mounts = concat(
    [
      {
        name      = "shared-mount-health-scripts"
        mountPath = "/scripts"
        readOnly  = true
      },
    ],
    local.shared_pvc_volume_mounts,
  )

  shared_mount_health_volume = {
    name = "shared-mount-health-scripts"
    configMap = {
      name        = kubernetes_config_map.shared_mount_health[0].metadata[0].name
      defaultMode = 493 # 0755 — Terraform integers are decimal, not octal
    }
  }

  shared_mount_health_env = [
    {
      name  = "MOUNT_PATHS"
      value = local.shared_mount_paths_csv
    },
    {
      name  = "MAX_WAIT_SEC"
      value = tostring(var.mount_health_wait_seconds)
    },
    {
      name  = "PROBE_MAX_ATTEMPTS"
      value = tostring(var.mount_health_probe_max_attempts)
    },
    {
      name  = "WATCHDOG_INTERVAL_SEC"
      value = tostring(var.mount_health_watchdog_interval_seconds)
    },
  ]

  shared_mount_health_init_container = {
    name         = "shared-mount-wait"
    image        = var.mount_health_image
    command      = ["/bin/sh", "/scripts/wait-for-mounts.sh"]
    env          = local.shared_mount_health_env
    volumeMounts = local.shared_mount_probe_volume_mounts
    resources = {
      limits = {
        cpu    = "100m"
        memory = "64Mi"
      }
      requests = {
        cpu    = "50m"
        memory = "32Mi"
      }
    }
  }

  shared_mount_health_sidecar = {
    name         = "shared-mount-watchdog"
    image        = var.mount_health_image
    command      = ["/bin/sh", "/scripts/watchdog.sh"]
    env          = local.shared_mount_health_env
    volumeMounts = local.shared_mount_probe_volume_mounts
    livenessProbe = {
      exec = {
        command = ["/scripts/probe-mounts.sh"]
      }
      initialDelaySeconds = 60
      periodSeconds       = var.mount_health_watchdog_interval_seconds
      timeoutSeconds      = 10
      failureThreshold    = 3
    }
    readinessProbe = {
      exec = {
        command = ["/scripts/probe-mounts.sh"]
      }
      initialDelaySeconds = 20
      periodSeconds       = 15
      timeoutSeconds      = 10
      failureThreshold    = 2
    }
    resources = {
      limits = {
        cpu    = "100m"
        memory = "64Mi"
      }
      requests = {
        cpu    = "50m"
        memory = "32Mi"
      }
    }
  }

  shared_mount_health_pod_security_context = {
    shareProcessNamespace = true
    fsGroup               = var.mount_pod_fs_group
  }

  shared_mount_container_security_context = {
    runAsUser                = var.mount_pod_run_as_user
    runAsGroup               = var.mount_pod_run_as_group
    allowPrivilegeEscalation = false
  }

  shared_mount_container_env = concat(
    var.lustre_mount_enabled ? [
      {
        name  = "LUSTRE_MOUNT_PATH"
        value = var.lustre_mount_path
      },
      {
        name  = "LUSTRE_VOLUME_NAME"
        value = var.lustre_volume_name
      },
    ] : [],
    var.s3_shared_mount_enabled ? [
      {
        name  = "S3_SHARED_MOUNT_PATH"
        value = var.s3_shared_mount_path
      },
      {
        name  = "S3_SHARED_VOLUME_NAME"
        value = var.s3_shared_volume_name
      },
    ] : [],
  )

  shared_mount_health_pod_overrides_by_mode = {
    enabled = {
      initContainers     = [local.shared_mount_health_init_container]
      sidecarContainers  = [local.shared_mount_health_sidecar]
      podSecurityContext = local.shared_mount_health_pod_security_context
      securityContext    = local.shared_mount_container_security_context
    }
    disabled = {
      initContainers    = []
      sidecarContainers = []
    }
  }

  shared_mount_health_pod_overrides = local.shared_mount_health_pod_overrides_by_mode[
    local.shared_mount_health_enabled ? "enabled" : "disabled"
  ]

  shared_mount_common_overrides_by_mode = {
    enabled  = { containerEnv = local.shared_mount_container_env }
    disabled = { containerEnv = [] }
  }

  shared_mount_common_overrides = local.shared_mount_common_overrides_by_mode[
    local.shared_mount_health_enabled ? "enabled" : "disabled"
  ]
}
