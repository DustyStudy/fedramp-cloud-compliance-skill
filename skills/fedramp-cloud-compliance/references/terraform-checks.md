# Terraform / IaC review checklist for FedRAMP

Use this for reviewing a plan, module, or PR. Report each finding as:

```
[SEVERITY] path/file.tf:LINE — resource.address
Problem: <what is wrong, concretely>
Fix: <attribute/value or code change>
Maps to: <800-53 control(s)> · <KSI(s)> · <rule ID(s) if any>
```

Severity guide:
- **Critical:** public exposure of data or admin surfaces, or no encryption for federal
  customer data.
- **High:** missing audit logging, wildcard IAM, long-lived credentials, non-FIPS
  endpoints/crypto where Class C/D requires them.
- **Medium:** weak retention, missing drift/inventory tooling, missing tags for boundary
  scoping.
- **Low:** hygiene.

Before reviewing, establish the **type/class**, the **cloud and partition** (GovCloud,
Azure Government, Assured Workloads regime), and whether the resources are **in the
boundary** (`MAS-CSO-IIR`). Crypto expectations depend on class: `CMU-CSO-UVM` says
validated modules are MAY for A/B, SHOULD for C, and MUST for D.

## 1. Boundary and inventory (CM-8, PL-2, MAS, KSI-PIY-GIV)
- [ ] In-boundary resources are identifiable, e.g. by a consistent tag/label such as
      `fedramp:boundary=in`, provider `default_tags`, or an Azure Policy or GCP org policy
      that requires it.
- [ ] The resources are in a government partition or regime where the class requires one:
      AWS `aws-us-gov` partition, azurerm `environment = "usgovernment"`, or GCP projects
      under an Assured Workloads folder.
- [ ] Regions are restricted: AWS SCP on `aws:RequestedRegion`, Azure "Allowed locations"
      policy, GCP `gcp.resourceLocations`.
- [ ] Third-party modules and providers are pinned by version, with a lock file committed
      (`SR-3`, `CM-2`, KSI-SCR-MIT).

## 2. Identity and access (AC-2, AC-6, IA-2, IA-5; KSI-IAM-*)
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
      or state outputs (KSI-SVC-ASM). Sensitive variables are marked `sensitive = true`,
      and the state backend is encrypted and access-restricted.

## 3. Network boundary (SC-7, AC-4; KSI-CNA-RNT, CNA-MAT, CNA-ULN)
- [ ] No ingress from `0.0.0.0/0` / `::/0` / `*` / `Internet` except to explicitly public
      front doors (LB/WAF/CDN), and never to SSH/RDP/DB/admin ports.
- [ ] Data stores are private. AWS: `publicly_accessible = false`, S3 public access block.
      Azure: `public_network_access_enabled = false` + private endpoints. GCP: `sql.restrictPublicIp`,
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
      (AWS ELB FIPS policies, `use_fips_endpoint = true`; AKS `fips_enabled`). Plain HTTP
      is redirected or disabled.
- [ ] Storage is only reachable over TLS (S3 `aws:SecureTransport` deny, Azure
      `https_traffic_only_enabled`, GCS is TLS by default).
- [ ] The crypto modules in use can be listed for `CMU-CSO-CMD`. Flag services that have
      no FIPS endpoint.

## 5. Logging and monitoring (AU-2, AU-3, AU-6, AU-9, AU-11, AU-12, SI-4; KSI-MLA-*)
- [ ] Control-plane audit logging is org-wide and multi-region: AWS org CloudTrail with
      log file validation + KMS; Azure diagnostic settings to Log Analytics on the
      subscription, Entra, and every resource; GCP org sink + Data Access logs.
- [ ] Data-plane/access logging is on for data stores and load balancers where relevant.
- [ ] Log storage is immutable (Object Lock / immutable blob / GCS bucket lock), and
      access is restricted to a small security role (AU-9, KSI-MLA-ALA).
- [ ] Retention is set explicitly. Don't default to "never expire" or 1 day. The period
      comes from the SDR / AU-11 decision.
- [ ] Threat detection is enabled org-wide (GuardDuty / Defender for Cloud / SCC), and
      findings are routed to the SIEM or ticketing (KSI-MLA-OSM, IR-4, SI-4).
- [ ] VPC/VNet flow logs are on for in-boundary networks.

## 6. Configuration and change management (CM-2, CM-3, CM-6, CA-7; KSI-CMT-*, KSI-SVC-ACM, KSI-CNA-EIS)
- [ ] Compliance-as-code is deployed: AWS Config conformance pack + Security Hub NIST
      800-53 standard / Azure Policy FedRAMP or NIST initiative / SCC.
- [ ] Changes flow through a pipeline with plan review, policy checks (Checkov, tfsec,
      OPA/Sentinel/Terraform policy), and approvals, not local `apply` (KSI-CMT-VTD,
      KSI-CMT-LMC).
- [ ] Drift detection runs on a schedule (a plan-only job) and its output is kept as
      evidence. For 20x Class B/C, the cadence should meet `VDR-TFR-PDD`, which you can
      check with `fedramp.py lookup VDR-TFR-PDD`.
- [ ] Resources are replaced rather than modified in place where feasible
      (KSI-CMT-RMV): immutable images, launch templates, node pool rotation.
- [ ] `lifecycle { prevent_destroy = true }` / deletion protection on stateful
      in-boundary resources.

## 7. Resilience (CP-9, CP-10, SC-5; KSI-RPL-*, KSI-CNA-OFA)
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
      marketplace images.

## What Terraform cannot show (say so in reviews)
Training (KSI-CED), IR procedures and after-action reviews (KSI-INR), executive support and
investment reviews (KSI-PIY-RES/RIS), recovery *testing* (KSI-RPL-TRC), supply-chain
vendor review (KSI-SCR), the SDR/CPO documents themselves, and all agency-facing
reporting (CCM, VER, IEC, SCN).

## Tooling to suggest
- **Checkov** has NIST 800-53 and FedRAMP-oriented policies. Run it with a pinned version
  and `soft_fail: false` in CI.
- **terraform test** with mock providers to assert security-relevant attributes.
- **Terraform/OPA/Sentinel policies** that encode the checks above as deny rules.
