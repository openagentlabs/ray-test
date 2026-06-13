terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.19.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.13"
    }
    # kubernetes_annotations patches the cloudwatch-agent ServiceAccount with
    # the IRSA eks.amazonaws.com/role-arn annotation. The chart's
    # cloudwatch-agent-serviceaccount.yaml template ONLY sets name + namespace
    # (no annotations key), so we cannot inject IRSA via helm_release.set.
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.27"
    }
    # null_resource forces a daemonset rollout-restart after the SA is
    # annotated, so existing agent pods (created without IRSA) are recreated
    # with the projected token + AWS_ROLE_ARN env injected by the EKS
    # pod-identity webhook.
    null = {
      source  = "hashicorp/null"
      version = ">= 3.2"
    }
  }
}
