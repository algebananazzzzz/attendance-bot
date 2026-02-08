locals {
  function_name = "${var.env}-app-func-${var.project_code}"
  lambda_subnet_ids = try(data.aws_subnets.lambda[0].ids, [])
  lambda_sg_ids     = try(data.aws_security_groups.lambda[0].ids, [])
  vpc_config = (
    length(local.lambda_subnet_ids) > 0 && length(local.lambda_sg_ids) > 0
    ? {
        subnet_ids                  = local.lambda_subnet_ids
        security_group_ids          = local.lambda_sg_ids
        ipv6_allowed_for_dual_stack = var.vpc_ipv6_allowed_for_dual_stack
      }
    : null
  )
}

module "lambda_function" {
  source             = "./modules/lambda_function"
  function_name      = local.function_name
  execution_role_arn = module.lambda_execution_role.role.arn
  deployment_package = {
    image_uri = "${aws_ecr_repository.this.repository_url}:placeholder"
  }
  ignore_deployment_package_changes = true

  depends_on = [null_resource.push_placeholder_image]

  timeout                = 30
  memory_size            = 1024
  ephemeral_storage_size = 512

  vpc_config = local.vpc_config

  environment_variables = {
    GOOGLE_SHEET_NAME            = var.google_sheet_name
    TELEGRAM_BOT_TOKEN_PARAM     = aws_ssm_parameter.telegram_bot_token.name
    GOOGLE_SHEET_ID_PARAM        = aws_ssm_parameter.google_sheet_id.name
    GOOGLE_SERVICE_ACCOUNT_PARAM = aws_ssm_parameter.google_service_account_json.name
    BROADCAST_CHAT_ID_PARAM      = aws_ssm_parameter.broadcast_chat_id.name
  }
}
