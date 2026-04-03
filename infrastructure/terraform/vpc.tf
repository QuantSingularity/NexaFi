# Enhanced VPC configuration for NexaFi with financial industry security standards

# Secondary region AZ data source - requires provider alias
data "aws_availability_zones" "secondary" {
  provider = aws.secondary
  state    = "available"
}

# Primary VPC
module "vpc_primary" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "${local.name_prefix}-primary-vpc"
  cidr = var.vpc_cidr_primary

  azs = slice(data.aws_availability_zones.available.names, 0, 3)

  private_subnets = [
    cidrsubnet(var.vpc_cidr_primary, 4, 1),
    cidrsubnet(var.vpc_cidr_primary, 4, 2),
    cidrsubnet(var.vpc_cidr_primary, 4, 3),
  ]

  public_subnets = [
    cidrsubnet(var.vpc_cidr_primary, 8, 1),
    cidrsubnet(var.vpc_cidr_primary, 8, 2),
    cidrsubnet(var.vpc_cidr_primary, 8, 3),
  ]

  database_subnets = [
    cidrsubnet(var.vpc_cidr_primary, 6, 16),
    cidrsubnet(var.vpc_cidr_primary, 6, 17),
    cidrsubnet(var.vpc_cidr_primary, 6, 18),
  ]

  intra_subnets = [
    cidrsubnet(var.vpc_cidr_primary, 6, 20),
    cidrsubnet(var.vpc_cidr_primary, 6, 21),
    cidrsubnet(var.vpc_cidr_primary, 6, 22),
  ]

  enable_nat_gateway   = var.enable_nat_gateway
  single_nat_gateway   = false
  one_nat_gateway_per_az = true
  enable_vpn_gateway   = var.enable_vpn_gateway
  enable_dns_hostnames = true
  enable_dns_support   = true

  enable_flow_log                                 = true
  create_flow_log_cloudwatch_iam_role             = true
  create_flow_log_cloudwatch_log_group            = true
  flow_log_destination_type                       = "cloud-watch-logs"
  flow_log_cloudwatch_log_group_retention_in_days = 2555
  flow_log_cloudwatch_log_group_kms_key_id        = aws_kms_key.nexafi_primary.arn
  flow_log_traffic_type                           = "ALL"
  flow_log_log_format                             = "$${version} $${account-id} $${interface-id} $${srcaddr} $${dstaddr} $${srcport} $${dstport} $${protocol} $${packets} $${bytes} $${windowstart} $${windowend} $${action} $${flowlogstatus} $${vpc-id} $${subnet-id} $${instance-id} $${tcp-flags} $${type} $${pkt-srcaddr} $${pkt-dstaddr} $${region} $${az-id} $${sublocation-type} $${sublocation-id}"

  manage_default_network_acl = true
  default_network_acl_tags = {
    Name = "${local.name_prefix}-primary-default-nacl"
  }

  manage_default_security_group  = true
  default_security_group_ingress = []
  default_security_group_egress  = []
  default_security_group_tags = {
    Name = "${local.name_prefix}-primary-default-sg"
  }

  public_subnet_tags = {
    "kubernetes.io/role/elb"                             = "1"
    "kubernetes.io/cluster/${local.name_prefix}-primary" = "shared"
    Tier                                                 = "public"
    SecurityZone                                         = "dmz"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"                    = "1"
    "kubernetes.io/cluster/${local.name_prefix}-primary" = "shared"
    Tier                                                 = "private"
    SecurityZone                                         = "application"
  }

  database_subnet_tags = {
    Tier               = "database"
    SecurityZone       = "data"
    BackupRequired     = "true"
    EncryptionRequired = "true"
  }

  intra_subnet_tags = {
    Tier         = "security"
    SecurityZone = "security"
    Purpose      = "security-services"
  }

  tags = merge(local.common_tags, local.compliance_tags, {
    Name   = "${local.name_prefix}-primary-vpc"
    Region = var.primary_region
    Type   = "primary"
  })
}

# Secondary VPC for disaster recovery
module "vpc_secondary" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  providers = {
    aws = aws.secondary
  }

  name = "${local.name_prefix}-secondary-vpc"
  cidr = var.vpc_cidr_secondary

  # Use secondary-region-specific AZ data source
  azs = slice(data.aws_availability_zones.secondary.names, 0, 3)

  private_subnets = [
    cidrsubnet(var.vpc_cidr_secondary, 4, 1),
    cidrsubnet(var.vpc_cidr_secondary, 4, 2),
    cidrsubnet(var.vpc_cidr_secondary, 4, 3),
  ]

  public_subnets = [
    cidrsubnet(var.vpc_cidr_secondary, 8, 1),
    cidrsubnet(var.vpc_cidr_secondary, 8, 2),
    cidrsubnet(var.vpc_cidr_secondary, 8, 3),
  ]

  database_subnets = [
    cidrsubnet(var.vpc_cidr_secondary, 6, 16),
    cidrsubnet(var.vpc_cidr_secondary, 6, 17),
    cidrsubnet(var.vpc_cidr_secondary, 6, 18),
  ]

  intra_subnets = [
    cidrsubnet(var.vpc_cidr_secondary, 6, 20),
    cidrsubnet(var.vpc_cidr_secondary, 6, 21),
    cidrsubnet(var.vpc_cidr_secondary, 6, 22),
  ]

  enable_nat_gateway   = var.enable_nat_gateway
  single_nat_gateway   = true
  enable_vpn_gateway   = var.enable_vpn_gateway
  enable_dns_hostnames = true
  enable_dns_support   = true

  enable_flow_log                                 = true
  create_flow_log_cloudwatch_iam_role             = true
  create_flow_log_cloudwatch_log_group            = true
  flow_log_destination_type                       = "cloud-watch-logs"
  flow_log_cloudwatch_log_group_retention_in_days = 2555

  manage_default_security_group  = true
  default_security_group_ingress = []
  default_security_group_egress  = []

  public_subnet_tags = {
    "kubernetes.io/role/elb"                               = "1"
    "kubernetes.io/cluster/${local.name_prefix}-secondary" = "shared"
    Tier                                                   = "public"
    SecurityZone                                           = "dmz"
  }

  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"                      = "1"
    "kubernetes.io/cluster/${local.name_prefix}-secondary" = "shared"
    Tier                                                   = "private"
    SecurityZone                                           = "application"
  }

  database_subnet_tags = {
    Tier               = "database"
    SecurityZone       = "data"
    BackupRequired     = "true"
    EncryptionRequired = "true"
  }

  intra_subnet_tags = {
    Tier         = "security"
    SecurityZone = "security"
    Purpose      = "security-services"
  }

  tags = merge(local.common_tags, local.compliance_tags, {
    Name   = "${local.name_prefix}-secondary-vpc"
    Region = var.secondary_region
    Type   = "disaster-recovery"
  })
}

# VPC Peering between primary and secondary regions
resource "aws_vpc_peering_connection" "primary_to_secondary" {
  vpc_id      = module.vpc_primary.vpc_id
  peer_vpc_id = module.vpc_secondary.vpc_id
  peer_region = var.secondary_region
  auto_accept = false

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-primary-to-secondary-peering"
    Type = "vpc-peering"
  })
}

resource "aws_vpc_peering_connection_accepter" "secondary" {
  provider = aws.secondary

  vpc_peering_connection_id = aws_vpc_peering_connection.primary_to_secondary.id
  auto_accept               = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-secondary-peering-accepter"
    Type = "vpc-peering"
  })
}

resource "aws_route" "primary_to_secondary" {
  count = length(module.vpc_primary.private_route_table_ids)

  route_table_id            = module.vpc_primary.private_route_table_ids[count.index]
  destination_cidr_block    = var.vpc_cidr_secondary
  vpc_peering_connection_id = aws_vpc_peering_connection.primary_to_secondary.id
}

resource "aws_route" "secondary_to_primary" {
  provider = aws.secondary
  count    = length(module.vpc_secondary.private_route_table_ids)

  route_table_id            = module.vpc_secondary.private_route_table_ids[count.index]
  destination_cidr_block    = var.vpc_cidr_primary
  vpc_peering_connection_id = aws_vpc_peering_connection.primary_to_secondary.id
}

# Enhanced Network ACLs for financial services
resource "aws_network_acl" "financial_services" {
  vpc_id     = module.vpc_primary.vpc_id
  subnet_ids = module.vpc_primary.private_subnets

  ingress {
    protocol   = "tcp"
    rule_no    = 100
    action     = "allow"
    cidr_block = var.vpc_cidr_primary
    from_port  = 443
    to_port    = 443
  }

  ingress {
    protocol   = "tcp"
    rule_no    = 110
    action     = "allow"
    cidr_block = var.vpc_cidr_primary
    from_port  = 8080
    to_port    = 8090
  }

  ingress {
    protocol   = "tcp"
    rule_no    = 120
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 1024
    to_port    = 65535
  }

  egress {
    protocol   = "tcp"
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 443
    to_port    = 443
  }

  egress {
    protocol   = "tcp"
    rule_no    = 110
    action     = "allow"
    cidr_block = var.vpc_cidr_primary
    from_port  = 5432
    to_port    = 5432
  }

  egress {
    protocol   = "tcp"
    rule_no    = 120
    action     = "allow"
    cidr_block = var.vpc_cidr_primary
    from_port  = 6379
    to_port    = 6379
  }

  egress {
    protocol   = "tcp"
    rule_no    = 130
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 1024
    to_port    = 65535
  }

  tags = merge(local.common_tags, {
    Name         = "${local.name_prefix}-financial-services-nacl"
    Type         = "network-acl"
    SecurityZone = "application"
  })
}

resource "aws_network_acl" "database" {
  vpc_id     = module.vpc_primary.vpc_id
  subnet_ids = module.vpc_primary.database_subnets

  ingress {
    protocol   = "tcp"
    rule_no    = 100
    action     = "allow"
    cidr_block = cidrsubnet(var.vpc_cidr_primary, 4, 1)
    from_port  = 5432
    to_port    = 5432
  }

  ingress {
    protocol   = "tcp"
    rule_no    = 110
    action     = "allow"
    cidr_block = cidrsubnet(var.vpc_cidr_primary, 4, 2)
    from_port  = 5432
    to_port    = 5432
  }

  ingress {
    protocol   = "tcp"
    rule_no    = 120
    action     = "allow"
    cidr_block = cidrsubnet(var.vpc_cidr_primary, 4, 3)
    from_port  = 5432
    to_port    = 5432
  }

  ingress {
    protocol   = "tcp"
    rule_no    = 130
    action     = "allow"
    cidr_block = cidrsubnet(var.vpc_cidr_primary, 4, 1)
    from_port  = 3306
    to_port    = 3306
  }

  ingress {
    protocol   = "tcp"
    rule_no    = 200
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 1024
    to_port    = 65535
  }

  egress {
    protocol   = "tcp"
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 1024
    to_port    = 65535
  }

  tags = merge(local.common_tags, {
    Name         = "${local.name_prefix}-database-nacl"
    Type         = "network-acl"
    SecurityZone = "data"
  })
}

resource "aws_network_acl" "security_services" {
  vpc_id     = module.vpc_primary.vpc_id
  subnet_ids = module.vpc_primary.intra_subnets

  ingress {
    protocol   = "tcp"
    rule_no    = 100
    action     = "allow"
    cidr_block = var.vpc_cidr_primary
    from_port  = 8200
    to_port    = 8201
  }

  ingress {
    protocol   = "tcp"
    rule_no    = 110
    action     = "allow"
    cidr_block = var.vpc_cidr_primary
    from_port  = 8080
    to_port    = 8080
  }

  ingress {
    protocol   = "tcp"
    rule_no    = 200
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 1024
    to_port    = 65535
  }

  egress {
    protocol   = "tcp"
    rule_no    = 100
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 443
    to_port    = 443
  }

  egress {
    protocol   = "tcp"
    rule_no    = 110
    action     = "allow"
    cidr_block = var.vpc_cidr_primary
    from_port  = 5432
    to_port    = 5432
  }

  egress {
    protocol   = "tcp"
    rule_no    = 120
    action     = "allow"
    cidr_block = "0.0.0.0/0"
    from_port  = 1024
    to_port    = 65535
  }

  tags = merge(local.common_tags, {
    Name         = "${local.name_prefix}-security-services-nacl"
    Type         = "network-acl"
    SecurityZone = "security"
  })
}

# VPC Endpoints for secure AWS service access
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = module.vpc_primary.vpc_id
  service_name      = "com.amazonaws.${var.primary_region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = module.vpc_primary.private_route_table_ids

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = "*"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::nexafi-*",
          "arn:aws:s3:::nexafi-*/*"
        ]
      }
    ]
  })

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-s3-endpoint"
    Type = "vpc-endpoint"
  })
}

resource "aws_vpc_endpoint" "ec2" {
  vpc_id              = module.vpc_primary.vpc_id
  service_name        = "com.amazonaws.${var.primary_region}.ec2"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc_primary.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-ec2-endpoint"
    Type = "vpc-endpoint"
  })
}

resource "aws_vpc_endpoint" "ecr_api" {
  vpc_id              = module.vpc_primary.vpc_id
  service_name        = "com.amazonaws.${var.primary_region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc_primary.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-ecr-api-endpoint"
    Type = "vpc-endpoint"
  })
}

resource "aws_vpc_endpoint" "ecr_dkr" {
  vpc_id              = module.vpc_primary.vpc_id
  service_name        = "com.amazonaws.${var.primary_region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc_primary.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-ecr-dkr-endpoint"
    Type = "vpc-endpoint"
  })
}

resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = module.vpc_primary.vpc_id
  service_name        = "com.amazonaws.${var.primary_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc_primary.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-secretsmanager-endpoint"
    Type = "vpc-endpoint"
  })
}

resource "aws_vpc_endpoint" "ssm" {
  vpc_id              = module.vpc_primary.vpc_id
  service_name        = "com.amazonaws.${var.primary_region}.ssm"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = module.vpc_primary.private_subnets
  security_group_ids  = [aws_security_group.vpc_endpoints.id]
  private_dns_enabled = true

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-ssm-endpoint"
    Type = "vpc-endpoint"
  })
}

resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "${local.name_prefix}-vpc-endpoints-"
  vpc_id      = module.vpc_primary.vpc_id
  description = "Security group for VPC endpoints"

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr_primary]
    description = "HTTPS from VPC"
  }

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS outbound"
  }

  lifecycle {
    create_before_destroy = true
  }

  tags = merge(local.common_tags, {
    Name = "${local.name_prefix}-vpc-endpoints-sg"
    Type = "security-group"
  })
}
