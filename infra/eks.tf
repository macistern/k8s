locals {
  cluster_name = "cluster-tutorial"
}

resource "aws_launch_template" "eks_nodes" {
  name_prefix = "${local.cluster_name}-nodes-"

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }
}

resource "aws_eks_cluster" "cluster" {
  name     = local.cluster_name
  version  = "1.35"
  role_arn = aws_iam_role.eks_cluster_role.arn
  vpc_config {
    subnet_ids              = concat(aws_subnet.public[*].id, aws_subnet.private[*].id)
    security_group_ids      = [aws_security_group.cluster.id]
    endpoint_private_access = true
    endpoint_public_access  = true
  }

  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = true
  }

  depends_on = [aws_iam_role_policy_attachment.eks_cluster_policy]

  tags = {
    Name = "devops-cluster"
  }
}

resource "aws_eks_node_group" "node_group" {
  cluster_name    = aws_eks_cluster.cluster.name
  node_group_name = "node-group-tutorial"
  node_role_arn   = aws_iam_role.eks_node_role.arn
  subnet_ids      = aws_subnet.public[*].id
  version         = "1.35"

  launch_template {
    id      = aws_launch_template.eks_nodes.id
    version = aws_launch_template.eks_nodes.latest_version
  }

  scaling_config {
    desired_size = 1
    max_size     = 2
    min_size     = 1
  }

  instance_types = [var.eks_node_instance_type]

  depends_on = [
    aws_iam_role_policy_attachment.eks_worker_node_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
    aws_iam_role_policy_attachment.eks_registry_policy,
    aws_iam_role_policy_attachment.aws_load_balancer_controller_node_role,
  ]

  tags = {
    Name = "devops-node-group"
  }
}

variable "eks_node_instance_type" {
  description = "EC2 instance type for the EKS managed node group. Choose a type supported by EKS and your account's SCP/Free Tier restrictions."
  type        = string
  default     = "t3.small"
}

data "aws_eks_cluster_auth" "cluster" {
  name = aws_eks_cluster.cluster.name
}

output "cluster_endpoint" {
  value = aws_eks_cluster.cluster.endpoint
}

output "cluster_name" {
  value = aws_eks_cluster.cluster.name
}
