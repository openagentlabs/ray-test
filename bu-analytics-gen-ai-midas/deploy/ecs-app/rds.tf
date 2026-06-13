# -----------------------------------------------------------------------------
# PostgreSQL RDS (module: ./modules/rds).
# Same registration pattern as deploy/ecs-app/s3.tf and deploy/ecs-app/eks.tf.
# VPC and subnets match EKS: vpc_id = eks_vpc_id; subnets = effective EKS node subnets.
#
# RDS master credentials: modules/rds sets manage_master_user_password = true so AWS
# creates and maintains a dedicated Secrets Manager secret (JSON). Terraform exposes
# db_master_user_secret_arn; deploy/ecs-app/eks-node-secretsmanager-read.tf grants the
# EKS node role GetSecretValue on that ARN for in-cluster pods.
# -----------------------------------------------------------------------------

locals {
  eks_node_subnet_ids_effective = var.eks_node_subnet_ids != null ? var.eks_node_subnet_ids : var.eks_cluster_subnet_ids
  # Pin RDS/Redis subnet groups independently of EKS worker subnets. Defaults to the
  # effective EKS node subnets to preserve legacy behaviour (uat/prod), but dev pins
  # these to the data-tier subnets where the live DB/cache ENIs already exist so EKS
  # workers can move to a different subnet pair without triggering SubnetInUse /
  # InvalidParameterValue subnet-group update errors.
  rds_subnet_ids_effective         = var.rds_subnet_ids != null ? var.rds_subnet_ids : local.eks_node_subnet_ids_effective
  elasticache_subnet_ids_effective = var.elasticache_subnet_ids != null ? var.elasticache_subnet_ids : local.eks_node_subnet_ids_effective
}

module "rds_postgres" {
  count  = var.rds_postgres_enabled ? 1 : 0
  source = "./modules/rds"

  aws_account_id = var.aws_account_id
  environment    = var.environment
  aws_region     = var.aws_region

  vpc_id              = var.eks_vpc_id
  db_subnet_ids       = local.rds_subnet_ids_effective
  instance_class      = var.rds_postgres_instance_class
  engine_version      = var.rds_postgres_engine_version
  skip_final_snapshot = var.rds_postgres_skip_final_snapshot
  deletion_protection = var.rds_postgres_deletion_protection

  eks_cluster_security_group_id = module.eks.eks_cluster_security_group_id

  additional_ingress_cidrs_all_traffic          = var.rds_additional_ingress_cidrs_all_traffic
  additional_ingress_cidrs_tcp_5432             = var.rds_additional_ingress_cidrs_tcp_5432
  additional_source_security_group_ids_tcp_5432 = var.rds_additional_source_security_group_ids_tcp_5432
}

output "rds_postgres_endpoint" {
  description = "PostgreSQL hostname (empty if rds_postgres_enabled is false)."
  value       = var.rds_postgres_enabled ? module.rds_postgres[0].db_instance_endpoint : null
}

output "rds_postgres_port" {
  description = "PostgreSQL port."
  value       = var.rds_postgres_enabled ? module.rds_postgres[0].db_instance_port : null
}

output "rds_postgres_db_name" {
  description = "Database name."
  value       = var.rds_postgres_enabled ? module.rds_postgres[0].db_name : null
}

output "rds_postgres_master_user_secret_arn" {
  description = "Secrets Manager ARN for the RDS master password (managed by RDS)."
  value       = var.rds_postgres_enabled ? module.rds_postgres[0].db_master_user_secret_arn : null
}

output "rds_postgres_security_group_id" {
  description = "RDS security group ID (for additional app-specific rules if needed)."
  value       = var.rds_postgres_enabled ? module.rds_postgres[0].db_security_group_id : null
}
