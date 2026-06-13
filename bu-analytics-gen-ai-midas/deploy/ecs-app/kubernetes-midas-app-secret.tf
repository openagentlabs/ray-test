# -----------------------------------------------------------------------------
# Sync midas-{environment}-us-east-1/app (Secrets Manager) → Kubernetes Secret
# midas-app-secret in midas-apps, gated by terraform_sync_app_secret_to_kubernetes.
# Enables RDS wiring env keys without relying on helm-deploy-releases.sh for that hop.
#
# Namespace midas-apps is NOT managed here (Helm / kubectl create it first).
# If midas-app-secret already exists in the cluster (Helm), import before apply (pass
# the same -var-file / -var as terraform plan — required vars e.g. aws_account_id):
#   terraform import -var-file=... -var 'aws_account_id=...' ... 'kubernetes_secret_v1.midas_app[0]' midas-apps/midas-app-secret
# Jenkins runs kubectl + conditional import after terraform init (see Jenkinsfile_Deploy_App).
#
# Encoding note (hashicorp/kubernetes provider ~2.27–2.38):
#   kubernetes_secret_v1 .data accepts PLAIN STRINGS. The provider maps .data to the
#   Kubernetes API stringData field internally — Kubernetes handles base64 encoding
#   before writing to etcd. Pods receive plain strings via envFrom.
#
#   DO NOT call base64encode() on values passed to .data — the provider + K8s already
#   encode once, so manual base64encode() produces double-encoded blobs in pods (the
#   AccessDeniedException / "YXJu..." ARN symptom seen in production incidents).
#
#   .binary_data is the correct field when values are already base64-encoded.
#   We only use .data here with raw plain strings from SM.
# -----------------------------------------------------------------------------

locals {
  midas_app_sm_raw_secret_string = var.terraform_sync_app_secret_to_kubernetes ? data.aws_secretsmanager_secret_version.app_current[0].secret_string : "{}"
  midas_app_sm_decoded           = try(jsondecode(local.midas_app_sm_raw_secret_string), {})
  # Coerce all values to plain strings (SM JSON values may be strings or numbers).
  # Passed directly to .data — no base64encode() needed or wanted.
  midas_app_k8s_string_data = {
    for k, v in local.midas_app_sm_decoded :
    k => try(tostring(v), jsonencode(v))
  }
}

data "aws_secretsmanager_secret_version" "app_current" {
  count     = var.terraform_sync_app_secret_to_kubernetes ? 1 : 0
  secret_id = module.secretsmanager.app_secret_id

  # Static depends_on only. When secretsmanager_app_secret_seed_from_rds is false, app_seed
  # has count 0; referencing aws_secretsmanager_secret_version.app_seed is still valid and
  # creates an implicit dependency on the resource type (no-op when count is 0).
  depends_on = [
    module.secretsmanager,
    aws_secretsmanager_secret_version.app_seed,
  ]
}

resource "kubernetes_secret_v1" "midas_app" {
  count = var.terraform_sync_app_secret_to_kubernetes ? 1 : 0

  metadata {
    name      = "midas-app-secret"
    namespace = "midas-apps"
  }

  type = "Opaque"

  # Plain strings from SM JSON — provider maps .data → K8s stringData (K8s encodes once).
  # DO NOT wrap in base64encode() — that causes double-encoding and broken pod env vars.
  data = local.midas_app_k8s_string_data

  lifecycle {
    # Guard 1: AWS_RDS_POSTGRES_SECRET_ID must be a plain ARN.
    # If SM contains base64(ARN) instead of the ARN, Terraform would write base64(ARN) into K8s
    # .data — the provider then base64-encodes it again — so pods receive base64(base64(ARN))
    # as the env var value, causing GetSecretValue to fail with AccessDeniedException.
    # This has occurred multiple times; this guard fails the apply before damage is done.
    # Fix: run populate-secrets.sh or manually aws secretsmanager put-secret-value with the plain ARN.
    precondition {
      condition = (
        !contains(keys(local.midas_app_k8s_string_data), "AWS_RDS_POSTGRES_SECRET_ID") ||
        startswith(
          try(local.midas_app_k8s_string_data["AWS_RDS_POSTGRES_SECRET_ID"], ""),
          "arn:"
        )
      )
      error_message = "AWS_RDS_POSTGRES_SECRET_ID in SM app secret does not start with 'arn:' — it may be base64-encoded. Correct the SM value (run populate-secrets.sh or aws secretsmanager put-secret-value) so it holds the plain ARN, then re-run terraform apply."
    }

    # Guard 2: Region keys must look like AWS region identifiers (e.g. us-east-1), not base64 blobs.
    # A base64-encoded region string would start with a capital letter and contain no hyphens.
    # This catches double-encoding of AWS_REGION / AWS_DEFAULT_REGION / AWS_SECRETS_MANAGER_REGION.
    precondition {
      condition = (
        !contains(keys(local.midas_app_k8s_string_data), "AWS_REGION") ||
        can(regex("^[a-z]{2}-[a-z]+-[0-9]$", try(local.midas_app_k8s_string_data["AWS_REGION"], "")))
      )
      error_message = "AWS_REGION in SM app secret does not match a valid AWS region pattern (e.g. us-east-1) — it may be base64-encoded. Correct the SM value and re-run terraform apply."
    }

    # Guard 3: AWS_SECRETS_MANAGER_VERIFY_SSL must be literally 'true' or 'false', not a base64 blob.
    precondition {
      condition = (
        !contains(keys(local.midas_app_k8s_string_data), "AWS_SECRETS_MANAGER_VERIFY_SSL") ||
        contains(["true", "false"], try(local.midas_app_k8s_string_data["AWS_SECRETS_MANAGER_VERIFY_SSL"], "true"))
      )
      error_message = "AWS_SECRETS_MANAGER_VERIFY_SSL in SM app secret is not 'true' or 'false' — it may be base64-encoded. Correct the SM value and re-run terraform apply."
    }

    # Guard 4: GRAPHRAG_API_KEY must be present and non-empty.
    # midas-graph-svc raises RuntimeError("GraphRAG setup verification failed") at startup
    # when GRAPHRAG_API_KEY is missing or empty. Fail the apply early with a clear message
    # rather than deploying a secret that will put the graph pod into CrashLoopBackOff.
    # To set the key: ./deploy/scripts/ci/set-graphrag-api-key.sh [ENVIRONMENT]
    precondition {
      condition = (
        !contains(keys(local.midas_app_k8s_string_data), "GRAPHRAG_API_KEY") ||
        length(try(local.midas_app_k8s_string_data["GRAPHRAG_API_KEY"], "")) > 0
      )
      error_message = "GRAPHRAG_API_KEY in SM app secret is empty. Set it with: ./deploy/scripts/ci/set-graphrag-api-key.sh [ENVIRONMENT], then re-run terraform apply."
    }
  }

  depends_on = [
    data.aws_secretsmanager_secret_version.app_current,
  ]
}
