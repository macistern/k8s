resource "aws_iam_policy" "aws_load_balancer_controller" {
  name   = "AWSLoadBalancerControllerIAMPolicy-devops-tutorial"
  policy = file("${path.module}/aws_load_balancer_controller_iam_policy.json")
}

resource "aws_iam_role_policy_attachment" "aws_load_balancer_controller_node_role" {
  policy_arn = aws_iam_policy.aws_load_balancer_controller.arn
  role       = aws_iam_role.eks_node_role.name
}

output "eks_node_role_arn" {
  value = aws_iam_role.eks_node_role.arn
}
