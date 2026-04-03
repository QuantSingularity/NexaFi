# Enhanced EKS configuration for NexaFi with financial industry security standards

# Secondary-region KMS key for encrypting secondary EKS secrets
resource "aws_kms_key" "nexafi_secondary" {
  provider                = aws.secondary
  description             = "NexaFi secondary region encryption key"
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
        Action   = ["kms:Decrypt", "kms:DescribeKey"]
        Resource = "*"
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name   = "${local.name_prefix}-secondary-key"
    Type   = "encryption"
    Region = var.secondary_region
  })
}

resource "aws_kms_alias" "nexafi_secondary" {
  provider      = aws.secondary
  name          = "alias/${local.name_prefix}-secondary"
  target_key_id = aws_kms_key.nexafi_secondary.key_id
}

# Primary EKS Cluster
module "eks_primary" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "${local.name_prefix}-primary"
  cluster_version = var.eks_cluster_version

  vpc_id                   = module.vpc_primary.vpc_id
  subnet_ids               = module.vpc_primary.private_subnets
  control_plane_subnet_ids = module.vpc_primary.intra_subnets

  cluster_endpoint_private_access      = true
  cluster_endpoint_public_access       = true
  cluster_endpoint_public_access_cidrs = var.eks_public_access_cidrs

  cluster_encryption_config = {
    provider_key_arn = aws_kms_key.nexafi_primary.arn
    resources        = ["secrets"]
  }

  cluster_enabled_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler"
  ]

  cloudwatch_log_group_retention_in_days = 2555
  cloudwatch_log_group_kms_key_id        = aws_kms_key.nexafi_primary.arn

  cluster_security_group_additional_rules = {
    ingress_nodes_443 = {
      description                = "Node groups to cluster API"
      protocol                   = "tcp"
      from_port                  = 443
      to_port                    = 443
      type                       = "ingress"
      source_node_security_group = true
    }
    ingress_financial_8080 = {
      description = "Financial services communication"
      protocol    = "tcp"
      from_port   = 8080
      to_port     = 8090
      type        = "ingress"
      cidr_blocks = [var.vpc_cidr_primary]
    }
    ingress_vault = {
      description = "Vault communication"
      protocol    = "tcp"
      from_port   = 8200
      to_port     = 8201
      type        = "ingress"
      cidr_blocks = [var.vpc_cidr_primary]
    }
  }

  node_security_group_additional_rules = {
    ingress_self_all = {
      description = "Node to node all ports/protocols"
      protocol    = "-1"
      from_port   = 0
      to_port     = 0
      type        = "ingress"
      self        = true
    }
    egress_database = {
      description = "Database access"
      protocol    = "tcp"
      from_port   = 5432
      to_port     = 5432
      type        = "egress"
      cidr_blocks = module.vpc_primary.database_subnets_cidr_blocks
    }
    egress_redis = {
      description = "Redis access"
      protocol    = "tcp"
      from_port   = 6379
      to_port     = 6379
      type        = "egress"
      cidr_blocks = [var.vpc_cidr_primary]
    }
    egress_https = {
      description = "HTTPS outbound"
      protocol    = "tcp"
      from_port   = 443
      to_port     = 443
      type        = "egress"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }

  eks_managed_node_groups = {
    general = {
      name           = "general"
      instance_types = var.node_group_instance_types
      capacity_type  = "ON_DEMAND"

      min_size     = 2
      max_size     = 10
      desired_size = 3

      # Use pre_bootstrap_user_data instead of bootstrap_extra_args for managed node groups
      pre_bootstrap_user_data = <<-EOT
        #!/bin/bash
        /etc/eks/bootstrap.sh ${local.name_prefix}-primary \
          --container-runtime containerd \
          --kubelet-extra-args '--max-pods=110'
      EOT

      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 100
            volume_type           = "gp3"
            iops                  = 3000
            throughput            = 150
            encrypted             = true
            kms_key_id            = aws_kms_key.nexafi_primary.arn
            delete_on_termination = true
          }
        }
      }

      metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "required"
        http_put_response_hop_limit = 2
        instance_metadata_tags      = "enabled"
      }

      taints = {}
      labels = {
        Environment = var.environment
        NodeGroup   = "general"
        Purpose     = "general-workloads"
      }

      tags = merge(local.common_tags, {
        Name = "${local.name_prefix}-general-node-group"
        Type = "eks-node-group"
      })
    }

    financial_services = {
      name           = "financial-services"
      instance_types = var.financial_node_group_instance_types
      capacity_type  = "ON_DEMAND"

      min_size     = 3
      max_size     = 15
      desired_size = 5

      pre_bootstrap_user_data = <<-EOT
        #!/bin/bash
        /etc/eks/bootstrap.sh ${local.name_prefix}-primary \
          --container-runtime containerd \
          --kubelet-extra-args '--max-pods=110 --kube-reserved=cpu=250m,memory=1Gi,ephemeral-storage=1Gi --system-reserved=cpu=250m,memory=0.2Gi,ephemeral-storage=1Gi'
      EOT

      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 200
            volume_type           = "gp3"
            iops                  = 4000
            throughput            = 250
            encrypted             = true
            kms_key_id            = aws_kms_key.nexafi_primary.arn
            delete_on_termination = true
          }
        }
      }

      metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "required"
        http_put_response_hop_limit = 1
        instance_metadata_tags      = "enabled"
      }

      taints = {
        financial = {
          key    = "financial-services"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      }

      labels = {
        Environment = var.environment
        NodeGroup   = "financial-services"
        Purpose     = "financial-workloads"
        Compliance  = "PCI-DSS"
        Tier        = "financial"
      }

      tags = merge(local.common_tags, local.compliance_tags, {
        Name = "${local.name_prefix}-financial-services-node-group"
        Type = "eks-node-group"
        Tier = "financial"
      })
    }

    compliance_monitoring = {
      name           = "compliance-monitoring"
      instance_types = ["m5.large", "m5.xlarge"]
      capacity_type  = "ON_DEMAND"

      min_size     = 2
      max_size     = 8
      desired_size = 3

      pre_bootstrap_user_data = <<-EOT
        #!/bin/bash
        /etc/eks/bootstrap.sh ${local.name_prefix}-primary \
          --container-runtime containerd \
          --kubelet-extra-args '--max-pods=110'
      EOT

      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 150
            volume_type           = "gp3"
            iops                  = 3000
            throughput            = 200
            encrypted             = true
            kms_key_id            = aws_kms_key.nexafi_primary.arn
            delete_on_termination = true
          }
        }
      }

      metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "required"
        http_put_response_hop_limit = 2
        instance_metadata_tags      = "enabled"
      }

      taints = {
        compliance = {
          key    = "compliance-monitoring"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      }

      labels = {
        Environment = var.environment
        NodeGroup   = "compliance-monitoring"
        Purpose     = "compliance-workloads"
        Tier        = "compliance"
      }

      tags = merge(local.common_tags, local.compliance_tags, {
        Name = "${local.name_prefix}-compliance-monitoring-node-group"
        Type = "eks-node-group"
        Tier = "compliance"
      })
    }
  }

  fargate_profiles = {
    audit_logs = {
      name = "audit-logs"
      selectors = [
        {
          namespace = "compliance"
          labels    = { fargate = "audit-logs" }
        }
      ]
      subnet_ids = module.vpc_primary.private_subnets
      tags = merge(local.common_tags, {
        Name = "${local.name_prefix}-audit-logs-fargate"
        Type = "fargate-profile"
      })
    }
    security_services = {
      name = "security-services"
      selectors = [
        {
          namespace = "security"
          labels    = { fargate = "security-services" }
        }
      ]
      subnet_ids = module.vpc_primary.intra_subnets
      tags = merge(local.common_tags, {
        Name = "${local.name_prefix}-security-services-fargate"
        Type = "fargate-profile"
      })
    }
  }

  enable_irsa = true

  cluster_addons = {
    coredns = {
      most_recent = true
      configuration_values = jsonencode({
        computeType = "Fargate"
        resources = {
          limits   = { cpu = "0.25", memory = "256M" }
          requests = { cpu = "0.25", memory = "256M" }
        }
      })
    }
    kube-proxy = { most_recent = true }
    vpc-cni = {
      most_recent = true
      configuration_values = jsonencode({
        env = {
          ENABLE_POD_ENI                    = "true"
          ENABLE_PREFIX_DELEGATION          = "true"
          POD_SECURITY_GROUP_ENFORCING_MODE = "standard"
        }
      })
    }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa_role.iam_role_arn
    }
    aws-efs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.efs_csi_irsa_role.iam_role_arn
    }
  }

  tags = merge(local.common_tags, local.compliance_tags, {
    Name   = "${local.name_prefix}-primary-eks"
    Type   = "eks-cluster"
    Region = var.primary_region
  })
}

# Secondary EKS Cluster for disaster recovery
module "eks_secondary" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  providers = { aws = aws.secondary }

  cluster_name    = "${local.name_prefix}-secondary"
  cluster_version = var.eks_cluster_version

  vpc_id                   = module.vpc_secondary.vpc_id
  subnet_ids               = module.vpc_secondary.private_subnets
  control_plane_subnet_ids = module.vpc_secondary.intra_subnets

  cluster_endpoint_private_access      = true
  cluster_endpoint_public_access       = true
  cluster_endpoint_public_access_cidrs = var.eks_public_access_cidrs

  # Use secondary-region KMS key
  cluster_encryption_config = {
    provider_key_arn = aws_kms_key.nexafi_secondary.arn
    resources        = ["secrets"]
  }

  cluster_enabled_log_types              = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  cloudwatch_log_group_retention_in_days = 2555
  cloudwatch_log_group_kms_key_id        = aws_kms_key.nexafi_secondary.arn

  eks_managed_node_groups = {
    dr_standby = {
      name           = "dr-standby"
      instance_types = ["t3.medium"]
      capacity_type  = "ON_DEMAND"

      min_size     = 2
      max_size     = 10
      desired_size = 2

      block_device_mappings = {
        xvda = {
          device_name = "/dev/xvda"
          ebs = {
            volume_size           = 50
            volume_type           = "gp3"
            encrypted             = true
            kms_key_id            = aws_kms_key.nexafi_secondary.arn
            delete_on_termination = true
          }
        }
      }

      metadata_options = {
        http_endpoint               = "enabled"
        http_tokens                 = "required"
        http_put_response_hop_limit = 2
      }

      labels = {
        Environment = var.environment
        NodeGroup   = "dr-standby"
        Purpose     = "disaster-recovery"
      }

      tags = merge(local.common_tags, {
        Name    = "${local.name_prefix}-dr-standby-node-group"
        Type    = "eks-node-group"
        Purpose = "disaster-recovery"
      })
    }
  }

  enable_irsa = true

  cluster_addons = {
    coredns            = { most_recent = true }
    kube-proxy         = { most_recent = true }
    vpc-cni            = { most_recent = true }
    aws-ebs-csi-driver = { most_recent = true }
  }

  tags = merge(local.common_tags, {
    Name    = "${local.name_prefix}-secondary-eks"
    Type    = "eks-cluster"
    Region  = var.secondary_region
    Purpose = "disaster-recovery"
  })
}

# IRSA roles
module "ebs_csi_irsa_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name             = "${local.name_prefix}-ebs-csi"
  attach_ebs_csi_policy = true

  oidc_providers = {
    ex = {
      provider_arn               = module.eks_primary.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
  tags = merge(local.common_tags, { Name = "${local.name_prefix}-ebs-csi-irsa" })
}

module "efs_csi_irsa_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name             = "${local.name_prefix}-efs-csi"
  attach_efs_csi_policy = true

  oidc_providers = {
    ex = {
      provider_arn               = module.eks_primary.oidc_provider_arn
      namespace_service_accounts = ["kube-system:efs-csi-controller-sa"]
    }
  }
  tags = merge(local.common_tags, { Name = "${local.name_prefix}-efs-csi-irsa" })
}

module "load_balancer_controller_irsa_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name                              = "${local.name_prefix}-load-balancer-controller"
  attach_load_balancer_controller_policy = true

  oidc_providers = {
    ex = {
      provider_arn               = module.eks_primary.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }
  tags = merge(local.common_tags, { Name = "${local.name_prefix}-load-balancer-controller-irsa" })
}

module "external_dns_irsa_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name                     = "${local.name_prefix}-external-dns"
  attach_external_dns_policy    = true
  external_dns_hosted_zone_arns = ["arn:aws:route53:::hostedzone/*"]

  oidc_providers = {
    ex = {
      provider_arn               = module.eks_primary.oidc_provider_arn
      namespace_service_accounts = ["kube-system:external-dns"]
    }
  }
  tags = merge(local.common_tags, { Name = "${local.name_prefix}-external-dns-irsa" })
}

module "cluster_autoscaler_irsa_role" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name                        = "${local.name_prefix}-cluster-autoscaler"
  attach_cluster_autoscaler_policy = true
  cluster_autoscaler_cluster_names = [module.eks_primary.cluster_name]

  oidc_providers = {
    ex = {
      provider_arn               = module.eks_primary.oidc_provider_arn
      namespace_service_accounts = ["kube-system:cluster-autoscaler"]
    }
  }
  tags = merge(local.common_tags, { Name = "${local.name_prefix}-cluster-autoscaler-irsa" })
}

# EFS for shared storage
resource "aws_efs_file_system" "shared_storage" {
  creation_token                  = "${local.name_prefix}-shared-storage"
  performance_mode                = "generalPurpose"
  throughput_mode                 = "provisioned"
  provisioned_throughput_in_mibps = 100
  encrypted                       = true
  kms_key_id                      = aws_kms_key.nexafi_primary.arn

  lifecycle_policy { transition_to_ia = "AFTER_30_DAYS" }
  lifecycle_policy { transition_to_primary_storage_class = "AFTER_1_ACCESS" }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-shared-storage"
    Type = "efs"
  })
}

resource "aws_efs_mount_target" "shared_storage" {
  count           = length(module.vpc_primary.private_subnets)
  file_system_id  = aws_efs_file_system.shared_storage.id
  subnet_id       = module.vpc_primary.private_subnets[count.index]
  security_groups = [aws_security_group.efs.id]
}

resource "aws_security_group" "efs" {
  name_prefix = "${local.name_prefix}-efs-"
  vpc_id      = module.vpc_primary.vpc_id
  description = "Security group for EFS mount targets"

  ingress {
    from_port   = 2049
    to_port     = 2049
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr_primary]
    description = "NFS from VPC"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "All outbound traffic"
  }

  lifecycle { create_before_destroy = true }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-efs-sg"
    Type = "security-group"
  })
}
