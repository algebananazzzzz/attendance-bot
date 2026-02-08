terraform {
  required_version = ">=1.4.2"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.4.0"
    }
  }

  backend "s3" {
    bucket               = ""
    key                  = "attendancebot.tfstate"
    workspace_key_prefix = "tf-state"
    region               = ""
  }

}
