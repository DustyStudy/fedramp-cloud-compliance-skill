# Azure implementation guide for FedRAMP

Starting points for implementation, not proof of compliance. **Before you assert that a
service is authorized, check the live audit-scope list:**
https://learn.microsoft.com/azure/azure-government/compliance/azure-services-in-fedramp-auditscope

## Authorization posture and inheritance

- **Azure (commercial) US regions** and **Azure Government** (US Gov Virginia, Arizona,
  Texas, …) both hold FedRAMP authorizations. Azure Government is the usual choice when
  customers also need DoD IL4/IL5, CJIS, IRS 1075, or screened US-person operations.
  Service coverage differs between the two clouds, and Azure Government lags on some
  services, so check the audit-scope list for **the specific cloud and service**.
- Azure Government is a **separate cloud**. It has its own endpoints
  (`*.usgovcloudapi.net`, `login.microsoftonline.us`), Entra tenant, and portal
  (portal.azure.us).
- **Get Microsoft's FedRAMP packages and CRM:**
  - The Azure Commercial SSP is on the Service Trust Portal (STP).
  - Other artifacts are in a restricted STP section under NDA.
  - Agencies can request the package through the FedRAMP Marketplace, which needs a
    .gov/.mil email.

  The CSP inherits PE and most MA/MP, and nothing for its own tenant
  configuration, identity, logging, or application.
- Every Azure service you use is a **third-party information resource** under
  `MAS-CSO-TPR`.

## Cryptography (CMU, SC-8, SC-12, SC-13, SC-28)

- Microsoft states that Azure services use FIPS-approved *algorithms* backed by validated
  modules such as SymCrypt (CMVP #5313, FIPS 140-3 Level 1 as of 2026-09). A cloud service
  as a whole is never "FIPS validated". For `CMU-CSO-CMD`, list the specific modules and
  certificates.
- FIPS 140-2 certificates moved to the CMVP Historical list on 2026-09-21. Cite active
  140-3 certificates and check their status on csrc.nist.gov before quoting them.
- **Key Vault Premium** (HSM-backed keys; HSM Platform 2 is FIPS 140-3 Level 3) or
  **Managed HSM** (FIPS 140-3 Level 3) for CMKs. Enable purge protection and soft delete,
  and use RBAC (not access policies).
- Use customer-managed keys where the rules or your SDR decisions call for key custody:
  Storage, SQL TDE, Cosmos DB, disk encryption sets, AKS etcd (KMS plugin), and so on.
  Enable Storage infrastructure (double) encryption for Class D if you decided you need it.
- **TLS:** the attribute names differ per resource, as of azurerm v5:
  - Storage: `min_tls_version = "TLS1_2"`, the only value v5 accepts.
  - SQL (`azurerm_mssql_server`) and Redis: `minimum_tls_version = "1.2"`.
  - App Service: `site_config { minimum_tls_version = "1.2" }`. It still accepts 1.0–1.3,
    so check it.

  Disable plain HTTP. On App Service, `https_only` defaults to `false`, so set it
  explicitly.
- **Your own code:** use a validated module. On Linux VMs and AKS nodes, use FIPS-enabled
  images (e.g. AKS `fips_enabled = true` node pools).

## Control family → Azure services

| Family | Primary Azure mechanisms | Customer must still… |
|---|---|---|
| AC | Entra ID RBAC and Azure RBAC; management groups; **PIM** (just-in-time, approval, time-bound); Conditional Access; access reviews; Azure Policy deny effects; private endpoints / `public_network_access_enabled = false` | Role design, reviews, least privilege, break-glass accounts |
| AU | Activity Log + Entra sign-in/audit logs → Log Analytics via **diagnostic settings** (every resource); Microsoft Sentinel; immutable (WORM) storage for archives; VNet flow logs | Event selection, review cadence, retention, access to logs (KSI-MLA-ALA) |
| CA / CM | **Azure Policy regulatory compliance initiatives:** "FedRAMP High" `d5264498-16f4-418a-b659-fa7ef418175f`, "FedRAMP Moderate" `e95f5a9f-57ad-4d03-bb0b-b1d16db93693`, "NIST SP 800-53 Rev. 5" `179d1daa-458f-4e47-8086-2a68d0d6c38f` (Azure Government uses the **same GUIDs** with different, smaller contents, e.g. FedRAMP High has about 185 policies in Gov vs about 709 in commercial. All three default to Audit/AuditIfNotExists effects); **Defender for Cloud** regulatory compliance dashboard; Machine Configuration (guest config); Azure Resource Graph inventory; Update Manager | Baselines, change control, remediation of non-compliant resources, inventory accuracy |
| CP | Azure Backup (immutable vaults, soft delete, cross-region restore); Site Recovery; availability zones; geo-redundant storage | RTO/RPO, restore testing |
| IA | Entra ID with **Conditional Access authentication strength "Phishing-resistant MFA"** (FIDO2/passkeys, Windows Hello for Business, certificate-based auth / PIV/CAC). Managed identities and workload identity federation instead of secrets; block legacy auth | IdP policy, authenticator lifecycle, service principal secret hygiene |
| IR | Defender for Cloud (CSPM + workload plans); Sentinel analytics and playbooks (Logic Apps); Defender XDR | IR plan, PAIN rating, IEC reporting |
| RA / SI | Defender Vulnerability Management / Defender for Servers; Defender for Containers (registry and runtime scanning); Update Manager; Microsoft Purview for data discovery | VER evaluation, VDR timeframes, KEV remediation |
| SC | VNets, NSGs, Azure Firewall Premium, WAF (Front Door / App Gateway), DDoS Protection, Private Link, Key Vault / Managed HSM | Deny-by-default flows, boundary docs, crypto module list |
| SR | ACR image signing with Notation (Notary Project). ACR content trust is deprecated: it can't be enabled on new registries after 2026-05-31, and azurerm v5 removed `trust_policy_enabled`. DevOps security in Defender for Cloud; GitHub Advanced Security | Vendor risk, provenance |
| PE / MA / MP | Inherited from Microsoft for the infrastructure | Your own endpoints and media |

## KSI measure ideas (20x)

| KSI | Example Azure measure |
|---|---|
| CNA-RNT / CNA-MAT | Policy compliance for "no public IP", NSG rules denying internet ingress, private endpoints for PaaS |
| CNA-EIS / SVC-ACM | Policy `deployIfNotExists` / `modify` remediation task history; Machine Configuration compliance |
| IAM-APM | Conditional Access policies using the phishing-resistant authentication strength; sign-in logs showing the auth methods actually used |
| IAM-JIT / IAM-ELP | PIM activation logs, count of permanent privileged assignments (target: break-glass only), access review completion |
| IAM-SNU | Managed identities vs. app registrations with secrets; secret/cert expiry report |
| MLA-OSM / MLA-LET | Sentinel data-connector health; diagnostic settings coverage (Policy "Deploy diagnostic settings…") |
| MLA-EVC | Defender for Cloud regulatory compliance score for the FedRAMP / NIST initiative over time |
| RPL-ABO / RPL-TRC | Backup job reports; documented test restores |
| PIY-GIV | Azure Resource Graph export of all in-boundary resources |

## Terraform specifics

```hcl
provider "azurerm" {
  features {}
  environment = "usgovernment"   # "public" for commercial Azure
}

resource "azurerm_management_group_policy_assignment" "fedramp_high" {
  name                 = "fedramp-high"
  management_group_id  = azurerm_management_group.root.id
  policy_definition_id = "/providers/Microsoft.Authorization/policySetDefinitions/d5264498-16f4-418a-b659-fa7ef418175f"
}
# name: 24 characters max. These three initiatives are audit-only, so no identity is needed.
# If you add DINE/Modify policies, add identity { type = "SystemAssigned" } and then
# location (Terraform requires location whenever identity is set), and grant the identity roles.
```

- Assign the initiative at the management-group level so that new subscriptions inherit
  it. These initiatives only *report* compliance, so pair them with deny/DINE policies to
  actually *enforce* it.
- These examples target `hashicorp/azurerm` v5 (5.0.0 was released 2026-07-27). Several
  names and defaults changed between v4 and v5. Check the v5 upgrade guide against
  existing code.
- [azure-baseline-tf](https://github.com/DustyStudy/azure-baseline-tf) and
  [azure-lighthouse-tf](https://github.com/DustyStudy/azure-lighthouse-tf) contain related
  baseline patterns.

## Common Azure findings

- Storage accounts: `public_network_access_enabled` left at true (the default),
  `allow_nested_items_to_be_public = true` (default `false` in v5, `true` in older
  versions), `min_tls_version` below `TLS1_2` (v4 and earlier), `shared_access_key_enabled
  = true` without justification, or no diagnostic settings.
- Key Vault: `purge_protection_enabled = false`, public network access, or access-policy
  mode instead of RBAC. That means `rbac_authorization_enabled = false` in v5, where the
  argument is required. In v4 it was `enable_rbac_authorization`, and v5 removed it.
- NSG rules with source `*`/`Internet` on 22/3389/admin ports.
- SQL / PostgreSQL flexible server with public access, Entra-only auth disabled
  (`azuread_authentication_only` on `azurerm_mssql_server`;
  `authentication { active_directory_auth_enabled = true, password_auth_enabled = false }`
  on PostgreSQL flexible server), or no auditing.
- App Service without `https_only = true` or with `site_config.minimum_tls_version` below
  1.2.
- AKS: `local_account_disabled = false`, no `azure_active_directory_role_based_access_control`,
  public API server without authorized IP ranges, `fips_enabled` absent where required.
- Resources with no `azurerm_monitor_diagnostic_setting`, so their logs never reach Log
  Analytics / Sentinel. In v5 this resource only accepts `enabled_log` and
  `enabled_metric` blocks.
- Service principals with client secrets where a managed identity would work.
