# Terraform helpers for pod_manager infrastructure.
# Usage: make -C infra/terraform plan-dev

TF_ENV ?= dev
ENV_DIR := environments/$(TF_ENV)

.PHONY: init plan apply validate fmt output validate-all plan-dev apply-dev

init:
	terraform -chdir=$(ENV_DIR) init -upgrade

validate:
	terraform -chdir=$(ENV_DIR) validate

validate-all: init validate
	helm lint ../helm/routing-tier

fmt:
	terraform -chdir=modules fmt -recursive
	terraform -chdir=$(ENV_DIR) fmt -recursive

plan: validate
	terraform -chdir=$(ENV_DIR) plan

apply:
	terraform -chdir=$(ENV_DIR) apply

deploy-images:
	../scripts/build-push-images.sh

deploy-helm:
	../scripts/deploy-helm.sh

output:
	terraform -chdir=$(ENV_DIR) output db_table_prefix
	terraform -chdir=$(ENV_DIR) output pod_manager_irsa_role_arn

plan-dev: TF_ENV=dev
plan-dev: plan

apply-dev: TF_ENV=dev
apply-dev: apply
