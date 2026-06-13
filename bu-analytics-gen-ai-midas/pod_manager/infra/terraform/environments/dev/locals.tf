locals {
  helm_set_flags = join(" ", [
    "--set serviceAccount.roleArn=${module.iam_pod_manager.role_arn}",
    "--set serviceName=${var.service_name}",
    "--set global.awsRegion=${var.aws_region}",
    "--set global.deployTarget=aws",
    "--set podManager.env.POD_MANAGER_APP_SERVICE_NAME=${var.service_name}",
    "--set podManager.postgres.tablePrefix=${var.db_table_prefix}",
  ])
}
