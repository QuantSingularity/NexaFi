# Terraform Outputs

output "primary_vpc_id" {
  description = "ID of the primary VPC"
  value       = module.vpc_primary.vpc_id
}

output "secondary_vpc_id" {
  description = "ID of the secondary VPC"
  value       = module.vpc_secondary.vpc_id
}

output "primary_eks_cluster_name" {
  description = "Name of the primary EKS cluster"
  value       = module.eks_primary.cluster_name
}

output "secondary_eks_cluster_name" {
  description = "Name of the secondary EKS cluster"
  value       = module.eks_secondary.cluster_name
}

output "primary_eks_cluster_endpoint" {
  description = "Endpoint of the primary EKS cluster"
  value       = module.eks_primary.cluster_endpoint
  sensitive   = true
}

output "primary_eks_cluster_certificate_authority_data" {
  description = "Base64 encoded certificate authority data for primary cluster"
  value       = module.eks_primary.cluster_certificate_authority_data
  sensitive   = true
}

output "kms_key_id" {
  description = "ID of the primary KMS key"
  value       = aws_kms_key.nexafi_primary.key_id
}

output "kms_key_arn" {
  description = "ARN of the primary KMS key"
  value       = aws_kms_key.nexafi_primary.arn
}

output "cloudtrail_arn" {
  description = "ARN of the CloudTrail"
  value       = aws_cloudtrail.nexafi_audit.arn
}

output "audit_logs_bucket" {
  description = "Name of the audit logs S3 bucket"
  value       = aws_s3_bucket.audit_logs.bucket
}

output "security_logs_bucket" {
  description = "Name of the security logs S3 bucket"
  value       = aws_s3_bucket.security_logs.bucket
}

output "sns_security_alerts_arn" {
  description = "ARN of the security alerts SNS topic"
  value       = aws_sns_topic.security_alerts.arn
}

output "efs_file_system_id" {
  description = "ID of the EFS file system for shared storage"
  value       = aws_efs_file_system.shared_storage.id
}
