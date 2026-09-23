# Google Cloud implementation guide for FedRAMP

Starting points for implementation, not proof of compliance. **Before you assert that a
service is authorized, check the live FedRAMP/DoD scope list:**
https://docs.cloud.google.com/architecture/security/fedramp-dod-compliance-scope
(general list: https://cloud.google.com/security/compliance/services-in-scope)

## Authorization posture and inheritance

- Google Cloud holds FedRAMP authorizations for many services in US regions. Coverage is
  per service, so check the services-in-scope list.
- **Assured Workloads** enforces a compliance regime on a folder that it creates. It
  limits the folder to services in scope for that regime and applies org policies. The
  other controls depend on the package:
  - The **FedRAMP High** package adds US-only data location plus personnel and support
    controls. Google states that FedRAMP High on Google Cloud requires Assured Workloads
    *and* Assured Support.
  - The **FedRAMP Moderate** package is documented mainly with support-personnel
    controls. Set `gcp.resourceLocations` yourself if you need location restriction. The Terraform
  `google_assured_workloads_workload.compliance_regime` values include `FEDRAMP_MODERATE`,
  `FEDRAMP_HIGH`, `IL2`, `IL4`, `IL5`, `CJIS`, `ITAR`, and `IRS_1075`. The regime is
  **immutable**, so choose it before creating projects.
- **Get Google's FedRAMP package (SSP, CRM):** request it under NDA through your Google
  account team, or through the FedRAMP PMO package request form (agencies). Compliance
  Reports Manager has public attestations, not the full package. The CSP inherits PE and most MA/MP, and nothing for its own IAM,
  configuration, logging, or application.
- Every Google service you use is a **third-party information resource** under
  `MAS-CSO-TPR`.

## Cryptography (CMU, SC-8, SC-12, SC-13, SC-28)

- Google encrypts at rest by default, and BoringCrypto holds a FIPS 140-3 certificate
  (#5104). Cite the current certificates from csrc.nist.gov, not from memory.
- **Cloud KMS** for customer-managed keys (CMEK). Protection levels are `SOFTWARE` (FIPS
  140-3 Level 1), `HSM` (Cloud HSM, FIPS 140-2 Level 3), `HSM_SINGLE_TENANT`, `EXTERNAL`,
  and `EXTERNAL_VPC`. The last two are Cloud EKM. Enforce them with org policies
  `constraints/gcp.restrictNonCmekServices` and `constraints/gcp.restrictCmekCryptoKeyProjects`.
  These are *list* constraints, so configure them with `values`, not `enforce`.
  `restrictNonCmekServices` doesn't apply to resources that already exist. Set a rotation
  period on keys.
- **TLS:** on load balancers, use SSL policies with `min_tls_version = "TLS_1_2"` and the
  `FIPS_202205` profile, which requires TLS_1_2, or `RESTRICTED`/`CUSTOM`. `TLS_1_3`
  requires `RESTRICTED`. Cloud SQL: `ip_configuration.ssl_mode = "ENCRYPTED_ONLY"` or
  `TRUSTED_CLIENT_CERTIFICATE_REQUIRED` (not supported on SQL Server). `require_ssl` was
  removed in provider 6.0.
- **Your own code:** use a validated module. On GKE, check whether the node image and
  your binaries run in FIPS mode.

## Control family → Google Cloud services

| Family | Primary GCP mechanisms | Customer must still… |
|---|---|---|
| AC | Cloud IAM (predefined/custom roles, no basic roles), IAM Conditions, **Privileged Access Manager** (JIT grants), IAM deny policies, org policy `iam.allowedPolicyMemberDomains`, VPC Service Controls perimeters | Role design, reviews, least privilege |
| AU | Cloud Audit Logs (Admin Activity always on; **enable Data Access logs** for in-scope services); aggregated **org-level log sinks** to a locked log bucket (bucket lock / retention policy) or BigQuery; VPC Flow Logs; firewall rules logging | Event selection, review, retention, log access |
| CA / CM | **Security Command Center Premium** (the Enterprise tier is deprecated and shuts down 2027-05-21) with **Compliance Manager** (includes a NIST SP 800-53 framework), Security Health Analytics, posture management; Assured Workloads violation monitoring; Cloud Asset Inventory; OS Config / VM Manager | Baselines, change control, remediation, inventory accuracy |
| CP | Backup and DR Service; regional/multi-regional services; Cloud SQL HA + PITR; GCS object versioning / retention | RTO/RPO, restore testing |
| IA | Cloud Identity / Workspace or a federated IdP with **phishing-resistant 2SV** (security keys / passkeys enforced); Workload Identity Federation instead of service-account keys (`iam.disableServiceAccountKeyCreation`); OS Login (`compute.requireOsLogin` enforces OS Login only; 2FA also needs instance/project metadata `enable-oslogin-2fa = TRUE`) | IdP policy, authenticator lifecycle |
| IR | SCC threat detection (Event Threat Detection, Container Threat Detection), Google SecOps (Chronicle) SIEM/SOAR, Pub/Sub notifications to ticketing | IR plan, PAIN rating, IEC reporting |
| RA / SI | Artifact Analysis (container scanning), VM Manager vulnerability reports, GKE security posture, Web Security Scanner, Sensitive Data Protection (DLP) | VER evaluation, VDR timeframes, KEV remediation |
| SC | VPC firewall policies (hierarchical), Cloud NGFW, Cloud Armor, Private Service Connect / Private Google Access, VPC Service Controls, Cloud KMS/HSM, org policies `compute.vmExternalIpAccess`, `sql.restrictPublicIp`, `storage.publicAccessPrevention`, `compute.skipDefaultNetworkCreation` | Deny-by-default flows, boundary docs, crypto module list |
| SR | Binary Authorization (attestation-based deploy), Artifact Registry, Assured Open Source Software, SLSA provenance from Cloud Build | Vendor risk, provenance |
| PE / MA / MP | Inherited from Google for the infrastructure; **Access Transparency** and **Access Approval** give visibility and control over Google personnel access | Your own endpoints and media |

## KSI measure ideas (20x)

| KSI | Example GCP measure |
|---|---|
| CNA-RNT / CNA-MAT / CNA-ULN | Org policy compliance (no external IPs, no default network); firewall policy exports; VPC-SC perimeter dry-run violations → zero |
| CNA-EIS / SVC-ACM | SCC Security Health Analytics findings trend; Config Sync / Policy Controller violations; Terraform plan-drift job |
| IAM-APM | Admin console 2SV enforcement report showing security-key-only; IdP policy export |
| IAM-JIT / IAM-ELP | Privileged Access Manager grant logs; IAM Recommender excess-permission findings |
| IAM-SNU | Count of user-managed service-account keys (target 0); Workload Identity Federation usage |
| MLA-OSM / MLA-LET | Org sink health, Data Access log config export, SIEM ingest metrics |
| MLA-EVC | SCC compliance report score for NIST 800-53 over time |
| RPL-ABO / RPL-TRC | Backup and DR job reports; restore test records |
| PIY-GIV | Cloud Asset Inventory export (`gcloud asset export`) of the in-boundary folder |

## Terraform specifics

```hcl
resource "google_assured_workloads_workload" "fedramp" {
  compliance_regime = "FEDRAMP_MODERATE"      # or FEDRAMP_HIGH; immutable
  display_name      = "fedramp-boundary"
  location          = var.region                # a US region, e.g. "us-west1" (as in the provider example)
  organization      = var.org_id                # bare numeric org ID
  billing_account   = "billingAccounts/${var.billing_account}"
  provisioned_resources_parent = "folders/${var.parent_folder}"   # parent under which AW creates its folder

  resource_settings {
    display_name  = "fedramp-boundary"
    resource_type = "CONSUMER_FOLDER"
  }
}

locals {
  # The folder Assured Workloads created (not var.parent_folder). Verify with `terraform plan`.
  aw_folder = one([for r in google_assured_workloads_workload.fedramp.resources :
  r.resource_id if r.resource_type == "CONSUMER_FOLDER"])
}

resource "google_org_policy_policy" "no_sa_keys" {
  name   = "folders/${local.aw_folder}/policies/iam.disableServiceAccountKeyCreation"  # no "constraints/" prefix
  parent = "folders/${local.aw_folder}"
  spec { rules { enforce = "TRUE" } }    # boolean constraints only; list constraints use values {}
}
```

- Put all in-boundary projects under the Assured Workloads folder. Resources created
  outside it are outside the boundary.
- These examples target `hashicorp/google` v8 (8.0.0 was released 2026-08-26).
- Google also offers *managed* versions of several constraints, e.g.
  `iam.managed.disableServiceAccountKeyCreation`, `compute.managed.requireOsLogin`,
  `sql.managed.restrictPublicIp`, `compute.managed.vmExternalIpAccess`, and
  `iam.managed.allowedPolicyMembers`. Check which form your org uses.
  `sql.restrictPublicIp` only affects new instances.
- [gcp-org-baseline-tf](https://github.com/DustyStudy/gcp-org-baseline-tf) contains related
  org-baseline patterns.

## Common GCP findings

- Primitive roles (`roles/owner`, `roles/editor`) granted to users or service accounts.
  `allUsers`/`allAuthenticatedUsers` bindings.
- `google_service_account_key` resources: long-lived keys, and the private key is stored in
  plaintext in Terraform state.
- Firewall rules with `source_ranges = ["0.0.0.0/0"]` on 22/3389, or the default network
  still present.
- GCS buckets without `uniform_bucket_level_access`, public access prevention, retention
  policy, or CMEK.
- Cloud SQL with a public IP (`ipv4_enabled = true` without justification), `ssl_mode`
  not `ENCRYPTED_ONLY`/`TRUSTED_CLIENT_CERTIFICATE_REQUIRED`, or no backups/PITR.
- GKE problems:
  - `enable_legacy_abac = true`.
  - No private nodes or master authorized networks.
  - No `workload_identity_config`.
  - `enable_shielded_nodes = false`. The default is true, so flag only an explicit false.
  - No `binary_authorization { evaluation_mode = "PROJECT_SINGLETON_POLICY_ENFORCE" }`.
    The old `enabled` argument is deprecated.
- Data Access audit logs not enabled (`google_*_iam_audit_config`), or no org-level sink.
- Projects created outside the Assured Workloads folder.
