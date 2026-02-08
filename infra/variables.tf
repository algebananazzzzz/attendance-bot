variable "region" {
  description = "The region where resources will be deployed."
  default     = "ap-southeast-1"
}

variable "project_code" {
  description = "The code name of the project used for naming convention."
}

variable "env" {
  description = "The target environment to which the resources will be deployed."
}

variable "google_sheet_name" {
  description = "Google Sheet name for attendance."
  default     = "Attendance"
}

variable "ssm_parameter_prefix" {
  description = "Prefix for SSM Parameter Store paths."
  default     = null
}

variable "vpc_subnet_name_labels" {
  description = "Subnet Name tag labels used to place the Lambda in a VPC."
  type        = list(string)
  default     = null
}

variable "vpc_security_group_name_labels" {
  description = "Security Group Name tag labels used to place the Lambda in a VPC."
  type        = list(string)
  default     = null
}

variable "vpc_ipv6_allowed_for_dual_stack" {
  description = "Allow IPv6 traffic for dual-stack subnets."
  type        = bool
  default     = false
}
