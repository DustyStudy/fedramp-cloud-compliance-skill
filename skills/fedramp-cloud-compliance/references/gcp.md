# Google Cloud implementation guide for FedRAMP

Starting points for implementation, not proof of compliance. **Before you assert that a
service is authorized, check the live list:**
https://cloud.google.com/security/compliance/services-in-scope

## Authorization posture and inheritance

- Google Cloud holds FedRAMP authorizations for many services in US regions. Coverage is
  per service, so check the services-in-scope list.
- **Assured Workloads** enforces a compliance regime on a folder. It restricts resource
  locations, limits the folder to services in scope for that regime, and applies
  personnel/support controls and org policies. The Terraform
  `google_assured_workloads_workload.compliance_regime` values include `FEDRAMP_MODERATE`,
  `FEDRAMP_HIGH`, `IL2`, `IL4`, `IL5`, `CJIS`, `ITAR`, and `IRS_1075`. The regime is
  **immutable**, so choose it before creating projects.
- **Get Google's FedRAMP package and CRM** from the Compliance Reports Manager or the
  FedRAMP Marketplace. The CSP inherits PE and most MA/MP, and nothing for its own IAM,
  configuration, logging, or application.
- Every Google service you use is a **third-party information resource** under
  `MAS-CSO-TPR`.

## Cryptography (CMU, SC-8, SC-12, SC-13, SC-28)

- Google encrypts at rest by default using its BoringCrypto-based FIPS 140-validated
  module. Cite Google's published CMVP certificates rather than a level from memory.
- **Cloud KMS** (software or `HSM` protection level) or **Cloud EKM** for customer-managed
  keys (CMEK). Enforce them with org policies
  `constraints/gcp.restrictNonCmekServices` and `constraints/gcp.restrictCmekCryptoKeyProjects`.
  Set a rotation period on keys.
- **TLS:** use SSL policies with `min_tls_version = "TLS_1_2"` and the `RESTRICTED`/`CUSTOM`
  profile on load balancers. Cloud SQL requires SSL, e.g. `ssl_mode = "ENCRYPTED_ONLY"` or
  stricter.
- **Your own code:** use a validated module. On GKE, check whether the node image and
  your binaries run in FIPS mode.

## Control family → Google Cloud services

| Family | Primary GCP mechanisms | Customer must still… |
|---|---|---|
| AC | Cloud IAM (predefined/custom roles, no basic roles), IAM Conditions, **Privileged Access Manager** (JIT grants), IAM deny policies, org policy `iam.allowedPolicyMemberDomains`, VPC Service Controls perimeters | Role design, reviews, least privilege |
| AU | Cloud Audit Logs (Admin Activity always on; **enable Data Access logs** for in-scope services); aggregated **org-level log sinks** to a locked log bucket (bucket lock / retention policy) or BigQuery; VPC Flow Logs; firewall rules logging | Event selection, review, retention, log access |
| CA / CM | **Security Command Center** (Premium/Enterprise) compliance reporting with NIST 800-53 mappings, Security Health Analytics, posture management; Assured Workloads violation monitoring; Cloud Asset Inventory; OS Config / VM Manager | Baselines, change control, remediation, inventory accuracy |
| CP | Backup and DR Service; regional/multi-regional services; Cloud SQL HA + PITR; GCS object versioning / retention | RTO/RPO, restore testing |
| IA | Cloud Identity / Workspace or a federated IdP with **phishing-resistant 2SV** (security keys / passkeys enforced); Workload Identity Federation instead of service-account keys (`iam.disableServiceAccountKeyCreation`); OS Login with 2FA (`compute.requireOsLogin`) | IdP policy, authenticator lifecycle |
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
  location          = "us"
  organization      = var.org_id
  billing_account   = "billingAccounts/${var.billing_account}"
  provisioned_resources_parent = "folders/${var.parent_folder}"
}

resource "google_org_policy_policy" "no_sa_keys" {
  name   = "${google_folder.boundary.name}/policies/iam.disableServiceAccountKeyCreation"
  parent = google_folder.boundary.name
  spec { rules { enforce = "TRUE" } }
}
```

- Put all in-boundary projects under the Assured Workloads folder. Resources created
  outside it are outside the boundary.
- The user's `gcp-org-baseline-tf` repo contains related org-baseline patterns.

## Common GCP findings

- Primitive roles (`roles/owner`, `roles/editor`) granted to users or service accounts.
  `allUsers`/`allAuthenticatedUsers` bindings.
- `google_service_account_key` resources (long-lived keys).
- Firewall rules with `source_ranges = ["0.0.0.0/0"]` on 22/3389, or the default network
  still present.
- GCS buckets without `uniform_bucket_level_access`, public access prevention, retention
  policy, or CMEK.
- Cloud SQL with a public IP, no SSL enforcement, or no backups/PITR.
- GKE: legacy ABAC, no private cluster/authorized networks, no Workload Identity, Shielded
  Nodes off, or Binary Authorization absent.
- Data Access audit logs not enabled (`google_*_iam_audit_config`), or no org-level sink.
- Projects created outside the Assured Workloads folder.
