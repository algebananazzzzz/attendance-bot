locals {
  vpc_subnet_names = var.vpc_subnet_name_labels == null ? [] : [
    for name in var.vpc_subnet_name_labels : replace(name, "$env", var.env)
  ]
  vpc_security_group_names = var.vpc_security_group_name_labels == null ? [] : [
    for name in var.vpc_security_group_name_labels : replace(name, "$env", var.env)
  ]
}

data "aws_subnets" "lambda" {
  count = length(local.vpc_subnet_names) > 0 ? 1 : 0
  filter {
    name   = "tag:Name"
    values = local.vpc_subnet_names
  }
}

data "aws_security_groups" "lambda" {
  count = length(local.vpc_security_group_names) > 0 ? 1 : 0
  filter {
    name   = "tag:Name"
    values = local.vpc_security_group_names
  }
}
