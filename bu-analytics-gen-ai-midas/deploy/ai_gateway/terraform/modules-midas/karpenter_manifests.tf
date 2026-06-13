# Karpenter Node definitions basically telling the application how and when to 
# scale for managed controller instances

# Small note:
# NodeClass -> How to build EC2 nodes when needed
# NodePool -> When, why and what kind of nodes to build

#Karpenter helm chart, used to automatically scale nodes for managed controllers in cloudbees
# resource "helm_release" "karpenter_chart" {
#   name      = "karpenter"
#   namespace = "karpenter"

#   repository = "oci://public.ecr.aws/karpenter"
#   chart      = "karpenter"
#   create_namespace = true

#   timeout = 600
#   wait    = true

#   values = [
#     yamlencode({
#       serviceAccount = {
#         annotations = {
#           "eks.amazonaws.com/role-arn" = aws_iam_role.karpenter_iam_role.arn
#         }
#       }
#       settings = {
#         clusterName     = aws_eks_cluster.exlerate_eks_cluster.name
#         clusterEndpoint = aws_eks_cluster.exlerate_eks_cluster.endpoint
#         aws = {
#           defaultInstanceProfile = aws_iam_role.karpenter_node_role.name
#         }
#       }
#     })
#   ]
# }

# NodeClass Definition:
# resource "kubernetes_manifest" "ec2_node_class" {
#   manifest = {
#     apiVersion = "karpenter.k8s.aws/v1"
#     kind       = "EC2NodeClass"
#     metadata = {
#       name = "default"
#     }
#     spec = {
#       amiFamily = var.ami_type
#       amiSelectorTerms = [{
#         alias = "bottlerocket@latest"
#       }]
#       role      = aws_iam_role.karpenter_node_role.arn
#       subnetSelectorTerms = [{
#         tags = {
#           "karpenter.sh/discovery" = "${aws_eks_cluster.exlerate_eks_cluster.name}"
#         }
#       }]
#       securityGroupSelectorTerms = [{
#         tags = {
#           "karpenter.sh/discovery" = "${aws_eks_cluster.exlerate_eks_cluster.name}"
#         }
#       }]
#     }
#   }

#   depends_on = [helm_release.karpenter_chart]
# }

# # NodePool Definition:
# resource "kubernetes_manifest" "node_pool" {
#   manifest = {
#     apiVersion = "karpenter.sh/v1"
#     kind       = "NodePool"
#     metadata = {
#       name = "default"
#     }
#     spec = {
#       weight = 100
#       template = {
#         spec = {
#           nodeClassRef = {
#             name = kubernetes_manifest.ec2_node_class.manifest["metadata"]["name"]
#             group = "karpenter.k8s.aws"
#             kind  = "EC2NodeClass"
#           }
#           requirements = [
#             {
#               key      = "node.kubernetes.io/instance-type"
#               operator = "In"
#               values   = ["t3.2xlarge", "t3.xlarge", "t3.large", "t3.medium"]
#             },
#             {
#               key      = "karpenter.sh/capacity-type"
#               operator = "In"
#               values   = ["on-demand"]
#             }
#           ]
#         }
#       }
#       limits = {
#         cpu = "100"
#       }
#       disruption = {
#         consolidationPolicy = "WhenEmpty"
#         consolidateAfter    = "30s"
#       }
#     }
#   }

#   depends_on = [helm_release.karpenter_chart, kubernetes_manifest.ec2_node_class]
# }