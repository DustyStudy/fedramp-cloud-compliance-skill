# Terraform / IaC review checklist for FedRAMP

Use this for reviewing a plan, module, or PR. Report each finding as:

```
[SEVERITY] path/file.tf:LINE — resource.address
Problem: <what is wrong, concretely>
Fix: <attribute/value or code change>
Maps to: <800-53 control(s)> · <KSI(s)> · <rule ID(s) if any>
```

Severity guide (_guidance_: FedRAMP defines no IaC severity scale, so adjust it to your program's risk methodology):
- **Critical:** public exposure of data or admin surfaces, or no encryption for federal
  customer data.
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
- [ ] Providers are pinned and `.terraform.lock.hcl` is committed. The lock file covers
      **providers only**: Terraform does not lock remote module versions, so pin modules
      with exact `version` constraints (registry) or a commit SHA `ref` (git)
      (`CM-2`, `SI-7`, `SR-3`, `SR-11`, KSI-SCR-MIT).

## 2. Identity and access (AC-2, AC-6, IA-2, IA-5, IA-5(7); KSI-IAM-*)
- [ ] No wildcard `Action`/`Resource` (AWS) or broad built-in roles (Azure Owner/Contributor
      at a broad scope, GCP `roles/owner`/`roles/editor`) granted to humans or workloads.
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
      - Keep the state backend encrypted and access-restricted.

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

## 4. Encryption (SC-8, SC-12, SC-13, SC-28; CMU; KSI-SVC-SIN, SVC-VCM)
- [ ] Encryption at rest is on for every data store, with customer-managed keys where the
      SDR says so (S3/EBS/RDS/…; Storage/SQL/disks; GCS/SQL/BigQuery CMEK).
- [ ] Keys: rotation enabled, deletion/purge protection, and key policies restrict admins
      vs. users (separation of duties, AC-5).
- [ ] TLS 1.2+ on every listener/endpoint. FIPS-capable policies where available
      (AWS ELB FIPS policies, `use_fips_endpoint = true`; GCP SSL policy `FIPS_202205`;
      AKS `fips_enabled`). Plain HTTP is redirected or disabled (App Service
      `https_only = true`).
- [ ] Storage is only reachable over TLS (S3 `aws:SecureTransport` deny, Azure
      `https_traffic_only_enabled`). GCS has no bucket-level TLS-only setting, so confirm
      that clients use the HTTPS endpoints, and use org policy `gcp.restrictTLSVersion` to
      block TLS 1.0/1.1.
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
