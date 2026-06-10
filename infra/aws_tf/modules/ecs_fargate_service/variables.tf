variable "assign_public_ip" {
  description = "Assign a public IP to Fargate tasks (required for default VPC public subnets without NAT)."
  type        = bool
  default     = true
  nullable    = false
}

variable "cluster_arn" {
  description = "ECS cluster ARN."
  type        = string
  nullable    = false
}

variable "container_environment" {
  description = "Plain environment variables for the container."
  type        = map(string)
  default     = {}
  nullable    = false
}

variable "container_image" {
  description = "Full container image URI (ECR URL with tag)."
  type        = string
  nullable    = false
}

variable "container_name" {
  description = "Container name in the task definition."
  type        = string
  nullable    = false
}

variable "container_port" {
  description = "Container port exposed for service discovery / load balancing."
  type        = number
  nullable    = false
}

variable "cpu" {
  description = "Fargate task CPU units."
  type        = number
  default     = 256
  nullable    = false
}

variable "desired_count" {
  description = "Desired task count."
  type        = number
  default     = 1
  nullable    = false
}

variable "enable_public_alb" {
  description = "When true, create an internet-facing ALB and register this service as a target."
  type        = bool
  default     = false
  nullable    = false
}

variable "execution_role_arn" {
  description = "ECS task execution role ARN."
  type        = string
  nullable    = false
}

variable "memory" {
  description = "Fargate task memory (MiB)."
  type        = number
  default     = 512
  nullable    = false
}

variable "service_discovery_namespace_id" {
  description = "Cloud Map namespace id for private DNS registration."
  type        = string
  nullable    = false
}

variable "service_discovery_namespace_name" {
  description = "Cloud Map private DNS namespace name (e.g. arb-ai-assistant.local)."
  type        = string
  nullable    = false
}

variable "service_discovery_name" {
  description = "DNS label registered in Cloud Map (e.g. iam, frontend)."
  type        = string
  nullable    = false
}

variable "service_name" {
  description = "ECS service name."
  type        = string
  nullable    = false
}

variable "solution" {
  description = "Solution-wide metadata propagated from the root module."
  type = object({
    name        = string
    description = string
    version     = string
    date        = string
    account_id  = string
    region      = string
  })
  nullable = false
}

variable "subnet_ids" {
  description = "Subnet ids for awsvpc networking."
  type        = list(string)
  nullable    = false
}

variable "task_role_arn" {
  description = "Optional IAM role assumed by the application container."
  type        = string
  default     = null
  nullable    = true
}

variable "task_security_group_id" {
  description = "Security group for the task ENI."
  type        = string
  nullable    = false
}

variable "workload_key" {
  description = "Stable workload key for tags."
  type        = string
  nullable    = false
}
