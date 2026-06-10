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

variable "email_subscription_endpoints" {
  description = <<-EOT
    Email addresses to subscribe to the SNS topic with protocol `email`.
    After apply, each address receives a confirmation email from AWS; the subscription stays
    `pending_confirmation` until confirmed. Only confirmed subscribers receive publishes from notification.svc.
  EOT
  type        = list(string)
  nullable    = false
  default     = []
}
