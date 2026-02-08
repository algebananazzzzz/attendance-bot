locals {
  ssm_prefix = coalesce(var.ssm_parameter_prefix, "/${var.project_code}/${var.env}")
}

resource "aws_ssm_parameter" "google_sheet_id" {
  name  = "${local.ssm_prefix}/google_sheet_id"
  type  = "SecureString"
  value = "manual-update-required"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "google_service_account_json" {
  name  = "${local.ssm_prefix}/google_service_account_json"
  type  = "SecureString"
  value = "manual-update-required"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "telegram_bot_token" {
  name  = "${local.ssm_prefix}/telegram_bot_token"
  type  = "SecureString"
  value = "manual-update-required"

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "broadcast_chat_id" {
  name  = "${local.ssm_prefix}/broadcast_chat_id"
  type  = "String"
  value = "manual-update-required"

  lifecycle {
    ignore_changes = [value]
  }
}
