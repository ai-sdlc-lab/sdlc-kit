terraform {
  required_version = ">= 1.10"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 6.69" }
  }
  backend "s3" {
    bucket       = "sdlc-lab-tfstate-992382408037"
    key          = "apps/@@NAME@@/dev/terraform.tfstate"
    region       = "eu-north-1"
    use_lockfile = true
  }
}

provider "aws" {
  region              = "eu-north-1"
  allowed_account_ids = ["992382408037"]
  default_tags {
    tags = { project = "sdlc-lab" }
  }
}

locals {
  env      = "dev"
  name     = "sdlc-lab-app-@@NAME@@-${local.env}" # also the execution role name (lab-admin deploy policy)
  boundary = "arn:aws:iam::992382408037:policy/sdlc-lab-boundary"
}

# --- API + web on Lambda --------------------------------------------------------

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = 7
}

resource "aws_iam_role" "api" {
  name                 = local.name
  permissions_boundary = local.boundary
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "api" {
  role = aws_iam_role.api.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.api.arn}:*"
      },
    ]
  })
}

resource "aws_lambda_function" "api" {
  function_name    = local.name
  role             = aws_iam_role.api.arn
  runtime          = "python3.14"
  architectures    = ["arm64"]
  handler          = "app.main.handler"
  filename         = "${path.module}/../build/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../build/lambda.zip")
  memory_size      = 128
  timeout          = 10
  depends_on       = [aws_cloudwatch_log_group.api, aws_iam_role_policy.api]
}

# Public, unauthenticated, read-only (Phase 3 fallback: no CloudFront, see lab-admin BASELINE).
resource "aws_lambda_function_url" "api" {
  function_name      = aws_lambda_function.api.function_name
  authorization_type = "NONE"
}

# Since Oct 2025 a NONE function URL needs both permissions (Lambda docs: urls-auth).
resource "aws_lambda_permission" "url" {
  statement_id           = "FunctionURLAllowPublicAccess"
  function_name          = aws_lambda_function.api.function_name
  action                 = "lambda:InvokeFunctionUrl"
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "invoke_via_url" {
  statement_id             = "FunctionURLInvokeAllowPublicAccess"
  function_name            = aws_lambda_function.api.function_name
  action                   = "lambda:InvokeFunction"
  principal                = "*"
  invoked_via_function_url = true
}

output "url" {
  value = aws_lambda_function_url.api.function_url
}
