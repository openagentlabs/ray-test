# Loaded by deploy/Jenkinsfile_Deploy_App (Terraform plan) for MIDAS.
# All-protocol ingress on RDS PostgreSQL and ElastiCache Redis security groups (see modules rds / elasticache).
# TCP 5432 from workload VPC CIDR - in-VPC VMs/pods; Jenkins uses this file for dev/uat/prod: adjust if a tenant VPC CIDR differs.

rds_additional_ingress_cidrs_all_traffic = ["10.54.74.117/32", "10.54.67.114/32"]

rds_additional_ingress_cidrs_tcp_5432 = ["10.72.134.0/23"]

elasticache_additional_ingress_cidrs_all_traffic = ["10.54.74.117/32", "10.54.67.114/32"]
