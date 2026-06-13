check "lustre_client_bootstrap_inputs" {
  assert {
    condition = !var.install_lustre_client || (
      length(trimspace(var.cluster_endpoint)) > 0 &&
      length(trimspace(var.cluster_certificate_authority_data)) > 0 &&
      length(trimspace(var.cluster_service_ipv4_cidr)) > 0
    )
    error_message = "When install_lustre_client is true, cluster_endpoint, cluster_certificate_authority_data, and cluster_service_ipv4_cidr are required for nodeadm bootstrap."
  }
}
