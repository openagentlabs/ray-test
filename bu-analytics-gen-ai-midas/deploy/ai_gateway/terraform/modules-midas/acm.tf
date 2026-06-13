# Legacy cert — still attached to midas-aigtw-c1-api-alb-dev and midas-dev-alb listeners.
# Keep in state with prevent_destroy so Terraform does not attempt deletion while in-use.
# Remove this block once ALB listeners have been migrated to the per-service certs below.
resource "aws_acm_certificate" "exlerate-c1-api-cert" {
  domain_name       = "midas-aigtw-control-api-dev.exlservice.com"
  validation_method = "DNS"

  lifecycle {
    prevent_destroy = true
    ignore_changes  = all
  }
}

# ---------------------------------------------------------------------------
# One-shot renewal trigger.
# The three per-service certs below timed out on DNS validation and entered
# FAILED/VALIDATION_TIMED_OUT state. ACM does not allow re-validation of a
# FAILED cert — a new certificate resource must be created.
#
# Mechanism: replace_triggered_by = [terraform_data.cert_renewal] causes
# Terraform to taint and replace each cert on the apply that first sees
# input = "1". create_before_destroy ensures the new cert is created before
# the FAILED one is destroyed so ConfigMap references never point at a void.
#
# After all three certs reach ISSUED and the Helm pipelines are green,
# reset input to "0" and commit — future applies will be no-ops.
# ---------------------------------------------------------------------------
resource "terraform_data" "cert_renewal" {
  input = "1"
}

# LiteLLM — certificate for exldecision-ai-dev-aigw-litellm.exlservice.com
resource "aws_acm_certificate" "litellm_cert" {
  domain_name       = "exldecision-ai-dev-aigw-litellm.exlservice.com"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
    replace_triggered_by  = [terraform_data.cert_renewal]
  }
}

# Langfuse — certificate for exldecision-ai-dev-aigw-langfuse.exlservice.com
resource "aws_acm_certificate" "langfuse_cert" {
  domain_name       = "exldecision-ai-dev-aigw-langfuse.exlservice.com"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
    replace_triggered_by  = [terraform_data.cert_renewal]
  }
}

# Control-API — certificate for exldecision-ai-dev-aigw-c1.exlservice.com
resource "aws_acm_certificate" "c1_api_cert" {
  domain_name       = "exldecision-ai-dev-aigw-c1.exlservice.com"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
    replace_triggered_by  = [terraform_data.cert_renewal]
  }
}

# ---------------------------------------------------------------------------
# Validation gates — Terraform blocks the apply here until ACM confirms each
# cert is ISSUED. The core infrastructure team adds the DNS CNAME records
# output in the phase-5 handoff table. No validation_record_fqdns needed
# because DNS is managed externally (corporate DNS, not Route 53 in this account).
# ---------------------------------------------------------------------------
resource "aws_acm_certificate_validation" "litellm_cert" {
  certificate_arn = aws_acm_certificate.litellm_cert.arn
}

resource "aws_acm_certificate_validation" "langfuse_cert" {
  certificate_arn = aws_acm_certificate.langfuse_cert.arn
}

resource "aws_acm_certificate_validation" "c1_api_cert" {
  certificate_arn = aws_acm_certificate.c1_api_cert.arn
}
