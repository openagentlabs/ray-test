# -----------------------------------------------------------------------------
# EKS managed node group scaling invariants (single group, homogeneous instance_types).
# MIDAS targets two m6i.4xlarge-class workers (16 vCPU / 64 GiB per instance type spec);
# backend Helm requests must stay below typical node Allocatable minus DaemonSet slack
# (see midas-api-backend-svc/values.yaml).
# -----------------------------------------------------------------------------

check "eks_node_scaling_order" {
  assert {
    condition = (
      var.eks_node_min_size <= var.eks_node_desired_size &&
      var.eks_node_desired_size <= var.eks_node_max_size &&
      length(var.eks_node_instance_types) > 0
    )
    error_message = "Invalid EKS scaling: require eks_node_min_size <= eks_node_desired_size <= eks_node_max_size and at least one eks_node_instance_types entry."
  }
}

check "eks_mid_two_worker_floor" {
  assert {
    condition     = var.eks_node_desired_size >= 2 && var.eks_node_min_size >= 2
    error_message = "MIDAS expects at least two workers (eks_node_desired_size >= 2 and eks_node_min_size >= 2) so the backend-sized pod and other workloads can run on separate nodes."
  }
}
