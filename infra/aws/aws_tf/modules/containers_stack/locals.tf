locals {
  _ecr_prefix_raw = lower(replace("${var.solution.name}-${var.solution.deployment_key}", "_", "-"))
  ecr_prefix      = can(regex("--", var.solution.deployment_key)) ? local._ecr_prefix_raw : replace(replace(replace(local._ecr_prefix_raw, "--", "-"), "--", "-"), "--", "-")

  workload_catalog = {
    frontend = {
      ecr_suffix              = "frontend"
      k8s_service_name        = "frontend"
      service_account_name    = "frontend"
      container_name          = "frontend"
      container_port          = 8802
      console_image_component = "frontend"
      cpu                     = "512m"
      memory                  = "1024Mi"
      expose_load_balancer    = false
      task_role_arn           = null
      environment = {
        PORT            = "8802"
        HOSTNAME        = "0.0.0.0"
        AUTH_TRUST_HOST = "true"
      }
    }
    manager_web = {
      ecr_suffix              = "manager-web"
      k8s_service_name        = "manager-web"
      service_account_name    = "manager-web"
      container_name          = "manager-web"
      container_port          = 8811
      console_image_component = "manager-web"
      cpu                     = "512m"
      memory                  = "1024Mi"
      expose_load_balancer    = true
      shared_mounts_enabled   = true
      schedule_on_ray_nodes   = true
      task_role_arn           = null
      environment = {
        PORT                   = "8811"
        HOSTNAME               = "0.0.0.0"
        MOUNT_WATCHDOG_ENABLED = "true"
      }
    }
    iam_svc = {
      ecr_suffix              = "iam-svc"
      k8s_service_name        = "iam"
      service_account_name    = "iam"
      container_name          = "iam"
      container_port          = 8803
      console_image_component = "iam-service"
      cpu                     = "256m"
      memory                  = "512Mi"
      expose_load_balancer    = false
      task_role_arn           = null
      environment             = {}
    }
    general_ai_agent = {
      ecr_suffix              = "general-ai-agent-svc"
      k8s_service_name        = "general-ai-agent"
      service_account_name    = "general-ai-agent"
      container_name          = "general-ai-agent"
      container_port          = 8806
      console_image_component = "general-ai-agent-service"
      cpu                     = "512m"
      memory                  = "1024Mi"
      expose_load_balancer    = false
      task_role_arn           = var.bedrock_task_role_arn
      environment             = {}
    }
    solutions_svc = {
      ecr_suffix              = "solutions-svc"
      k8s_service_name        = "solutions"
      service_account_name    = "solutions"
      container_name          = "solutions"
      container_port          = 8804
      console_image_component = "solutions-service"
      cpu                     = "256m"
      memory                  = "512Mi"
      expose_load_balancer    = false
      task_role_arn           = null
      environment             = {}
    }
    notification_svc = {
      ecr_suffix              = "notification-svc"
      k8s_service_name        = "notification"
      service_account_name    = "notification"
      container_name          = "notification"
      container_port          = 8807
      console_image_component = "notification-service"
      cpu                     = "256m"
      memory                  = "512Mi"
      expose_load_balancer    = false
      task_role_arn           = null
      environment             = {}
    }
    storage_svc = {
      ecr_suffix              = "storage-svc"
      k8s_service_name        = "storage"
      service_account_name    = "storage"
      container_name          = "storage"
      container_port          = 8805
      console_image_component = "storage-service"
      cpu                     = "256m"
      memory                  = "512Mi"
      expose_load_balancer    = false
      task_role_arn           = null
      environment = {
        STORAGE_DATABASE_PATH = "/tmp/storage.db"
      }
    }
    collaboration_svc = {
      ecr_suffix              = "collaboration-svc"
      k8s_service_name        = "collaboration"
      service_account_name    = "collaboration"
      container_name          = "collaboration"
      container_port          = 8808
      console_image_component = "collaboration-service"
      cpu                     = "256m"
      memory                  = "512Mi"
      expose_load_balancer    = false
      task_role_arn           = null
      environment             = {}
    }
    document_storage_svc = {
      ecr_suffix              = "document-storage-svc"
      k8s_service_name        = "document-storage"
      service_account_name    = "document-storage"
      container_name          = "document-storage"
      container_port          = 8809
      console_image_component = "document-storage-service"
      cpu                     = "256m"
      memory                  = "512Mi"
      expose_load_balancer    = false
      task_role_arn           = var.document_storage_task_role_arn != "" ? var.document_storage_task_role_arn : null
      environment             = {}
    }
    arch_diagram_agent_svc = {
      ecr_suffix              = "arch-diagram-agent-svc"
      k8s_service_name        = "arch-diagram-agent"
      service_account_name    = "arch-diagram-agent"
      container_name          = "arch-diagram-agent"
      container_port          = 8810
      console_image_component = "arch-diagram-agent-service"
      cpu                     = "512m"
      memory                  = "1024Mi"
      expose_load_balancer    = false
      task_role_arn           = var.arch_diagram_agent_bedrock_task_role_arn
      environment             = {}
    }
  }

  enabled_workloads = {
    for key, cfg in local.workload_catalog :
    key => cfg
    if try(var.workloads[key].enabled, true)
  }

  irsa_service_account_names = [
    for key, cfg in local.enabled_workloads :
    cfg.service_account_name
  ]

  workload_image_tags = {
    for key, _ in local.enabled_workloads :
    key => coalesce(try(var.workloads[key].image_tag, null), var.image_tag)
  }
}
