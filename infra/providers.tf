terraform {
  required_version = ">= 1.5.0"

  backend "s3" {
    bucket         = "tailord-tf-state"
    key            = "infra/terraform.tfstate"
    region         = "us-east-2"
    dynamodb_table = "tailord-tf-lock"
    encrypt        = true
  }

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region

   default_tags {
    tags = {
      Environment = "Development"
      Project     = var.project_name
      ManagedBy   = "Terraform"
    }
  }
}
