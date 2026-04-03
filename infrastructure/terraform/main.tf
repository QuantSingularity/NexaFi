# Main infrastructure configuration - see versions.tf for terraform block

provider "aws" {
  region = var.primary_region

  default_tags {
    tags = {
      Project            = "NexaFi"
      Environment        = var.environment
      ManagedBy          = "Terraform"
      SecurityCompliance = "PCI-DSS,SOC2,GDPR"
      DataClassification = "Confidential"
      BackupRequired     = "true"
      MonitoringEnabled  = "true"
    }
  }
}

provider "aws" {
  alias  = "secondary"
  region = var.secondary_region

  default_tags {
    tags = {
      Project            = "NexaFi"
      Environment        = var.environment
      ManagedBy          = "Terraform"
      SecurityCompliance = "PCI-DSS,SOC2,GDPR"
      DataClassification = "Confidential"
      BackupRequired     = "true"
      MonitoringEnabled  = "true"
      DisasterRecovery   = "true"
    }
  }
}

# Kubernetes and Helm providers - uncomment after EKS cluster creation
# provider "kubernetes" {
#   host                   = module.eks_primary.cluster_endpoint
#   cluster_ca_certificate = base64decode(module.eks_primary.cluster_certificate_authority_data)
#   exec {
#     api_version = "client.authentication.k8s.io/v1beta1"
#     command     = "aws"
#     args        = ["eks", "get-token", "--cluster-name", module.eks_primary.cluster_name]
#   }
# }
# provider "helm" {
#   kubernetes {
#     host                   = module.eks_primary.cluster_endpoint
#     cluster_ca_certificate = base64decode(module.eks_primary.cluster_certificate_authority_data)
#     exec {
#       api_version = "client.authentication.k8s.io/v1beta1"
#       command     = "aws"
#       args        = ["eks", "get-token", "--cluster-name", module.eks_primary.cluster_name]
#     }
#   }
# }

locals {
  name_prefix = "nexafi-${var.environment}"

  common_tags = {
    Project            = "NexaFi"
    Environment        = var.environment
    ManagedBy          = "Terraform"
    SecurityCompliance = "PCI-DSS,SOC2,GDPR"
    DataClassification = "Confidential"
  }

  compliance_tags = {
    PCI_DSS_Scope    = "true"
    SOC2_Type2       = "true"
    GDPR_Applicable  = "true"
    SOX_Applicable   = "true"
    GLBA_Applicable  = "true"
    FFIEC_Applicable = "true"
  }

  security_config = {
    enable_encryption_at_rest     = true
    enable_encryption_in_transit  = true
    enable_network_segmentation   = true
    enable_audit_logging          = true
    enable_vulnerability_scanning = true
    enable_intrusion_detection    = true
    enable_data_loss_prevention   = true
  }

  monitoring_config = {
    enable_cloudtrail          = true
    enable_config_rules        = true
    enable_guardduty           = true
    enable_security_hub        = true
    enable_inspector           = true
    enable_macie               = true
    enable_cloudwatch_insights = true
  }

  backup_config = {
    backup_retention_days     = 2555
    cross_region_backup       = true
    point_in_time_recovery    = true
    automated_backup_testing  = true
    disaster_recovery_testing = true
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_availability_zones" "available" {
  state = "available"
}

resource "random_password" "master_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

# KMS key for primary region
resource "aws_kms_key" "nexafi_primary" {
  description             = "NexaFi primary encryption key"
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
        Sid    = "Allow EKS Service"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow CloudTrail"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action = [
          "kms:GenerateDataKey*",
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-primary-key"
    Type = "encryption"
  })
}

resource "aws_kms_alias" "nexafi_primary" {
  name          = "alias/${local.name_prefix}-primary"
  target_key_id = aws_kms_key.nexafi_primary.key_id
}

# CloudTrail for audit logging
resource "aws_cloudtrail" "nexafi_audit" {
  name           = "${local.name_prefix}-audit-trail"
  s3_bucket_name = aws_s3_bucket.audit_logs.bucket

  include_global_service_events = true
  is_multi_region_trail         = true
  enable_logging                = true
  enable_log_file_validation    = true
  kms_key_id                    = aws_kms_key.nexafi_primary.arn

  event_selector {
    read_write_type           = "All"
    include_management_events = true

    data_resource {
      type   = "AWS::S3::Object"
      values = ["arn:aws:s3:::${aws_s3_bucket.audit_logs.bucket}/"]
    }

    data_resource {
      type   = "AWS::Lambda::Function"
      values = ["arn:aws:lambda"]
    }
  }

  insight_selector {
    insight_type = "ApiCallRateInsight"
  }

  insight_selector {
    insight_type = "ApiErrorRateInsight"
  }

  depends_on = [
    aws_s3_bucket_policy.audit_logs,
    aws_s3_bucket.audit_logs,
  ]

  tags = merge(local.common_tags, local.compliance_tags, {
    Name = "${local.name_prefix}-audit-trail"
    Type = "audit"
  })
}

# S3 bucket for audit logs
resource "aws_s3_bucket" "audit_logs" {
  bucket        = "${local.name_prefix}-audit-logs-${random_id.bucket_suffix.hex}"
  force_destroy = false

  tags = merge(local.common_tags, local.compliance_tags, {
    Name = "${local.name_prefix}-audit-logs"
    Type = "audit"
  })
}

resource "aws_s3_bucket_versioning" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.nexafi_primary.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "audit_logs" {
  bucket                  = aws_s3_bucket.audit_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "audit_logs" {
  bucket = aws_s3_bucket.audit_logs.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AWSCloudTrailAclCheck"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:GetBucketAcl"
        Resource = "arn:aws:s3:::${aws_s3_bucket.audit_logs.bucket}"
      },
      {
        Sid    = "AWSCloudTrailWrite"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "arn:aws:s3:::${aws_s3_bucket.audit_logs.bucket}/AWSLogs/${data.aws_caller_identity.current.account_id}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      },
      {
        Sid    = "DenyInsecureTransport"
        Effect = "Deny"
        Principal = "*"
        Action   = "s3:*"
        Resource = [
          "arn:aws:s3:::${aws_s3_bucket.audit_logs.bucket}",
          "arn:aws:s3:::${aws_s3_bucket.audit_logs.bucket}/*"
        ]
        Condition = {
          Bool = {
            "aws:SecureTransport" = "false"
          }
        }
      }
    ]
  })
}

resource "aws_s3_bucket_lifecycle_configuration" "audit_logs" {
  bucket     = aws_s3_bucket.audit_logs.id
  depends_on = [aws_s3_bucket_versioning.audit_logs]

  rule {
    id     = "audit_log_lifecycle"
    status = "Enabled"
    filter { prefix = "" }

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }
    transition {
      days          = 90
      storage_class = "GLACIER"
    }
    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }
    expiration {
      days = 2555
    }
    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# GuardDuty for threat detection
resource "aws_guardduty_detector" "nexafi" {
  enable = true

  datasources {
    s3_logs {
      enable = true
    }
    kubernetes {
      audit_logs {
        enable = true
      }
    }
    malware_protection {
      scan_ec2_instance_with_findings {
        ebs_volumes {
          enable = true
        }
      }
    }
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-guardduty"
    Type = "security"
  })
}

# Security Hub
resource "aws_securityhub_account" "nexafi" {
  enable_default_standards = true
  depends_on               = [aws_guardduty_detector.nexafi]
}

# AWS Config recorder
resource "aws_config_configuration_recorder" "nexafi" {
  name     = "${local.name_prefix}-config-recorder"
  role_arn = aws_iam_role.config.arn

  recording_group {
    all_supported                 = true
    include_global_resource_types = true
  }
}

# Config recorder status - actually starts the recorder
resource "aws_config_configuration_recorder_status" "nexafi" {
  name       = aws_config_configuration_recorder.nexafi.name
  is_enabled = true
  depends_on = [aws_config_delivery_channel.nexafi]
}

resource "aws_config_delivery_channel" "nexafi" {
  name           = "${local.name_prefix}-config-delivery"
  s3_bucket_name = aws_s3_bucket.config.bucket
  depends_on     = [aws_config_configuration_recorder.nexafi]
}

resource "aws_s3_bucket" "config" {
  bucket        = "${local.name_prefix}-config-${random_id.bucket_suffix.hex}"
  force_destroy = false

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-config"
    Type = "compliance"
  })
}

resource "aws_s3_bucket_public_access_block" "config" {
  bucket                  = aws_s3_bucket.config.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "config" {
  bucket = aws_s3_bucket.config.id
  rule {
    apply_server_side_encryption_by_default {
      kms_master_key_id = aws_kms_key.nexafi_primary.arn
      sse_algorithm     = "aws:kms"
    }
    bucket_key_enabled = true
  }
}

# IAM role for Config
resource "aws_iam_role" "config" {
  name = "${local.name_prefix}-config-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "config.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-config-role"
    Type = "iam"
  })
}

resource "aws_iam_role_policy_attachment" "config" {
  role       = aws_iam_role.config.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWS_ConfigRole"
}

resource "aws_iam_role_policy" "config_s3" {
  name = "${local.name_prefix}-config-s3-policy"
  role = aws_iam_role.config.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["s3:PutObject"]
        Resource = "arn:aws:s3:::${aws_s3_bucket.config.bucket}/AWSLogs/*"
        Condition = {
          StringLike = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetBucketAcl"]
        Resource = "arn:aws:s3:::${aws_s3_bucket.config.bucket}"
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt", "kms:GenerateDataKey"]
        Resource = aws_kms_key.nexafi_primary.arn
      }
    ]
  })
}
