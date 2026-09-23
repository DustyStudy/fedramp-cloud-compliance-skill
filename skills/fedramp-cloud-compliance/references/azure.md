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
- **Get Microsoft's FedRAMP packages and CRM** from the Service Trust Portal or the FedRAMP
  Marketplace. The CSP inherits PE and most MA/MP, and nothing for its own tenant
  configuration, identity, logging, or application.
- Every Azure service you use is a **third-party information resource** under
  `MAS-CSO-TPR`.

## Cryptography (CMU, SC-8, SC-12, SC-13, SC-28)

- Azure platform services use Microsoft's FIPS 140-validated modules (e.g. Windows
  CNG/SymCrypt). Cite the CMVP certificates Microsoft lists, and don't give a level from
  memory.
- **Key Vault Premium** (HSM-backed keys) or **Managed HSM** for CMKs. Enable
  purge protection and soft delete, and use RBAC (not access policies).
- Use customer-managed keys where the rules or your SDR decisions call for key custody:
  Storage, SQL TDE, Cosmos DB, disk encryption sets, AKS etcd (KMS plugin), and so on.
  Enable Storage infrastructure (double) encryption for Class D if you decided you need it.
- **TLS:** set `min_tls_version = "TLS1_2"` (Storage, App Service, SQL, Redis). Disable
  plain HTTP.
- **Your own code:** use a validated module. On Linux VMs and AKS nodes, use FIPS-enabled
  images (e.g. AKS `fips_enabled = true` node pools).

## Control family → Azure services

| Family | Primary Azure mechanisms | Customer must still… |
|---|---|---|
| AC | Entra ID RBAC and Azure RBAC; management groups; **PIM** (just-in-time, approval, time-bound); Conditional Access; access reviews; Azure Policy deny effects; private endpoints / `public_network_access_enabled = false` | Role design, reviews, least privilege, break-glass accounts |
| AU | Activity Log + Entra sign-in/audit logs → Log Analytics via **diagnostic settings** (every resource); Microsoft Sentinel; immutable (WORM) storage for archives; VNet flow logs | Event selection, review cadence, retention, access to logs (KSI-MLA-ALA) |
| CA / CM | **Azure Policy regulatory compliance initiatives:** "FedRAMP High" `d5264498-16f4-418a-b659-fa7ef418175f`, "FedRAMP Moderate" `e95f5a9f-57ad-4d03-bb0b-b1d16db93693`, "NIST SP 800-53 Rev. 5" `179d1daa-458f-4e47-8086-2a68d0d6c38f` (Azure Government has its own copies. Verify the IDs in the target cloud); **Defender for Cloud** regulatory compliance dashboard; Machine Configuration (guest config); Azure Resource Graph inventory; Update Manager | Baselines, change control, remediation of non-compliant resources, inventory accuracy |
| CP | Azure Backup (immutable vaults, soft delete, cross-region restore); Site Recovery; availability zones; geo-redundant storage | RTO/RPO, restore testing |
| IA | Entra ID with **Conditional Access authentication strength "Phishing-resistant MFA"** (FIDO2/passkeys, Windows Hello for Business, certificate-based auth / PIV/CAC). Managed identities and workload identity federation instead of secrets; block legacy auth | IdP policy, authenticator lifecycle, service principal secret hygiene |
| IR | Defender for Cloud (CSPM + workload plans); Sentinel analytics and playbooks (Logic Apps); Defender XDR | IR plan, PAIN rating, IEC reporting |
| RA / SI | Defender Vulnerability Management / Defender for Servers; Defender for Containers (registry and runtime scanning); Update Manager; Microsoft Purview for data discovery | VER evaluation, VDR timeframes, KEV remediation |
| SC | VNets, NSGs, Azure Firewall Premium, WAF (Front Door / App Gateway), DDoS Protection, Private Link, Key Vault / Managed HSM | Deny-by-default flows, boundary docs, crypto module list |
| SR | ACR with content trust / Notation signing, Defender for DevOps, GitHub Advanced Security | Vendor risk, provenance |
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
  location             = var.location   # required when the initiative contains DINE/modify policies
  identity { type = "SystemAssigned" }
}
```

- Assign the initiative at the management-group level so that new subscriptions inherit
  it. Audit-only initiatives *report* compliance, so pair them with deny/DINE policies to
  actually *enforce* it.
- The user's `azure-baseline-tf` and `azure-lighthouse-tf` repos contain related
  baseline patterns.

## Common Azure findings

- Storage accounts: `public_network_access_enabled`/`allow_nested_items_to_be_public`
  left at true, `min_tls_version` below TLS1_2, `shared_access_key_enabled = true` without
  justification, or no diagnostic settings.
- Key Vault: `purge_protection_enabled = false`, public network access, or access-policy
  mode instead of RBAC.
- NSG rules with source `*`/`Internet` on 22/3389/admin ports.
- SQL / PostgreSQL flexible server with public access, AAD-only auth disabled, or no
  auditing.
- AKS: `local_account_disabled = false`, no `azure_active_directory_role_based_access_control`,
  public API server without authorized IP ranges, `fips_enabled` absent where required.
- Resources with no `azurerm_monitor_diagnostic_setting`, so their logs never reach Log
  Analytics / Sentinel.
- Service principals with client secrets where a managed identity would work.
