# Terraform / IaC review checklist for FedRAMP

Use this for reviewing a plan, module, or PR. Report each finding as:

```
[SEVERITY] path/file.tf:LINE — resource.address
Problem: <what is wrong, concretely>
Fix: <attribute/value or code change>
Maps to: <800-53 control(s)> · <KSI(s)> · <rule ID(s) if any>
Reachability: internet-reachable yes/no/unknown · likely exploitable yes/no/unknown — <one-line basis, or the evidence needed>
Deployed: yes/no/unknown — <how you know: state file, plan, account query, user said>
```

The reachability line is an *initial estimate* for triage, not the formal `VER-EVA-EIR` /
`VER-EVA-ELX` evaluation. Private addressing alone doesn't make something not
internet-reachable: a payload can arrive through a load balancer, queue, or upload.

Severity guide (_guidance_: FedRAMP defines no IaC severity scale, so adjust it to your program's risk methodology):
- **Critical:** public exposure of data or admin surfaces, or no encryption for federal
  customer data; CI jobs that run untrusted code with deploy credentials.
- **High:** missing audit logging, wildcard IAM, long-lived credentials, or non-validated
  crypto for Class D (`CMU-CSO-UVM` MUST).
- **Medium:** non-validated crypto for Class C (SHOULD: acceptable only with a documented
  decision in the SDR).
- **Medium:** weak retention, missing drift/inventory tooling, missing tags for boundary
  scoping.
- **Low:** hygiene.

Before reviewing, establish the **type/class**, the **cloud and partition** (GovCloud,
Azure Government, Assured Workloads regime), and whether the resources are **in the
boundary** (`MAS-CSO-IIR`). Crypto expectations depend on class: `CMU-CSO-UVM` says
validated modules are MAY for A/B, SHOULD for C, and MUST for D.

## 1. Boundary and inventory (CM-8, PL-2, SA-9(5), MAS, KSI-PIY-GIV)
- [ ] In-boundary resources are identifiable, e.g. by a consistent tag/label such as
      `fedramp:boundary=in`, provider `default_tags`, or an Azure Policy or GCP org policy
      that requires it.
- [ ] The resources are in a government partition or regime where the class requires one:
      AWS `aws-us-gov` partition, azurerm `environment = "usgovernment"`, or GCP projects
      under an Assured Workloads folder.
- [ ] Regions are restricted: AWS SCP on `aws:RequestedRegion`, Azure "Allowed locations"
      policy, GCP `gcp.resourceLocations`.
- [ ] Each AWS provider block names the account it may touch: `allowed_account_ids =
      [var.account_id]` (Azure: `subscription_id`; GCP: `project`), so a plan can't be
      applied to the wrong account or environment (CM-3, CM-5).
- [ ] Providers are pinned and `.terraform.lock.hcl` is committed. The lock file covers
      **providers only**: Terraform does not lock remote module versions, so pin modules
      with exact `version` constraints (registry) or a commit SHA `ref` (git)
      (`CM-2`, `SI-7`, `SR-3`, `SR-11`, KSI-SCR-MIT).

## 2. Identity and access (AC-2, AC-6, IA-2, IA-5, IA-5(7); KSI-IAM-*)
- [ ] No wildcard `Action` (AWS) or broad built-in roles (Azure Owner/Contributor at a broad
      scope, GCP `roles/owner`/`roles/editor`) granted to humans or workloads. Scope
      `Resource` to ARNs wherever the action supports resource-level permissions; where AWS
      requires `"Resource": "*"` (e.g. `ec2:DescribeInstances`), limit the actions, add the
      supported condition keys, and record the exception. Judge `Deny` statements separately.
- [ ] No long-lived credentials: AWS `aws_iam_access_key`/IAM users, Azure SP client
      secrets where a managed identity is possible, GCP `google_service_account_key`
      (KSI-IAM-SNU).
- [ ] Workload identity is used instead: IRSA/EKS Pod Identity, AKS workload identity, GKE
      Workload Identity.
- [ ] Privileged access is JIT/time-bound where the IaC manages it: Identity Center
      assignments, PIM eligible (not active) assignments, GCP PAM entitlements
      (KSI-IAM-JIT).
- [ ] Break-glass accounts are documented and monitored, not created ad hoc.
- [ ] Secrets come from a secrets manager or key vault, not variables, `default` values,
      or state outputs (IA-5(7), KSI-SVC-ASM).
      - `sensitive = true` only redacts CLI and HCP Terraform UI output. The value is still written in plaintext
        to state and saved plan files.
      - Prefer `ephemeral` variables/resources and write-only arguments (Terraform 1.10+
        and 1.11+) where the provider supports them.
      - Keep the state backend encrypted and access-restricted (see the S3 backend item).
- [ ] **CI/CD federation is pinned.** GitHub Actions OIDC trusts check both `aud` and
      `sub` for a specific repo *and* environment (or branch), e.g. AWS
      `token.actions.githubusercontent.com:aud = "sts.amazonaws.com"` and
      `token.actions.githubusercontent.com:sub = "repo:<org>/<repo>:environment:prod"`.
      No `repo:<org>/*` or `*` wildcards, no missing `sub` condition. Match the subject
      format GitHub actually issues; repos can customize it to include immutable
      owner/repo IDs. Equivalents: Azure federated identity credential `subject`; GCP
      Workload Identity Federation `attribute_condition` on `assertion.repository` and
      environment/ref. See section 9 for plan vs. apply roles (AC-6, IA-2, IA-5;
      KSI-IAM-SNU).
- [ ] **Cross-service and third-party trusts.** Service principals in role trusts and
      resource policies carry confused-deputy conditions (`aws:SourceArn` /
      `aws:SourceAccount`). Third-party SaaS roles require `sts:ExternalId` (AC-6,
      AC-20).
- [ ] **No anonymous Allow.** No `Principal: "*"` (or `{"AWS": "*"}`) in an **Allow**
      statement of a resource policy (S3, KMS, SQS, SNS, Lambda, ECR, Secrets Manager,
      VPC endpoint) unless an `aws:PrincipalOrgID` / `aws:PrincipalAccount` /
      `aws:SourceVpce` condition limits it. `Principal: "*"` in a **Deny** (e.g. the
      `aws:SecureTransport` deny) is correct; don't flag it (AC-3, AC-6, SC-7).
- [ ] **IMDSv2 required.** `metadata_options { http_tokens = "required" }` on
      `aws_instance` and `aws_launch_template`, and the regional account default
      `aws_ec2_instance_metadata_defaults` (`http_tokens = "required"`). The account
      default only applies to new launches and can be overridden, so check the
      instance/launch-template settings too, or enforce with an SCP on
      `ec2:MetadataHttpTokens` (SC-7, AC-6).
- [ ] **Terraform state backend** (state holds secrets and the full resource map). For
      S3: `encrypt = true` with `kms_key_id` (a CMK); `use_lockfile = true` (Terraform
      1.10+; `dynamodb_table` locking is deprecated); bucket versioning, Block Public
      Access, TLS-only bucket policy, and access logging; access limited to the
      pipeline roles plus break-glass. The backend has its own endpoint settings, so set
      `use_fips_endpoint = true` in the backend block too, not only in the provider.
      Both plan and apply roles need lock-file write/delete when locking is on
      (SC-28, AC-3, AC-6, CM-5).
- [ ] **Root access is centralized** (AWS Organizations):
      `aws_iam_organizations_features` with
      `enabled_features = ["RootCredentialsManagement", "RootSessions"]`, managed from the
      management account, then root credentials removed from member accounts (AC-2, AC-6,
      IA-2). **GovCloud differs:** GovCloud root users have no console sign-in and can't
      use MFA devices, and their access keys exist only if requested from AWS Support (or issued to a
      solution provider), so
      there are no root credentials to manage centrally. Enable `RootSessions` for
      privileged root tasks on member accounts, and flag any GovCloud root access keys
      that were requested and never deleted.
- [ ] **No inbound SSH/RDP for administration.** Use SSM Session Manager (or Azure
      Bastion / GCP IAP) instead. Session logs go to an encrypted destination: KMS
      encryption on the session preferences (`aws_ssm_document` `SSM-SessionManagerRunShell`
      `kmsKeyId`) and an encrypted S3/CloudWatch log target. Session Manager doesn't log
      the content of SSH-over-SSM or port-forwarding sessions, so restrict those session
      documents where session auditing is required (AC-17, AU-2, AU-12; KSI-CNA-RNT).
- [ ] **Credentials that can't be federated** (third-party API keys, database
      passwords) live in Secrets Manager / Key Vault / Secret Manager with rotation
      configured (`aws_secretsmanager_secret_rotation`, RDS
      `manage_master_user_password = true`) (IA-5(1), IA-5(7); KSI-SVC-ASM).
- [ ] **EKS uses access entries:** `access_config { authentication_mode = "API" }` on new
      clusters. For existing clusters, migrate through `API_AND_CONFIG_MAP` and verify
      access entries first; leaving ConfigMap mode can't be undone (AC-2, AC-6).

## 3. Network boundary (SC-7, AC-4; KSI-CNA-RNT, CNA-MAT, CNA-ULN)
- [ ] No ingress from `0.0.0.0/0` / `::/0` / `*` / `Internet` except to explicitly public
      front doors (LB/WAF/CDN), and never to SSH/RDP/DB/admin ports.
- [ ] Data stores are private. AWS: `publicly_accessible = false`, S3 public access block.
      Azure: public network access disabled (`public_network_access_enabled = false`, or
      `public_network_access = "Disabled"` on storage in azurerm 5.5.0+) + private endpoints. GCP: `sql.restrictPublicIp`,
      public access prevention.
- [ ] Egress is controlled (firewall/NAT with allow-lists) for Class C/D workloads.
- [ ] Kubernetes API endpoints are private or restricted to authorized CIDRs.
- [ ] Public entry points have a WAF and DDoS protection (SC-5, KSI-CNA-OFA).
- [ ] **No public sharing** (AC-3, AC-21, SC-7; KSI-CNA-RNT):
      - account-level S3 Block Public Access (`aws_s3_account_public_access_block`, all
        four settings true)
      - EBS snapshot and AMI public-sharing blocks (`aws_ebs_snapshot_block_public_access`
        `state = "block-all-sharing"`, `aws_ec2_image_block_public_access`
        `state = "block-new-sharing"`)
      - no RDS snapshots or AMIs shared with `all` (`aws_db_snapshot` /
        `shared_accounts`, `aws_ami_launch_permission` `group = "all"`)
      - no Lambda function URLs with `authorization_type = "NONE"` (use `AWS_IAM`).
        Function URLs aren't offered in GovCloud, so this applies to commercial regions
      - S3 object ownership `BucketOwnerEnforced` (`aws_s3_bucket_ownership_controls`),
        so ACLs can't grant access
- [ ] **Org-wide guardrails over per-resource settings** (AWS Organizations; all
      available in GovCloud). Prefer these to dozens of per-resource findings, and still
      check the resources for drift the policy doesn't cover:
      - **EC2 declarative policy** (`aws_organizations_policy` with
        `type = "DECLARATIVE_POLICY_EC2"`): IMDSv2 defaults (`instance_metadata_defaults`),
        `image_block_public_access`, `snapshot_block_public_access`,
        `vpc_block_public_access`, `serial_console_access`. Account admins can't change a
        setting the policy holds. IMDS *defaults* don't stop a launch from asking for
        IMDSv1; also set `instance_metadata_defaults.http_tokens_enforced` to
        `"enabled"`, and remediate existing IMDSv1 instances separately.
      - **Resource control policies** (`type = "RESOURCE_CONTROL_POLICY"`): deny
        non-TLS access (`aws:SecureTransport`) and access by principals outside the org
        (`aws:PrincipalOrgID`, with service-principal exceptions) on S3, KMS, STS, SQS,
        Secrets Manager, and the other services RCPs support. On STS, leave
        `AssumeRoleWithWebIdentity` and `AssumeRoleWithSAML` out of the org-only deny:
        GitHub OIDC and IdP federation carry no `aws:PrincipalOrgID`. Check the current supported
        service list; RCPs don't apply to the management account or service-linked roles.
      (AC-3, AC-6, CM-6, CM-7, SC-7, SC-8; KSI-CNA-RNT)
- [ ] **DNSSEC on public DNS.** Public Route 53 hosted zones are signed
      (`aws_route53_key_signing_key` backed by an asymmetric `ECC_NIST_P256` KMS key, plus
      `aws_route53_hosted_zone_dnssec`), and the DS record is published at the parent.
      The KMS key must be in `us-east-1` (commercial) or `us-gov-west-1` (GovCloud). Add a
      CloudWatch alarm on `DNSSECInternalFailure` / `DNSSECKeySigningKeysNeedingAction`.
      Azure DNS and Cloud DNS have their own DNSSEC settings (SC-20, SC-21).
- [ ] **Default VPCs removed** in every in-boundary account and region (Control Tower
      account factory option, or a baseline job). _Guidance:_ a strong default, not a
      FedRAMP rule; unused default VPCs widen the attack surface (CM-7, SC-7).
- [ ] **VPC endpoints act as a data perimeter:** gateway and interface endpoints carry an
      `aws_vpc_endpoint` `policy` that limits principals and resources to the org
      (`aws:PrincipalOrgID`, `aws:ResourceOrgID`), with explicit exceptions for
      AWS-owned resources the workloads need. The default policy allows full access.
      Endpoint policies only govern traffic through that endpoint; pair them with RCPs
      and SCPs (AC-4, SC-7).
- [ ] **ALBs drop invalid headers:** `aws_lb` `drop_invalid_header_fields = true` (guards
      against request smuggling) (SC-7, SI-10).

## 4. Encryption (SC-8, SC-12, SC-13, SC-28; CMU; KSI-SVC-SIN, SVC-VCM)
- [ ] Encryption at rest is on for every data store, with customer-managed keys where the
      SDR says so (S3/EBS/RDS/…; Storage/SQL/disks; GCS/SQL/BigQuery CMEK).
- [ ] Keys: rotation enabled, deletion/purge protection, and key policies restrict admins
      vs. users (separation of duties, AC-5). AWS KMS rotates only symmetric encryption
      keys with AWS-generated material automatically. Symmetric keys with imported
      material support on-demand rotation. Asymmetric keys, HMAC keys, and keys in custom
      key stores (e.g. the DNSSEC KSK key) need a documented manual rollover instead of
      `enable_key_rotation`.
- [ ] TLS 1.2+ on every listener/endpoint. FIPS-capable policies where available
      (AWS ELB FIPS policies, `use_fips_endpoint = true`; GCP SSL policy `FIPS_202205`;
      AKS `fips_enabled`). Plain HTTP is redirected or disabled (App Service
      `https_only = true`).
- [ ] Storage is only reachable over TLS (S3 `aws:SecureTransport` deny, Azure
      `https_traffic_only_enabled`). GCS has no bucket-level TLS-only setting, so confirm
      that clients use the HTTPS endpoints, and use org policy `gcp.restrictTLSVersion` to
      block TLS 1.0/1.1.
- [ ] Databases reject non-TLS clients: RDS/Aurora parameter `rds.force_ssl = 1`
      (PostgreSQL, SQL Server) or `require_secure_transport = ON` (MySQL, MariaDB) in the
      `aws_db_parameter_group` / `aws_rds_cluster_parameter_group`; Azure/GCP: enforce
      TLS on the server (`ssl_enforcement`/`require_ssl` equivalents) (SC-8).
- [ ] The crypto modules in use can be listed for `CMU-CSO-CMD`. Flag services that have
      no FIPS endpoint.

## 5. Logging and monitoring (AU-2, AU-3, AU-6, AU-9, AU-11, AU-12, SI-4; KSI-MLA-*)
- [ ] Control-plane audit logging is org-wide and multi-region: AWS org CloudTrail with
      log file validation + KMS; Azure diagnostic settings to Log Analytics on the
      subscription, Entra, and every resource; GCP org sink + Data Access logs (for Class D
      also AU-12(1), a system-wide, time-correlated audit trail).
- [ ] Data-plane/access logging is on for data stores and load balancers where relevant.
- [ ] Log storage is immutable (Object Lock / immutable blob / GCS bucket lock), and
      access is restricted to a small security role (AU-9; AU-9(4) for Class C/D; AU-9(3)
      for Class D; KSI-MLA-ALA).
- [ ] Retention is set explicitly. Don't default to "never expire" or 1 day. The period
      comes from the SDR / AU-11 decision.
- [ ] Threat detection is enabled org-wide (GuardDuty / Defender for Cloud / SCC), and
      findings are routed to the SIEM or ticketing (KSI-MLA-OSM, IR-4, SI-4).
- [ ] VPC/VNet flow logs are on for in-boundary networks.
- [ ] The org trail records **S3 data events** for buckets holding federal customer data
      or logs (`advanced_event_selector` on `data.resources.type = AWS::S3::Object`), not
      management events only (AU-2, AU-12).
- [ ] ALB access logs, S3 server access logs, and VPC Resolver query logs reach the
      central log archive. ALB and S3 server access logs can only be delivered to an
      SSE-S3 bucket in the same Region (S3: same account too, no Object Lock default
      retention), so deliver locally, then copy them into the CMK-encrypted, Object-Locked
      archive with SSE-KMS set on the copy (S3 Batch Operations, a Lambda copy, or a
      Firehose/SIEM pipeline). Native S3 replication keeps the source's SSE-S3 encryption
      on the replica, so it does not re-encrypt them with the CMK. Flag a design that points them
      directly at a CMK or Object Lock bucket, because delivery will fail (AU-2, AU-9,
      AU-12).
- [ ] Security services (GuardDuty, Security Hub CSPM, Config, Inspector, Macie, IAM
      Access Analyzer) run from a **delegated administrator** account, not the management
      account, and are **auto-enabled for new accounts** (`auto_enable` /
      `auto_enable_organization_members = "ALL"`) (CA-7, SI-4; KSI-MLA-OSM).
- [ ] _Guidance:_ log-archive Object Lock uses `COMPLIANCE` mode. `GOVERNANCE` mode can be
      bypassed by principals with `s3:BypassGovernanceRetention`, so it doesn't make logs
      immutable to an admin (AU-9).
- [ ] **Security tooling can't be switched off:** SCPs deny `cloudtrail:StopLogging` /
      `DeleteTrail` / `UpdateTrail`, `guardduty:DeleteDetector` /
      `DisassociateFromAdministratorAccount`, `config:StopConfigurationRecorder` /
      `DeleteConfigurationRecorder`, `securityhub:DisableSecurityHub`, and
      `organizations:LeaveOrganization`, except for a named break-glass role. SCPs don't
      apply to the management account or service-linked roles, so keep workloads out of
      the management account. Azure: Azure Policy `deny`/`DeployIfNotExists` on
      diagnostic settings and Defender plans, plus management-group RBAC (deny assignments
      only come from managed mechanisms such as deployment stacks). GCP: org policy
      constraints and IAM deny policies on logging sinks and SCC settings (AU-9, CM-5,
      SI-4; KSI-MLA-OSM).

## 6. Configuration and change management (CM-2, CM-3, CM-3(2), CM-4, CM-5, CM-6, CM-6(1), CA-7; KSI-CMT-*, KSI-SVC-ACM, KSI-CNA-EIS)
- [ ] Compliance-as-code is deployed: AWS Config conformance pack + Security Hub NIST
      800-53 standard (Security Hub CSPM) / Azure Policy FedRAMP or NIST initiative / SCC
      Premium with Compliance Manager.
- [ ] Changes flow through a pipeline with plan review, policy checks (Checkov,
      `trivy config` (tfsec has been folded into Trivy), OPA/Conftest, Sentinel, or
      Terraform policy), and approvals. No local `apply`: humans shouldn't hold
      write credentials outside the pipeline (CM-5, KSI-CMT-VTD, KSI-CMT-LMC).
- [ ] Drift detection runs on a schedule (a plan-only job) and its output is kept as
      evidence. A plan job is *one input* to `VDR-TFR-PDD` (Persistent Drift Detection).
      That rule asks for vulnerability detection on resources likely to drift, and FedRAMP
      treats misconfiguration as a vulnerability. It applies to all classes (SHOULD):
      at least every 3 months for A, 1 month for B, 14 days for C, and 7 days for D. Confirm
      with `fedramp.py lookup VDR-TFR-PDD`.
- [ ] Resources are replaced rather than modified in place where feasible
      (KSI-CMT-RMV): immutable images, launch templates, node pool rotation.
- [ ] API-level deletion protection on stateful in-boundary resources, e.g. RDS
      `deletion_protection`, Key Vault purge protection, Cloud SQL
      `settings.deletion_protection_enabled`, or Compute `deletion_protection`. On Cloud
      SQL and GKE, the top-level `deletion_protection` argument only blocks *Terraform*
      from deleting the resource.
      `lifecycle { prevent_destroy = true }` is only a guard inside Terraform. It does
      nothing once the resource block is removed, or for changes made outside Terraform.
- [ ] **Every in-boundary resource is managed by IaC** (CM-2, CM-3, CM-8; KSI-CMT-LMC,
      KSI-PIY-GIV). _Guidance:_ treat unmanaged resources as findings to reconcile, not
      automatic non-compliance; service-created resources and documented emergency
      changes are expected. Flag:
      - resources created in the console or CloudShell
      - `import` blocks or `terraform import` work that is pending and not yet applied
      - resources that exist in the account but not in any state file
      How to find them: CloudTrail write events whose principal isn't a pipeline role;
      AWS Config / Resource Explorer inventory compared with `terraform state list`
      across workspaces; `terraform plan -refresh-only` for drift on managed resources.
- [ ] **Changes are classified for SCN.** The pipeline (or PR template) records whether a
      change is a significant change and its type (`SCN-CSO-EVA`), keeps those records
      for FedRAMP (`SCN-CSO-MAR`), and has an emergency-change path: emergency changes
      MAY skip advance notice, but MUST notify, supply the SCN materials retroactively,
      and be assessed afterwards (`SCN-CSO-EMG`).
- [ ] _Guidance below Class D:_ ECR repositories use `image_tag_mutability = "IMMUTABLE"`
      and scanning (basic `scan_on_push`, or enhanced continuous scanning, which also
      catches CVEs published after the push). Lambda functions attach an
      `aws_lambda_code_signing_config` (`policies { untrusted_artifact_on_deployment =
      "Enforce" }`) via `code_signing_config_arn`; the config alone protects nothing.
      For Class D these support CM-14 (signed components) and SI-7 (CM-2, SI-7, SR-11).

## 7. Resilience (CP-6, CP-7, CP-9, CP-9(8), CP-10, CP-10(2); KSI-RPL-*, KSI-CNA-OFA)
- [ ] Backups are configured by policy (AWS Backup / Azure Backup / GCP Backup and DR),
      with immutability or vault lock, and a cross-region or cross-account copy for
      Class C/D.
- [ ] Multi-AZ/zone-redundant settings on stateful services match the stated RTO/RPO.
- [ ] Point-in-time recovery is on for databases.

## 8. Vulnerability management hooks (RA-5, SI-2; VDR/VER)
- [ ] Image/registry scanning is enabled (ECR enhanced / Defender for Containers /
      Artifact Analysis). The Inspector/Defender/VM Manager agents or agentless scanning
      cover all compute.
- [ ] Patch baselines/maintenance windows are defined (SSM Patch Manager / Update Manager /
      OS Config).
- [ ] AMIs/images come from a hardened pipeline (CIS/STIG, FIPS mode), not ad hoc
      marketplace images (CM-2, CM-6).

## 9. CI/CD pipeline: GitHub Actions (CM-3, CM-5, AC-6, IA-5, SA-10, SR-3, SI-7; KSI-CMT-*, KSI-SCR-MIT)

The pipeline holds the credentials that change the boundary, so review `.github/workflows/`
with the same weight as the `.tf` files. Items marked _Guidance_ are organizational
standards, not FedRAMP rules.

**Scope**
- [ ] GitHub (the org, repos, Actions) and its runners are documented as third-party
      information resources when they can affect federal customer data (`MAS-CSO-TPR`):
      usage, configuration, justification, mitigations. Check GitHub's current FedRAMP
      status on the FedRAMP Marketplace rather than assuming it.
- [ ] _Guidance:_ for Class C/D, deploy jobs run on **controlled, ephemeral self-hosted
      runners** inside the boundary (one job per runner, e.g. Actions Runner Controller or
      CodeBuild-hosted runners), not GitHub-hosted runners. Never use self-hosted runners
      on public repos.
- [ ] _Guidance:_ FedRAMP repos live in a separate GitHub organization (or enterprise) with
      its own owners, SSO, and policies, apart from commercial work.

**Hardening**
- [ ] Third-party actions are pinned to a full 40-character commit SHA (with a `# vX.Y.Z`
      comment), kept current by Dependabot (`package-ecosystem: "github-actions"`).
      Enterprise/org policy "require actions to be pinned to a full-length commit SHA"
      where available.
- [ ] Dependabot (or Renovate) also covers Terraform (`package-ecosystem: "terraform"`)
      so providers and modules stay patched (SI-2, SR-3; KSI-SCR-MIT).
- [ ] Workflows are scanned in CI with `zizmor` (security: injection, `pull_request_target`,
      unpinned actions, excessive permissions) and `actionlint` (correctness), as
      required checks. They automate several workflow-level checks, but not trust
      policies, environment protections, org settings, or runner isolation.
- [ ] **Org-level Actions policy:** default `GITHUB_TOKEN` permissions read-only;
      "Allow GitHub Actions to create and approve pull requests" off (otherwise a workflow
      can satisfy its own required review); allowed actions limited to GitHub-owned,
      verified creators, and an explicit allow-list; fork PR workflows from outside
      collaborators need approval. Self-hosted runners have egress limited to an
      allow-list (GitHub, the cloud APIs/FIPS endpoints, package mirrors) (AC-6, CM-7,
      SC-7).
- [ ] Least-privilege `permissions:`: workflow default `contents: read` (or `{}`), and
      each job adds only what it needs. `id-token: write` only on jobs that use OIDC
      (cloud role assumption, artifact attestations).
- [ ] No `pull_request_target` or `workflow_run` job that checks out or runs PR code with
      secrets, write tokens, or cloud credentials.
- [ ] No script injection: `${{ github.event.* }}` / `${{ github.head_ref }}` and other
      untrusted values never appear inside `run:`; pass them through `env:` and quote
      them.
- [ ] **Untrusted PRs can't reach production.** `terraform plan` runs provider code and
      `external` data sources, and reads state. Plans for fork or unreviewed PRs use no
      production credentials, state, or privileged runner networks; a production plan
      runs only on trusted branches or after review.
- [ ] `concurrency:` groups serialize runs per state/environment
      (`group: terraform-${{ inputs.environment }}`), with `cancel-in-progress: false` for
      apply jobs, so two applies can't race and an apply is never killed midway.
- [ ] `terraform init -lockfile=readonly`, so CI can't silently change provider hashes.
- [ ] IaC scanners (Checkov, `trivy config`) and `terraform validate` are required status
      checks.
- [ ] GovCloud: OIDC provider and role ARNs are built from `data.aws_partition` (never
      `arn:aws:`), the job sets `AWS_USE_FIPS_ENDPOINT=true`, and the region is
      `us-gov-west-1` / `us-gov-east-1`.
- [ ] `role-session-name` includes the run ID (e.g. `gha-${{ github.run_id }}`) so
      CloudTrail entries trace back to a workflow run (AU-3).

**Change control**
- [ ] **Separate plan and change roles.** A read-only plan role (plus state-lock writes)
      that PR/branch jobs can assume, and an apply role whose trust `sub` is scoped to a
      GitHub **environment** (`repo:<org>/<repo>:environment:prod`). The environment has
      required reviewers, "Prevent self-review" on, admin bypass off, and deployment
      branch/tag restrictions. Required reviewers on private repos need GitHub
      Enterprise (or Pro/Team for public repos only); check the plan (CM-3, CM-5, AC-5).
- [ ] **Deploys run only through a central reusable workflow.** The org customizes the
      OIDC `sub` claim template (GitHub REST API: OIDC subject claim customization) to
      include `repo`, `context`, and `job_workflow_ref`, and each repo opts in
      (`use_default: false`); the org template doesn't apply until it does. Customizing
      replaces the default subject format, so the trust must match the complete new
      `sub`, keeping the repo and environment parts, with `job_workflow_ref` pinned to
      `<org>/<platform-repo>/.github/workflows/deploy.yml@refs/heads/main` (or a tag). A
      repo can't then write its own job that assumes the role. Keep the platform repo's
      own rules strict, since anyone allowed to call the workflow can use it
      (CM-3, CM-5, AC-6).
- [ ] The apply role can't widen its own access: no unbounded `iam:PassRole`, no rights
      to edit its own trust or policies, or to remove permission boundaries and SCPs
      (AC-6, CM-5).
- [ ] **What was reviewed is what runs.** Apply uses the saved plan file (`terraform apply
      tfplan`) produced from the approved commit, not a fresh plan. Bind it to the commit
      SHA, workflow run, and target state, and check its digest before applying. Never
      run `apply` on `pull_request` events (CM-3, CM-4, SI-7).
- [ ] Branch rulesets on the default branch: PR required, approvals, CODEOWNERS review
      (CODEOWNERS covers `*.tf`, `.github/workflows/`, and `CODEOWNERS` itself), status
      checks required, no force pushes or deletions, bypass limited and logged.
- [ ] _Guidance:_ signed commits required by ruleset. This strengthens SI-7 integrity
      evidence; it doesn't by itself meet CM-14 (Class D), which is about verifying signed
      software and firmware components before installation (e.g. image signature
      verification).

**Secrets and evidence**
- [ ] No stored cloud keys: no `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`, Azure client
      secrets, or GCP key JSON in repo, environment, or org secrets; OIDC only
      (IA-5, KSI-IAM-SNU).
- [ ] Secret scanning with push protection is on for every repo.
- [ ] Saved plan artifacts contain cleartext sensitive values. Anyone with read access to
      the repo can download Actions artifacts; environment protection rules do not limit
      downloads. Keep plans in storage only the deploy roles can read, or encrypt them
      before upload with a key only the apply job can use, and set a short
      `retention-days` (SC-28).
- [ ] Plan output posted to PRs or job summaries (tfcmt, Atlantis, custom scripts) is a
      summary or redacted, because anyone with repo read access sees it. `sensitive`
      only masks marked values; data sources and some attributes can still print secrets
      (SC-28, AC-3).
- [ ] The GitHub audit log is streamed to the SIEM (enterprise audit log streaming) and
      retained per AU-11 (AU-2, AU-6; KSI-MLA-OSM).
- [ ] _Guidance:_ build provenance attestations (`actions/attest-build-provenance`) for
      images and artifacts deployed into the boundary, verified before deploy (SR-4,
      SI-7; KSI-SCR-MIT).

**Evidence automation (20x)**
- [ ] _Guidance:_ a scheduled workflow (e.g. nightly) produces the persistent,
      machine-generated evidence KSIs expect and writes it to an Object-Locked evidence
      bucket under dated keys. Its OIDC role is read-only except `s3:PutObject` on the
      evidence prefix and the KMS permissions to encrypt (or a separate writer role):
      - AWS Config conformance pack compliance and Security Hub CSPM NIST 800-53 score
      - a `terraform plan -detailed-exitcode` drift result per workspace (`VDR-TFR-PDD`)
      - an inventory export (Config advanced query / Resource Explorer) compared with
        state (KSI-PIY-GIV)
      - IAM user/access-key counts, IMDSv1 count, public-resource count
      It feeds the historical metrics in the SDR (`SDR-CSX-KMT`): Class B SHOULD supply
      30-day and up-to-1-year summaries; Class C MUST also supply all daily metric data,
      including the status of persistent validation. Alert on a failed run: a
      broken evidence job is a failed detection (`VDR-CSO-FAV`).

## After the review: deployed findings

If the reviewed code is already deployed, a confirmed finding is a candidate
**vulnerability** (FedRAMP treats misconfiguration as one). Validate it against the live
resource first, then hand it to the VDR/VER process:

1. Evaluate it formally within the class's `VER-TFR-EVU` window: internet reachability
   (`VER-EVA-EIR`), likely exploitability (`VER-EVA-ELX`), and potential agency impact,
   rated N0–N5 (`VER-EVA-EPA`). N0 means exploitation is extremely unlikely to have any
   adverse effect on agencies; it isn't a "false positive" label.
2. `VDR-TFR-PVR` (SHOULD) sets the mitigation timeframes from the evaluation, by PAIN ×
   reachability × exploitability. KEVs follow CISA due dates (`VDR-TFR-KEV`). Check
   whether `VER-TFR-IRI` / `VER-TFR-NRI` make it a reportable incident for the class.
3. Track it in the vulnerability report: `VER-RPT-VDT` fields, or `VER-RPT-AVI` if it
   becomes an accepted vulnerability.
4. A broken detection or response mechanism (scanner disabled, logging off, drift job
   failing) is itself a vulnerability (`VDR-CSO-FAV`).

Look up the class-specific text with `fedramp.py lookup` before quoting a timeframe.

## What Terraform cannot show (say so in reviews)
Training (KSI-CED), IR procedures and after-action reviews (KSI-INR), executive support and
investment reviews (KSI-PIY-RES/RIS), recovery *testing* (KSI-RPL-TRC), supply-chain
vendor review (KSI-SCR; repo automation like Dependabot covers only part of it), the
SDR/CPO documents themselves, and all agency-facing reporting (CCM, VER, IEC, SCN).

## Tooling to suggest
- **Checkov** (open source) checks the security settings above, but it has **no selectable
  NIST 800-53 or FedRAMP framework**. `--framework` selects the IaC type, and compliance
  filtering (`--policy-metadata-filter`) needs a Prisma Cloud API key. Use it for
  misconfiguration findings, and map them to controls yourself. Pin the version, and set
  `soft_fail: false` in CI. Unset means a hard fail, but state it explicitly.
- **Trivy** (`trivy config`) is the successor to tfsec for IaC misconfiguration scanning.
- **terraform test** with mock providers (`mock_provider`, `override_resource`; Terraform
  1.7+) to assert security-relevant attributes.
- **Policy as code:** OPA/Conftest or Sentinel for deny rules. HashiCorp's HCL-based
  **Terraform policy** (`.policy.hcl`, `tfpolicy test`) was announced on 2026-07-16 as a
  public beta in HCP Terraform. HashiCorp says not to use it in production yet.
