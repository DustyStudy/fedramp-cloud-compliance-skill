# AWS implementation guide for FedRAMP

Starting points for implementation, not proof of compliance. AWS changes its service
authorizations and features often. **Before you assert that a service is authorized,
check the live list:** https://aws.amazon.com/compliance/services-in-scope/FedRAMP/

## Authorization posture and inheritance

- **AWS GovCloud (US-West `us-gov-west-1`, US-East `us-gov-east-1`)** is the usual choice
  for Rev5 Class D / former High and for ITAR/CJIS/DoD IL workloads. It uses a separate
  partition (`aws-us-gov`) with separate accounts, credentials, and ARNs.
- **Commercial US East/West regions** carry AWS's FedRAMP authorization for many services
  at a lower level than GovCloud. Confirm the per-service level on the services-in-scope
  page. Don't assume.
- **Get AWS's FedRAMP package and customer responsibility matrix** from **AWS Artifact**,
  or from the FedRAMP Marketplace. The CSP inherits PE, most of MA and MP, and the
  physical parts of SC/CP. It inherits nothing for its own IAM, configuration, logging,
  application security, or data.
- **Every AWS service in the boundary is a third-party information resource** under
  `MAS-CSO-TPR`. Record the services you use and their authorization status in the CPO.

## Cryptography (CMU ruleset, SC-8, SC-12, SC-13, SC-28)

- **FIPS endpoints:** set `use_fips_endpoint = true` in the Terraform `aws` provider, or
  set `AWS_USE_FIPS_ENDPOINT=true` for SDKs and the CLI. GovCloud and commercial US
  regions publish FIPS endpoints for most services. Some services have none (check the
  AWS FIPS endpoints page), and those gaps belong in the `CMU-CSO-CMD` module list.
- **KMS:** use customer-managed keys (CMKs) with `enable_key_rotation = true`. KMS HSMs
  are FIPS 140 validated, so cite the current CMVP certificate number from the AWS KMS
  docs rather than a level from memory. Use CloudHSM when you need dedicated key custody.
- **TLS on load balancers:** use FIPS security policies on ALB/NLB listeners, e.g.
  `ELBSecurityPolicy-TLS13-1-2-FIPS-2023-04`, and verify the current policy names. Use
  ACM certificates.
- **At rest:** encrypt S3 (SSE-KMS plus a bucket key), EBS (account-level
  `aws_ebs_encryption_by_default`), RDS/Aurora, DynamoDB, EFS, SQS/SNS, CloudWatch Logs,
  and Secrets Manager, all with CMKs.
- **Your own code:** it needs a validated module, e.g. OpenSSL 3 FIPS provider, AWS-LC
  FIPS, BoringCrypto, or Go's FIPS mode. Record which one in the module list. On EC2 or
  containers, use FIPS-enabled OS images such as Amazon Linux 2023 with FIPS mode, or
  Bottlerocket FIPS variants.

## Control family → AWS services

| Family | Primary AWS mechanisms | Customer must still… |
|---|---|---|
| AC (access) | IAM Identity Center; IAM roles; Organizations SCPs and resource control policies (RCPs); permission boundaries; IAM Access Analyzer (external + unused access); S3 Block Public Access (account + org) | Define roles, review access, enforce least privilege, disable unused identities (AC-2, AC-6) |
| AU (audit) | Organization CloudTrail (all regions, log file validation, KMS, data events where needed); CloudWatch Logs; S3 Object Lock for log archives; Security Lake / SIEM integration; VPC Flow Logs; ALB/WAF/Route 53 Resolver query logs | Choose event types (AU-2), review logs (AU-6), set retention, protect log access (AU-9) |
| CA / CM (assessment, config) | AWS Config (all resources, org aggregator) + conformance packs `Operational-Best-Practices-for-FedRAMP-Low/-Moderate/-HighPart1/-HighPart2`, `…-for-NIST-800-53-rev-5`; Security Hub **NIST SP 800-53 Rev. 5** standard (`standards/nist-800-53/v/5.0.0`); Control Tower controls; Systems Manager State Manager / Inventory | Baselines (CM-2/6), change control (CM-3), inventory accuracy (CM-8), and remediation workflow |
| CP (contingency) | AWS Backup (org backup policies, Vault Lock, cross-region/cross-account copies); multi-AZ; Elastic Disaster Recovery; Route 53 health checks | Set RTO/RPO, *test* restores (CP-4, CP-9, KSI-RPL-TRC) |
| IA (identification) | Identity Center with external IdP and **phishing-resistant MFA** (FIDO2/passkeys, PIV/CAC), required by FedRAMP guidance on IA-2(1)/(2); IAM Roles Anywhere; no IAM users or long-lived access keys; root MFA via hardware key | Enforce MFA strength at the IdP, manage authenticators (IA-5), handle non-user identities (KSI-IAM-SNU) |
| IR (incident) | GuardDuty (org, all protection plans in use); Security Hub findings aggregation; Detective; EventBridge → SNS/ticketing; SSM Incident Manager | IR plan, PAIN rating, and FedRAMP reporting timelines (IEC ruleset); after-action reviews |
| RA / SI (vuln, integrity) | Amazon Inspector (EC2, ECR, Lambda; SBOM export); ECR enhanced scanning; SSM Patch Manager; GuardDuty Malware Protection; CloudTrail log integrity; Macie (sensitive data discovery) | Evaluate each vuln (VER-EVA-*), meet VDR timeframes, handle KEVs (`VDR-TFR-KEV`) |
| SC (boundary, crypto) | VPC design with private subnets; security groups; Network Firewall; WAF; Shield Advanced; PrivateLink / VPC endpoints (FIPS); KMS; ACM; Route 53 Resolver DNS Firewall | Deny-by-default flows (SC-7), boundary docs, crypto module list (CMU) |
| SR (supply chain) | ECR with image signing (AWS Signer / Notation); CodeArtifact; Inspector SBOMs | Vendor risk process, provenance verification |
| PE / MA / MP | Inherited from AWS for the infrastructure layer | Your own endpoints/media, if any are in scope |

## KSI measure ideas (20x)

| KSI | Example AWS measure (persistent, machine-generated) |
|---|---|
| CNA-RNT / CNA-MAT | Config rules for restricted SGs, no public IPs/IGW routes on private tiers; Security Hub controls EC2.2/EC2.18/EC2.19 pass rate |
| CNA-EIS / SVC-ACM | Config conformance pack compliance %; drift remediation via SSM Automation; Terraform plan-drift job output |
| IAM-APM / IAM-ELP / IAM-JIT | IdP MFA-policy export; Access Analyzer unused-access findings trend; time-bound Identity Center assignments (e.g. via TEAM) |
| IAM-SNU | Count of IAM users/access keys (target 0); role trust policies scoped with conditions |
| MLA-OSM / MLA-LET / MLA-RVL | CloudTrail org-trail status + Security Lake/SIEM ingest health; alert → ticket SLAs |
| MLA-EVC | Security Hub NIST 800-53 standard score over time |
| SVC-SIN / SVC-VCM | Config rules for encryption at rest, FIPS/TLS listener policies, `s3-bucket-ssl-requests-only` |
| RPL-ABO / RPL-TRC | AWS Backup job success + restore-testing results (AWS Backup restore testing) |
| PIY-GIV | AWS Config advanced query / Resource Explorer inventory export |
| SCR-MON | Inspector SBOM + ECR scan results for third-party dependencies |

## Terraform specifics

```hcl
provider "aws" {
  region            = "us-gov-west-1"   # or a commercial US region if the service authorization allows
  use_fips_endpoint = true
  default_tags { tags = { "fedramp:boundary" = "in" } }
}

data "aws_partition" "current" {}      # never hard-code "arn:aws:"; GovCloud is "aws-us-gov"
```

- Enable the Security Hub standard with
  `standards_arn = "arn:${data.aws_partition.current.partition}:securityhub:${var.region}::standards/nist-800-53/v/5.0.0"`.
- Deploy conformance packs from AWS's templates, and pin a reviewed copy in your repo so
  that changes go through CM-3.
- The user's `fedramp-terraform-library` repo has reusable modules for many of these
  patterns: org CloudTrail, GuardDuty, Security Hub, the Config conformance pack, and FIPS
  VPC endpoints.

## Common AWS findings (feed into terraform-checks.md)

- `aws_s3_bucket` without a public access block, SSE-KMS, or a TLS-only bucket policy.
- `aws_security_group` ingress from `0.0.0.0/0` / `::/0` on admin ports.
- CloudTrail missing `is_multi_region_trail`, `enable_log_file_validation`, or `kms_key_id`.
- `aws_iam_policy` with `"Action": "*"` / `"Resource": "*"`. IAM users with access keys.
- `aws_db_instance` without `storage_encrypted`, `iam_database_authentication_enabled`,
  or `deletion_protection`, or with `publicly_accessible = true`.
- `aws_lb_listener` without a FIPS/TLS 1.2+ `ssl_policy`. HTTP listeners without a redirect.
- EKS: public endpoint open to 0.0.0.0/0, no control-plane logging, or no secrets
  envelope encryption.
- Logs without retention or KMS (`aws_cloudwatch_log_group`).
