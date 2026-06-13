output "alb_arn" {
  description = "ARN of the internal ALB."
  value       = aws_lb.alb.arn
}

output "alb_dns_name" {
  description = "DNS name of the internal ALB (stable; never changes while the ALB exists)."
  value       = aws_lb.alb.dns_name
}

output "nlb_arn" {
  description = "ARN of the internal NLB."
  value       = aws_lb.nlb.arn
}

output "nlb_dns_name" {
  description = "DNS name of the internal NLB (use this for corporate routing; ENI IPs are static)."
  value       = aws_lb.nlb.dns_name
}

output "alb_sg_id" {
  description = "Security group ID attached to the ALB."
  value       = aws_security_group.alb.id
}

output "nlb_sg_id" {
  description = "Security group ID attached to the NLB."
  value       = aws_security_group.nlb.id
}

output "alb_frontend_target_group_arn" {
  description = "ALB target group ARN for frontend pods (port 8080). Use in TargetGroupBinding."
  value       = aws_lb_target_group.frontend.arn
}

output "alb_backend_target_group_arn" {
  description = "ALB target group ARN for backend pods (port 8000). Use in TargetGroupBinding."
  value       = aws_lb_target_group.backend.arn
}

output "alb_graph_target_group_arn" {
  description = "ALB target group ARN for graph pods (port 8001). Use in TargetGroupBinding."
  value       = aws_lb_target_group.graph.arn
}
