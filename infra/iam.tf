locals {
  lambda_execution_role_name   = "${var.env}-mgmt-iamrole-${var.project_code}"
  lambda_execution_policy_name = "${var.env}-mgmt-iampolicy-${var.project_code}"
}

data "aws_caller_identity" "current" {}

module "lambda_execution_role" {
  source = "./modules/iam_role"
  name   = local.lambda_execution_role_name
  policy_attachments = [
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
  ]
  custom_policy = {
    name = local.lambda_execution_policy_name
    statements = {
      SsmParameters = {
        effect = "Allow"
        actions = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:PutParameter",
        ]
        resources = [
          aws_ssm_parameter.google_sheet_id.arn,
          aws_ssm_parameter.google_service_account_json.arn,
          aws_ssm_parameter.telegram_bot_token.arn,
          aws_ssm_parameter.broadcast_chat_id.arn,
          format(
            "arn:aws:ssm:%s:%s:parameter/%s/*",
            var.region,
            data.aws_caller_identity.current.account_id,
            trimprefix(local.ssm_prefix, "/")
          ),
        ]
      }
    }
  }
}
