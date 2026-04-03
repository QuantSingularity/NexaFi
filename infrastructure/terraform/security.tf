# Comprehensive security configuration for NexaFi infrastructure

resource "aws_kms_key" "database" {
  description             = "NexaFi database encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow RDS Service"
        Effect = "Allow"
        Principal = { Service = "rds.amazonaws.com" }
        Action = ["kms:Decrypt", "kms:DescribeKey", "kms:Encrypt", "kms:GenerateDataKey*", "kms:ReEncrypt*"]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-database-key"
    Type    = "encryption"
    Purpose = "database"
  })
}

resource "aws_kms_alias" "database" {
  name          = "alias/${local.name_prefix}-database"
  target_key_id = aws_kms_key.database.key_id
}

resource "aws_kms_key" "backup" {
  description             = "NexaFi backup encryption key"
  deletion_window_in_days = 30
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow Backup Service"
        Effect = "Allow"
        Principal = { Service = "backup.amazonaws.com" }
        Action = ["kms:Decrypt", "kms:DescribeKey", "kms:Encrypt", "kms:GenerateDataKey*", "kms:ReEncrypt*"]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-backup-key"
    Type    = "encryption"
    Purpose = "backup"
  })
}

resource "aws_kms_alias" "backup" {
  name          = "alias/${local.name_prefix}-backup"
  target_key_id = aws_kms_key.backup.key_id
}

# WAF for application protection
resource "aws_wafv2_web_acl" "nexafi_api" {
  name  = "${local.name_prefix}-api-waf"
  scope = "REGIONAL"

  default_action { allow {} }

  rule {
    name     = "RateLimitRule"
    priority = 1
    action { block {} }
    statement {
      rate_based_statement {
        limit              = 2000
        aggregate_key_type = "IP"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "RateLimitRule"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "SQLInjectionRule"
    priority = 2
    action { block {} }
    statement {
      sqli_match_statement {
        field_to_match { body { oversize_handling = "CONTINUE" } }
        text_transformation { priority = 1; type = "URL_DECODE" }
        text_transformation { priority = 2; type = "HTML_ENTITY_DECODE" }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "SQLInjectionRule"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "XSSRule"
    priority = 3
    action { block {} }
    statement {
      xss_match_statement {
        field_to_match { body { oversize_handling = "CONTINUE" } }
        text_transformation { priority = 1; type = "URL_DECODE" }
        text_transformation { priority = 2; type = "HTML_ENTITY_DECODE" }
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "XSSRule"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesCommonRuleSet"
    priority = 4
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesCommonRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "CommonRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  rule {
    name     = "AWSManagedRulesKnownBadInputsRuleSet"
    priority = 5
    override_action { none {} }
    statement {
      managed_rule_group_statement {
        name        = "AWSManagedRulesKnownBadInputsRuleSet"
        vendor_name = "AWS"
      }
    }
    visibility_config {
      cloudwatch_metrics_enabled = true
      metric_name                = "KnownBadInputsRuleSetMetric"
      sampled_requests_enabled   = true
    }
  }

  visibility_config {
    cloudwatch_metrics_enabled = true
    metric_name                = "NexaFiAPIWAF"
    sampled_requests_enabled   = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-api-waf"
    Type = "waf"
  })
}

resource "aws_acm_certificate" "nexafi_api" {
  domain_name               = "api.nexafi.com"
  subject_alternative_names = ["*.api.nexafi.com", "app.nexafi.com", "*.app.nexafi.com"]
  validation_method         = "DNS"
  lifecycle { create_before_destroy = true }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-api-certificate"
    Type = "certificate"
  })
}

resource "aws_secretsmanager_secret" "database_credentials" {
  name                    = "${local.name_prefix}/database/credentials"
  description             = "Database credentials for NexaFi"
  kms_key_id              = aws_kms_key.nexafi_primary.arn
  recovery_window_in_days = 30
  replica { region = var.secondary_region }

  tags = merge(local.common_tags, local.compliance_tags, {
    Name = "${local.name_prefix}-database-credentials"
    Type = "secret"
  })
}

resource "aws_secretsmanager_secret_version" "database_credentials" {
  secret_id = aws_secretsmanager_secret.database_credentials.id
  secret_string = jsonencode({
    username = "nexafi_admin"
    password = random_password.master_password.result
  })
}

resource "random_password" "jwt_secret" {
  length           = 64
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "jwt_secret" {
  name                    = "${local.name_prefix}/auth/jwt-secret"
  description             = "JWT signing secret for NexaFi authentication"
  kms_key_id              = aws_kms_key.nexafi_primary.arn
  recovery_window_in_days = 30
  replica { region = var.secondary_region }

  tags = merge(local.common_tags, local.compliance_tags, {
    Name = "${local.name_prefix}-jwt-secret"
    Type = "secret"
  })
}

resource "aws_secretsmanager_secret_version" "jwt_secret" {
  secret_id     = aws_secretsmanager_secret.jwt_secret.id
  secret_string = jsonencode({ secret = random_password.jwt_secret.result })
}

resource "aws_ssm_parameter" "app_config" {
  name = "/${local.name_prefix}/app/config"
  type = "String"
  value = jsonencode({
    environment = var.environment
    region      = var.primary_region
    cluster     = module.eks_primary.cluster_name
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-app-config"
    Type = "parameter"
  })
}

resource "aws_iam_role" "financial_services_role" {
  name = "${local.name_prefix}-financial-services-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = module.eks_primary.oidc_provider_arn
        }
        Condition = {
          StringEquals = {
            "${replace(module.eks_primary.cluster_oidc_issuer_url, "https://", "")}:sub" = "system:serviceaccount:financial-services:financial-services-sa"
            "${replace(module.eks_primary.cluster_oidc_issuer_url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = merge(local.common_tags, local.compliance_tags, {
    Name = "${local.name_prefix}-financial-services-role"
    Type = "iam-role"
  })
}

resource "aws_iam_policy" "financial_services_policy" {
  name        = "${local.name_prefix}-financial-services-policy"
  description = "IAM policy for financial services"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue", "secretsmanager:DescribeSecret"]
        Resource = [aws_secretsmanager_secret.database_credentials.arn, aws_secretsmanager_secret.jwt_secret.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"]
        Resource = "arn:aws:ssm:${var.primary_region}:${data.aws_caller_identity.current.account_id}:parameter/${local.name_prefix}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:DescribeKey"]
        Resource = [aws_kms_key.nexafi_primary.arn, aws_kms_key.database.arn]
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "arn:aws:s3:::${local.name_prefix}-*/*"
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
        Resource = "arn:aws:logs:${var.primary_region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/eks/${local.name_prefix}-*"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-financial-services-policy"
    Type = "iam-policy"
  })
}

resource "aws_iam_role_policy_attachment" "financial_services_policy_attachment" {
  role       = aws_iam_role.financial_services_role.name
  policy_arn = aws_iam_policy.financial_services_policy.arn
}

resource "aws_securityhub_insight" "nexafi_critical_findings" {
  filters {
    severity_label {
      comparison = "EQUALS"
      value      = "CRITICAL"
    }
    resource_tags {
      comparison = "EQUALS"
      key        = "Project"
      value      = "NexaFi"
    }
  }
  group_by_attribute = "ResourceId"
  name               = "NexaFi Critical Security Findings"
}

resource "aws_config_config_rule" "encrypted_volumes" {
  name = "${local.name_prefix}-encrypted-volumes"
  source {
    owner             = "AWS"
    source_identifier = "ENCRYPTED_VOLUMES"
  }
  depends_on = [aws_config_configuration_recorder_status.nexafi]
  tags       = merge(local.common_tags, { Name = "${local.name_prefix}-encrypted-volumes-rule", Type = "config-rule" })
}

resource "aws_config_config_rule" "root_access_key_check" {
  name = "${local.name_prefix}-root-access-key-check"
  source {
    owner             = "AWS"
    source_identifier = "ROOT_ACCESS_KEY_CHECK"
  }
  depends_on = [aws_config_configuration_recorder_status.nexafi]
  tags       = merge(local.common_tags, { Name = "${local.name_prefix}-root-access-key-check", Type = "config-rule" })
}

resource "aws_config_config_rule" "mfa_enabled_for_iam_console_access" {
  name = "${local.name_prefix}-mfa-enabled-for-iam-console-access"
  source {
    owner             = "AWS"
    source_identifier = "MFA_ENABLED_FOR_IAM_CONSOLE_ACCESS"
  }
  depends_on = [aws_config_configuration_recorder_status.nexafi]
  tags       = merge(local.common_tags, { Name = "${local.name_prefix}-mfa-enabled-rule", Type = "config-rule" })
}

resource "aws_config_config_rule" "s3_bucket_ssl_requests_only" {
  name = "${local.name_prefix}-s3-ssl-requests-only"
  source {
    owner             = "AWS"
    source_identifier = "S3_BUCKET_SSL_REQUESTS_ONLY"
  }
  depends_on = [aws_config_configuration_recorder_status.nexafi]
  tags       = merge(local.common_tags, { Name = "${local.name_prefix}-s3-ssl-rule", Type = "config-rule" })
}

resource "aws_inspector2_enabler" "nexafi" {
  account_ids    = [data.aws_caller_identity.current.account_id]
  resource_types = ["ECR", "EC2"]
}

resource "aws_macie2_account" "nexafi" {
  finding_publishing_frequency = "FIFTEEN_MINUTES"
  status                       = "ENABLED"
}

resource "aws_s3_bucket" "security_logs" {
  bucket        = "${local.name_prefix}-security-logs-${random_id.bucket_suffix.hex}"
  force_destroy = false

  tags = merge(local.common_tags, local.compliance_tags, {
    Name = "${local.name_prefix}-security-logs"
    Type = "security-logs"
  })
}

resource "aws_s3_bucket_versioning" "security_logs" {
  bucket = aws_s3_bucket.security_logs.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "security_logs" {
  bucket = aws_s3_bucket.security_logs.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.nexafi_primary.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "security_logs" {
  bucket                  = aws_s3_bucket.security_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "security_logs" {
  bucket     = aws_s3_bucket.security_logs.id
  depends_on = [aws_s3_bucket_versioning.security_logs]

  rule {
    id     = "security_log_lifecycle"
    status = "Enabled"
    filter { prefix = "" }
    transition { days = 30; storage_class = "STANDARD_IA" }
    transition { days = 90; storage_class = "GLACIER" }
    transition { days = 365; storage_class = "DEEP_ARCHIVE" }
    expiration { days = 2555 }
  }
}

resource "aws_cloudwatch_metric_alarm" "high_error_rate" {
  alarm_name          = "${local.name_prefix}-high-error-rate"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "4XXError"
  namespace           = "AWS/ApplicationELB"
  period              = "300"
  statistic           = "Sum"
  threshold           = "100"
  alarm_description   = "High 4XX error rate detected"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
  ok_actions          = [aws_sns_topic.security_alerts.arn]
  treat_missing_data  = "notBreaching"

  dimensions = {
    LoadBalancer = "app/${local.name_prefix}-alb"
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-high-error-rate-alarm"
    Type = "cloudwatch-alarm"
  })
}

resource "aws_cloudwatch_metric_alarm" "failed_login_attempts" {
  alarm_name          = "${local.name_prefix}-failed-login-attempts"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FailedLoginAttempts"
  namespace           = "NexaFi/Security"
  period              = "300"
  statistic           = "Sum"
  threshold           = "10"
  alarm_description   = "High number of failed login attempts detected"
  alarm_actions       = [aws_sns_topic.security_alerts.arn]
  treat_missing_data  = "notBreaching"

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-failed-login-attempts-alarm"
    Type = "cloudwatch-alarm"
  })
}

resource "aws_sns_topic" "security_alerts" {
  name              = "${local.name_prefix}-security-alerts"
  kms_master_key_id = aws_kms_key.nexafi_primary.arn

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-security-alerts"
    Type = "sns-topic"
  })
}

# GuardDuty EventBridge - severity is a numeric range 0.0-10.0;
# use numeric_greater_than_or_equals to catch all High (7.0+) and Critical (9.0+) findings
resource "aws_cloudwatch_event_rule" "guardduty_findings" {
  name        = "${local.name_prefix}-guardduty-findings"
  description = "Capture GuardDuty High and Critical findings"

  event_pattern = jsonencode({
    source      = ["aws.guardduty"]
    detail-type = ["GuardDuty Finding"]
    detail = {
      severity = [{ numeric = [">=", 7] }]
    }
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-guardduty-findings-rule"
    Type = "eventbridge-rule"
  })
}

resource "aws_cloudwatch_event_target" "guardduty_sns" {
  rule      = aws_cloudwatch_event_rule.guardduty_findings.name
  target_id = "SendToSNS"
  arn       = aws_sns_topic.security_alerts.arn
}

resource "aws_sns_topic_policy" "security_alerts" {
  arn = aws_sns_topic.security_alerts.arn

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AllowEventBridgePublish"
        Effect = "Allow"
        Principal = { Service = "events.amazonaws.com" }
        Action   = "SNS:Publish"
        Resource = aws_sns_topic.security_alerts.arn
      },
      {
        Sid    = "AllowCloudWatchPublish"
        Effect = "Allow"
        Principal = { Service = "cloudwatch.amazonaws.com" }
        Action   = "SNS:Publish"
        Resource = aws_sns_topic.security_alerts.arn
      }
    ]
  })
}
