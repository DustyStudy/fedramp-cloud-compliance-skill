# AWS implementation guide for FedRAMP

Starting points for implementation, not proof of compliance. AWS changes its service
authorizations and features often. **Before you assert that a service is authorized,
check the live list:** https://aws.amazon.com/compliance/services-in-scope/FedRAMP/

## Authorization posture and inheritance

- **AWS GovCloud (US-West `us-gov-west-1`, US-East `us-gov-east-1`)** is the usual choice
  (guidance) for Rev5 Class D / former High and for ITAR/CJIS/DoD IL workloads. It uses a separate
  partition (`aws-us-gov`) with separate accounts, credentials, and ARNs.
- **Commercial US East/West regions** are listed on AWS's services-in-scope page as
  "FedRAMP Class C (formerly Moderate)", and GovCloud as "Class D (formerly High)". The
  level is per service, so confirm each one on the services-in-scope page. For example,
  Macie is listed for East/West but not GovCloud (as of 2026-09).
- **Get AWS's FedRAMP package and customer responsibility matrix** from **AWS Artifact**,
  or from the FedRAMP Marketplace. The CSP inherits the physical and
  environmental (PE) controls. For how other families split between AWS and the
  customer, use the CRM in AWS's package. The CSP inherits nothing for its own IAM,
  configuration, logging, application security, or data.
- **AWS services as third-party information resources:** when `MAS-CSO-IIR` applies,
  `MAS-CSO-TPR` covers the third-party resources likely to handle federal customer data,
  or to affect its confidentiality, integrity, or availability. For each one, document
  usage and configuration, justification, mitigations, and compensating controls.
  Recording each service's FedRAMP status is useful context, but the rule doesn't
  require it.

## Cryptography (CMU ruleset, SC-8, SC-12, SC-13, SC-28)

- **FIPS endpoints:** set `use_fips_endpoint = true` in the Terraform `aws` provider, or
  set `AWS_USE_FIPS_ENDPOINT=true` for SDKs and the CLI. GovCloud and commercial US
  regions publish FIPS endpoints for many services, but not all. Check each service on the
  AWS FIPS endpoints page (https://aws.amazon.com/compliance/fips/). Services without one
  belong in the `CMU-CSO-CMD` module list.
- **KMS:** use customer-managed keys (CMKs) with `enable_key_rotation = true`. The KMS
  HSM holds CMVP #4884 (FIPS 140-3, Overall Level 3, active). Checked on 2026-09-23, it is
  an **interim validation with a sunset date of 2026-11-17**, and it was the only active
  KMS certificate. Re-check csrc.nist.gov before you cite it in a `CMU-CSO-CMD` module
  list. Use CloudHSM when you need dedicated key custody.
- **TLS on load balancers:** use FIPS security policies on ALB/NLB listeners, e.g.
  `ELBSecurityPolicy-TLS13-1-2-FIPS-2023-04` or the newer post-quantum `…-FIPS-PQ-2025-09`
  variants, and verify the current policy names. Use
  ACM certificates.
- **At rest:** encrypt S3, EBS, RDS/Aurora, DynamoDB, EFS, SQS/SNS, CloudWatch Logs, and
  Secrets Manager, all with CMKs:
  - S3: SSE-KMS plus a bucket key, via `aws_s3_bucket_server_side_encryption_configuration`
    with `bucket_key_enabled = true`.
  - EBS: account-level `aws_ebs_encryption_by_default`. On its own this uses the
    AWS-managed key, so add `aws_ebs_default_kms_key` to use a CMK.
- **Your own code:** it needs a validated module, e.g. OpenSSL 3 FIPS provider, AWS-LC
  FIPS, BoringCrypto, or Go's FIPS mode. Record which one in the module list. On EC2 or
  containers, use FIPS-enabled OS images such as Amazon Linux 2023 with FIPS mode, or
  Bottlerocket FIPS variants.

## Control family → AWS services

| Family | Primary AWS mechanisms | Customer must still… |
|---|---|---|
| AC (access) | IAM Identity Center; IAM roles; Organizations SCPs and resource control policies (RCPs); permission boundaries; IAM Access Analyzer (external + unused access); S3 Block Public Access (account + org) | Define roles, review access, enforce least privilege, disable unused identities (AC-2, AC-6) |
| AU (audit) | Organization CloudTrail (all regions, log file validation, KMS, data events where needed); CloudWatch Logs; S3 Object Lock for log archives; Security Lake / SIEM integration; VPC Flow Logs; ALB/WAF/VPC Resolver (formerly Route 53 Resolver) query logs | Choose event types (AU-2), review logs (AU-6), set retention, protect log access (AU-9) |
| CA / CM (assessment, config) | AWS Config (all resources, org aggregator) + conformance packs `Operational-Best-Practices-for-FedRAMP-Low/-Moderate/-HighPart1/-HighPart2`, `…-for-NIST-800-53-rev-5`; Security Hub CSPM **NIST SP 800-53 Rev. 5** standard (`standards/nist-800-53/v/5.0.0`); Control Tower controls; Systems Manager State Manager / Inventory | Baselines (CM-2/6), change control (CM-3), inventory accuracy (CM-8), and remediation workflow |
| CP (contingency) | AWS Backup (org backup policies, Vault Lock, cross-region/cross-account copies); multi-AZ; Elastic Disaster Recovery; Route 53 health checks | Set RTO/RPO, *test* restores (CP-4, CP-9, KSI-RPL-TRC) |
| IA (identification) | Identity Center with external IdP and **phishing-resistant MFA** (FIDO2/passkeys, PIV/CAC), required by FedRAMP guidance on IA-2(1)/(2); IAM Roles Anywhere; no IAM users or long-lived access keys; root MFA via hardware key | Enforce MFA strength at the IdP, manage authenticators (IA-5), handle non-user identities (KSI-IAM-SNU) |
| IR (incident) | GuardDuty (org, all protection plans in use); Security Hub / Security Hub CSPM findings aggregation; Detective; EventBridge → SNS/ticketing or on-call tooling; AWS Security Incident Response (East/West only on the FedRAMP scope page). SSM Incident Manager closed to new customers on 2025-11-07, so don't design new processes around it | IR plan, PAIN rating, and FedRAMP reporting timelines (IEC ruleset); after-action reviews |
| RA / SI (vuln, integrity) | Amazon Inspector (EC2, ECR, Lambda; SBOM export); ECR enhanced scanning; SSM Patch Manager; GuardDuty Malware Protection; CloudTrail log integrity; Macie (sensitive data discovery; not listed for GovCloud as of 2026-09) | Evaluate each vuln (VER-EVA-*), meet VDR timeframes, handle KEVs (`VDR-TFR-KEV`) |
| SC (boundary, crypto) | VPC design with private subnets; security groups; Network Firewall; WAF; Shield Advanced (East/West only on the FedRAMP scope page); PrivateLink / VPC endpoints (FIPS); KMS; ACM; Route 53 Resolver DNS Firewall | Deny-by-default flows (SC-7), boundary docs, crypto module list (CMU) |
| SR (supply chain) | ECR with image signing (AWS Signer / Notation); Inspector SBOMs. CodeArtifact is not on the FedRAMP services-in-scope page | Vendor risk process, provenance verification |
| PE / MA / MP | Inherited from AWS for the infrastructure layer | Your own endpoints/media, if any are in scope |

## KSI measure ideas (20x)

> _Guidance:_ these are suggested measures, not FedRAMP requirements. FedRAMP defines the KSI outcomes (`generated/ksi.md`); you choose the measures.

| KSI | Example AWS measure (persistent, machine-generated) |
|---|---|
| CNA-RNT / CNA-MAT | Config rules for restricted SGs, no public IPs/IGW routes on private tiers; Security Hub CSPM controls EC2.2/EC2.18/EC2.19 pass rate |
| CNA-EIS / SVC-ACM | Config conformance pack compliance %; drift remediation via SSM Automation; Terraform plan-drift job output |
| IAM-APM / IAM-ELP / IAM-JIT | IdP MFA-policy export; Access Analyzer unused-access findings trend; time-bound Identity Center assignments (e.g. via TEAM, the open-source aws-samples Temporary Elevated Access Management solution. TEAM is not an AWS managed service, so it runs inside your boundary) |
| IAM-SNU | Count of IAM users/access keys (target 0); role trust policies scoped with conditions |
| MLA-OSM / MLA-LET / MLA-RVL | CloudTrail org-trail status + Security Lake/SIEM ingest health; alert → ticket SLAs |
| MLA-EVC | Security Hub CSPM NIST 800-53 standard score over time |
| SVC-SIN / SVC-VCM | Config rules for encryption at rest, FIPS/TLS listener policies, `s3-bucket-ssl-requests-only` |
| RPL-ABO / RPL-TRC | AWS Backup job success + restore-testing results (AWS Backup restore testing) |
| PIY-GIV | AWS Config advanced query / Resource Explorer inventory export |
| SCR-MON | Inspector SBOM + ECR scan results for third-party dependencies |

## Terraform specifics

```hcl
provider "aws" {
  region            = "us-gov-west-1" # or a commercial US region if the service authorization allows
  use_fips_endpoint = true
  default_tags { tags = { "fedramp:boundary" = "in" } }
}

data "aws_partition" "current" {} # never hard-code "arn:aws:"; GovCloud is "aws-us-gov"
```

- **Naming:** in June 2025 AWS renamed the original Security Hub to **Security Hub CSPM**,
  and a new, OCSF-based "AWS Security Hub" became generally available on 2025-12-02. The
  NIST 800-53 standard and its control IDs belong to Security Hub CSPM. In Terraform, the
  classic `aws_securityhub_*` resources manage Security Hub CSPM, and the `_v2` resources
  (e.g. `aws_securityhub_account_v2`, 6.43.0+) manage the new service. As of 2026-09, only
  Security Hub CSPM appears on AWS's FedRAMP services-in-scope page.
- Enable the Security Hub CSPM standard with
  `standards_arn = "arn:${data.aws_partition.current.partition}:securityhub:${var.region}::standards/nist-800-53/v/5.0.0"`.
- Deploy conformance packs from AWS's templates, and pin a reviewed copy in your repo so
  that changes go through CM-3. The FedRAMP templates are close to the 51,200-byte
  `template_body` limit (Moderate is about 50.6 KB), so upload the reviewed copy to S3 and
  use `template_s3_uri` instead. For multi-account deployments, use
  `aws_config_organization_conformance_pack`.
- [fedramp-terraform-library](https://github.com/DustyStudy/fedramp-terraform-library) has
  reusable modules for many of these patterns: org CloudTrail, GuardDuty, Security Hub,
  the Config conformance pack, and FIPS VPC endpoints.
- These examples target `hashicorp/aws` v6. In v6, `data.aws_region.name` is deprecated in
  favour of `.region`, and `aws_partition.id` in favour of `.partition`.

## Common AWS findings (feed into terraform-checks.md)

- S3 buckets without an `aws_s3_bucket_public_access_block` (all four settings true),
  `aws_s3_bucket_server_side_encryption_configuration` (SSE-KMS, `bucket_key_enabled`), or
  a TLS-only `aws_s3_bucket_policy` (deny when `aws:SecureTransport` is false). Since
  provider v4 these are separate resources, and the inline `aws_s3_bucket` arguments are
  deprecated.
- `aws_security_group` ingress from `0.0.0.0/0` / `::/0` on admin ports.
- CloudTrail missing `is_multi_region_trail`, `enable_log_file_validation`, or `kms_key_id`.
- `aws_iam_policy` with `"Action": "*"` / `"Resource": "*"`. IAM users with access keys.
- `aws_db_instance` / `aws_rds_cluster` (Aurora) without `storage_encrypted` (plus
  `kms_key_id` for a CMK), `iam_database_authentication_enabled`, or
  `deletion_protection`, or an instance with `publicly_accessible = true`.
- `aws_lb_listener` without a FIPS/TLS 1.2+ `ssl_policy`. HTTP listeners without a redirect.
- EKS: public endpoint open to 0.0.0.0/0 (`vpc_config.public_access_cidrs`), no
  control-plane logging (`enabled_cluster_log_types`), or no customer-managed key in
  `encryption_config`. On Kubernetes 1.28+, EKS envelope-encrypts API data by default
  with an AWS-owned key, so the finding is about key custody, not missing encryption.
- Logs without retention or KMS (`aws_cloudwatch_log_group`).
