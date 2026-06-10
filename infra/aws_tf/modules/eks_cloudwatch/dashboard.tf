resource "aws_cloudwatch_dashboard" "eks" {
  dashboard_name = "${var.solution.name}-eks-${var.cluster_name}"

  dashboard_body = jsonencode({
    widgets = concat(
      [
        {
          type   = "text"
          x      = 0
          y      = 0
          width  = 24
          height = 2
          properties = {
            markdown = "# EKS Fargate — ${var.cluster_name}\nContainer Insights metrics, control plane logs, and application log volume for `${var.solution.name}`."
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 2
          width  = 8
          height = 6
          properties = {
            title  = "Running pods (cluster)"
            region = var.solution.region
            view   = "timeSeries"
            stat   = "Average"
            period = 60
            metrics = [
              ["ContainerInsights", "service_number_of_running_pods", "ClusterName", var.cluster_name],
            ]
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 2
          width  = 8
          height = 6
          properties = {
            title  = "Pod CPU utilization"
            region = var.solution.region
            view   = "timeSeries"
            stat   = "Average"
            period = 60
            metrics = [
              ["ContainerInsights", "pod_cpu_utilization", "ClusterName", var.cluster_name, { stat = "Average" }],
            ]
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 2
          width  = 8
          height = 6
          properties = {
            title  = "Pod memory utilization"
            region = var.solution.region
            view   = "timeSeries"
            stat   = "Average"
            period = 60
            metrics = [
              ["ContainerInsights", "pod_memory_utilization", "ClusterName", var.cluster_name, { stat = "Average" }],
            ]
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 8
          width  = 8
          height = 6
          properties = {
            title  = "Pod network RX bytes"
            region = var.solution.region
            view   = "timeSeries"
            stat   = "Sum"
            period = 60
            metrics = [
              ["ContainerInsights", "pod_network_rx_bytes", "ClusterName", var.cluster_name],
            ]
          }
        },
        {
          type   = "metric"
          x      = 8
          y      = 8
          width  = 8
          height = 6
          properties = {
            title  = "Pod network TX bytes"
            region = var.solution.region
            view   = "timeSeries"
            stat   = "Sum"
            period = 60
            metrics = [
              ["ContainerInsights", "pod_network_tx_bytes", "ClusterName", var.cluster_name],
            ]
          }
        },
        {
          type   = "metric"
          x      = 16
          y      = 8
          width  = 8
          height = 6
          properties = {
            title  = "Container restarts"
            region = var.solution.region
            view   = "timeSeries"
            stat   = "Sum"
            period = 60
            metrics = [
              ["ContainerInsights", "pod_number_of_container_restarts", "ClusterName", var.cluster_name],
            ]
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 14
          width  = 12
          height = 6
          properties = {
            title  = "EKS container log volume (platform group)"
            region = var.solution.region
            view   = "timeSeries"
            stat   = "Sum"
            period = 300
            metrics = [
              ["AWS/Logs", "IncomingBytes", "LogGroupName", local.eks_containers_log_group, { stat = "Sum" }],
            ]
          }
        },
        {
          type   = "metric"
          x      = 12
          y      = 14
          width  = 12
          height = 6
          properties = {
            title  = "Container Insights application log volume"
            region = var.solution.region
            view   = "timeSeries"
            stat   = "Sum"
            period = 300
            metrics = [
              ["AWS/Logs", "IncomingBytes", "LogGroupName", local.container_insights_application, { stat = "Sum" }],
            ]
          }
        },
        {
          type   = "metric"
          x      = 0
          y      = 20
          width  = 24
          height = 6
          properties = {
            title  = "Application service log volume (IncomingBytes)"
            region = var.solution.region
            view   = "timeSeries"
            stat   = "Sum"
            period = 300
            metrics = [
              for key, name in var.application_log_group_names :
              ["AWS/Logs", "IncomingBytes", "LogGroupName", name, { stat = "Sum", label = key }]
            ]
          }
        },
        {
          type   = "log"
          x      = 0
          y      = 26
          width  = 12
          height = 8
          properties = {
            title  = "EKS control plane — errors"
            region = var.solution.region
            query  = "SOURCE '${local.eks_control_plane_log_group}' | filter @message like /(?i)(error|fail|denied)/ | sort @timestamp desc | limit 50"
          }
        },
        {
          type   = "log"
          x      = 12
          y      = 26
          width  = 12
          height = 8
          properties = {
            title  = "Fargate container stdout/stderr"
            region = var.solution.region
            query  = "SOURCE '${local.eks_containers_log_group}' | sort @timestamp desc | limit 50"
          }
        },
        {
          type   = "log"
          x      = 0
          y      = 34
          width  = 24
          height = 8
          properties = {
            title  = "Container Insights — recent application logs"
            region = var.solution.region
            query  = "SOURCE '${local.container_insights_application}' | sort @timestamp desc | limit 50"
          }
        },
      ],
    )
  })
}
