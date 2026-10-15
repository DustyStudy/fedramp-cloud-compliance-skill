# Building an AWS GovCloud environment for FedRAMP (Terraform + GitHub Actions)

Use this for a **greenfield build** in `us-gov-west-1` / `us-gov-east-1`. It gives the build
order, the GovCloud-specific steps, and what to check before moving on. Everything built
here also has to pass [terraform-checks.md](terraform-checks.md), and service details are
in [aws.md](aws.md).

Statements about GovCloud behavior were checked against the AWS GovCloud (US) User Guide
on 2026-10-15. Architecture choices (account layout, OU names, hub-and-spoke networking)
are _guidance_. A finished build provides evidence toward controls and KSIs. It doesn't
make the system compliant or certified.

## Build defaults

> _Guidance:_ these are this skill's defaults for generated code, not FedRAMP
> requirements. If the user's program says otherwise, follow it and record the decision
> in the SDR.

- Build ARNs from `data.aws_partition.current.partition`. Never hard-code `arn:aws:` or
  `arn:aws-us-gov:`.
- GovCloud providers use only `us-gov-west-1` and `us-gov-east-1`, with
  `use_fips_endpoint = true` and `allowed_account_ids`. The S3 backend sets
  `use_fips_endpoint = true` as well. The one exception is the commercial account-vending
  step in §1.
- KMS CMKs: `enable_key_rotation = true` on symmetric keys, `deletion_window_in_days`
  between 7 and 30, and key policies that separate key admins from key users.
- S3: all four Block Public Access settings, versioning, server access logging, SSE-KMS,
  and a `Deny` on `aws:SecureTransport = "false"`. The exception is buckets that receive
  S3 server access logs or ALB/NLB access logs directly: those need SSE-S3 in the same
  Region, then replication into the KMS-encrypted archive (terraform-checks.md §5).
- No `0.0.0.0/0` or `::/0` ingress on 22 or 3389. Use SSM Session Manager.
- GitHub Actions authenticate with OIDC. Never use static access keys.
- Run `terraform fmt` and `terraform validate`, then `terraform plan` and review the
  saved plan. Never use `terraform apply -auto-approve` or `destroy -auto-approve`.
- Don't put export-controlled data in account names, emails, OU names, IAM names, tags,
  or policy documents. AWS says this metadata may leave the GovCloud Regions.

## Build order

| Stage | Builds | Done when |
|---|---|---|
| 0. Decide | Type and class, boundary, Regions, IdP, data types | Decisions recorded as SDR entries (§0) |
| 1. Accounts | Paired accounts, GovCloud org, OUs | Every account is in the GovCloud org and in its OU |
| 2. Landing zone | Control Tower or plain Organizations | One owner for every guardrail and trail |
| 3. Bootstrap | State backend, first OIDC roles | Pipeline plans and applies; bootstrap credentials removed |
| 4. Guardrails | SCPs, RCPs, declarative policies | Tested in a staging OU; break-glass still works |
| 5. Logging and security | Org trail, Config, GuardDuty, Security Hub CSPM, Inspector | A test event reaches the archive and a test finding reaches a person |
| 6. Identity | Identity Center, IdP, permission sets, break-glass | Phishing-resistant MFA is enforced; break-glass tested |
| 7. Network | IPAM, TGW, inspection, egress, endpoints, DNS | Flows match the boundary diagram; no direct internet route from workloads |
| 8. Workload baseline | Per-account defaults, backup, patching, scanning | Baseline applied to every account, including new ones |
| 9. Evidence | Inventory and KSI evidence collection | Inventory reconciles with state; evidence runs on schedule |

The pipeline (stage 3) comes before most other stages, so they're built through reviewed
plans rather than from a laptop.

## 0. Decisions before writing code

- Type and class (`program-2026.md`). Crypto expectations follow the class: `CMU-CSO-UVM`
  is MUST for Class D.
- The boundary: which accounts, Regions, and services are in scope (`MAS-CSO-IIR`), and
  the third-party resources (`MAS-CSO-TPR`).
- Home Region. _Guidance:_ use `us-gov-west-1` as the home Region, because the IAM control
  plane, Organizations policy operations, and org-root operations only run there. Use
  `us-gov-east-1` for recovery copies and failover.
- The IdP, and how it enforces phishing-resistant MFA (KSI-IAM-APM).
- Which services you'll use. Check each one on the FedRAMP services-in-scope page and in
  its GovCloud User Guide page before you design around it (feature gaps are below).

## 1. Accounts and the partition model

Verified facts:

- A GovCloud account needs an existing commercial (standard) account, and the account
  holder must meet the US-person and ITAR eligibility requirements.
- `CreateGovCloudAccount` is called from the **commercial** organization's management
  account and is available only in US East (N. Virginia). Each call creates two accounts
  with the same email address:
  - a commercial account for billing and support, which joins the commercial org;
  - a standalone GovCloud account.
- A GovCloud account can join only a GovCloud organization, by invitation. The GovCloud
  org is independent of the commercial one, and its feature set must be "all features".
- No IAM role can delegate access between a GovCloud account and a commercial account.
  Each partition needs its own roles, its own GitHub OIDC providers, and its own state.
- The new GovCloud account gets an `OrganizationAccountAccessRole` (or the `RoleName` you
  pass), which the GovCloud account paired with your commercial management account can
  assume.

In Terraform:

- The commercial step is `aws_organizations_account` with `create_govcloud = true`, run by
  a provider in `us-east-1` against the commercial management account. `govcloud_id`
  returns the GovCloud account ID. Keep this in its own root module and state, with no
  workload resources in it. It's the only commercial-partition code in the build.
- `close_on_deletion` isn't supported for GovCloud accounts. To manage the GovCloud
  account with Terraform, import it into a GovCloud-side `aws_organizations_account`.
- The AWS provider has no resource for invitations or handshakes. Invite and accept with
  the CLI (`aws organizations invite-account-to-organization`, then `accept-handshake` from
  the new account's role), and import the account once it has joined.

_Guidance:_ a typical layout:

| OU | Accounts |
|---|---|
| Root | GovCloud management account. Org, policies, and billing only; no workloads |
| Security | Log archive; security tooling (delegated admin for GuardDuty, Security Hub CSPM, Config, Inspector, Access Analyzer) |
| Infrastructure | Network hub; shared services and CI (pipeline roles, runners) |
| Workloads/Prod, Workloads/NonProd | One account per workload and environment |
| Suspended | Accounts pending closure, with a deny-all SCP |

## 2. Landing zone: Control Tower or plain Organizations

Control Tower in GovCloud (verified):

- It's available in both GovCloud Regions.
- It can't create accounts, including through Account Factory. You create the Audit and
  Log Archive accounts first (§1) and enroll them.
- Account Factory for Terraform (AFT) can't be deployed by new customers in GovCloud.
- Control Tower's RCP controls aren't available. Organizations RCPs are.
- Some controls have no effect in GovCloud, with no error. These include the root-user
  controls and "disallow cross-region networking".

_Guidance:_ for a Terraform-first build, the usual choice is plain Organizations managed
in Terraform. Use Control Tower when the team wants its controls library and dashboard.
Then accept that account creation and enrollment stay outside Terraform, and don't manage
the same trail, Config setup, or SCPs from both Terraform and Control Tower. Whichever you
pick, record who owns each guardrail.

## 3. Bootstrap: state backend and first pipeline roles

1. **State backend.** Create the state bucket and its KMS key with local state, using an
   admin role in the management or CI account. Then move the state into the bucket with
   `terraform init -migrate-state`. Settings are in terraform-checks.md §2: CMK,
   `use_lockfile = true`, versioning, FIPS endpoint.
2. **State layout.** Keep separate state per account, environment, and layer (org,
   security, network, workload), so a plan role only reads the state it needs.
3. **OIDC.** The IAM OIDC provider (`token.actions.githubusercontent.com`, audience
   `sts.amazonaws.com`) has to exist in every account whose role GitHub assumes directly.
   The other option is one CI account whose role chains into roles in the target
   accounts. That works because they're all in the GovCloud partition.
   - GitHub is one of the IdPs whose certificates AWS validates against its own root CAs,
     so `thumbprint_list` isn't used for verification.
   - Trust policies, plan/apply role separation, and reusable-workflow pinning are covered
     in terraform-checks.md §9.
4. **Runner Region.** GovCloud has no global STS endpoint. Set `aws-region` to a GovCloud
   Region in `aws-actions/configure-aws-credentials`, so the job uses the Regional
   endpoint.
5. **Retire the bootstrap.** Once the pipeline can plan and apply its own stack, remove
   the bootstrap admin session or IAM user and its keys. Record the handover as a CM-3
   change.

Done when: the pipeline applies a saved, reviewed plan to the backend's own stack, and no
long-lived keys exist.

## 4. Organization guardrails

GovCloud orgs support SCPs, RCPs, tag policies, and EC2 and S3 declarative policies. They
don't support backup, chat application, or AI services opt-out policies. Run policy-type
operations against `us-gov-west-1`.

_Guidance:_ baseline set:

- **SCPs:**
  - Deny every Region except the two GovCloud Regions, with the usual exceptions for
    services that don't use Regions.
  - Deny `organizations:LeaveOrganization`.
  - Deny stopping, deleting, or changing CloudTrail, Config, GuardDuty, Security Hub CSPM,
    and Access Analyzer, and deny changes to the log archive bucket and its KMS keys,
    except for a named security role.
  - Deny creating IAM users and access keys, except for break-glass.
  - Deny launching instances without IMDSv2 (`ec2:MetadataHttpTokens`).
- **RCPs:** deny access to org resources from principals outside the org
  (`aws:PrincipalOrgID`, with service-principal exceptions), and deny non-TLS access
  (`aws:SecureTransport`). On STS, scope the org-only deny to `sts:AssumeRole` and the
  like. `AssumeRoleWithWebIdentity` (GitHub OIDC) and `AssumeRoleWithSAML` (IdP
  federation) carry no `aws:PrincipalOrgID`, so a blanket deny breaks the pipeline and
  federated sign-in. Constrain those through the role trust policies instead. AWS's
  data-perimeter-policy-examples repo has tested patterns.
- **Declarative policies:** EC2 for IMDSv2 defaults and blocking public AMI and snapshot
  sharing; S3 to keep Block Public Access on.
- SCPs and RCPs don't apply to the management account, so keep workloads out of it.
- Attach new policies to a staging OU first. Check that break-glass and the pipeline
  still work, then attach them to the production OUs. Policy changes go through the
  pipeline like any other change (CM-3, CM-5).

## 5. Logging and security tooling

- **Trusted access and delegated admins.** Enable trusted access with
  `aws_organizations_aws_service_access`, then make the security tooling account the
  admin with each service's own resource where one exists:
  `aws_guardduty_organization_admin_account`, `aws_securityhub_organization_admin_account`,
  `aws_inspector2_delegated_admin_account`. Config and Access Analyzer use
  `aws_organizations_delegated_administrator`. GuardDuty, Security Hub CSPM, and
  Inspector admins are per Region, so set them and their auto-enable configuration
  (e.g. `aws_guardduty_organization_configuration`) in both GovCloud Regions. AWS says to
  check which services support trusted access in the Organizations console in GovCloud.
- **Org trail** (terraform-checks.md §5): all Regions, log file validation, a CMK, data
  events where federal customer data lives, delivered to an Object Lock bucket in the log
  archive account.
- _Guidance:_ **turn on Config, GuardDuty, and Inspector in both GovCloud Regions**, even when one
  Region has no workloads, so activity there is still recorded and detected.
- **GuardDuty in GovCloud** (verified):
  - Runtime Monitoring needs the `com.amazonaws.<region>.guardduty-data-fips` VPC endpoint.
  - Entity lists aren't available; IP address lists are.
  - The `CredentialAccess:IAMUser/CompromisedCredentials` finding isn't available.
  - Several EKS anomaly finding types aren't available.
  - Malware Protection skips Marketplace AMI instances and EC2/EBS recovery points.
- **Alert routing.** EventBridge sends findings above a threshold to the on-call channel
  or ticketing (KSI-MLA-OSM, KSI-IAM-SUS).
- **Prove it works.** Provisioning alone isn't evidence (KSI-MLA-LET, KSI-MLA-RVL).
  - Check that the trail's latest delivery time is recent.
  - Generate GuardDuty sample findings and confirm one reaches a person.
  - Confirm the Config aggregator sees every account in both Regions.

## 6. Identity

- **Identity Center** (both GovCloud Regions; verified):
  - Its admin console, SDK, and CLI use FIPS endpoints.
  - Instance and permission-set ARNs use the `aws-us-gov` partition.
  - Allowlist its domains on any web filter or proxy.
  - Connect the external IdP over SAML with SCIM provisioning.
  - Enforce phishing-resistant MFA at the IdP (KSI-IAM-APM, IA-2(1), IA-2(2)).
  - Set session durations per permission set.
  - Review assignments on a schedule (AC-2, KSI-IAM-ELP).
- **IAM in GovCloud** (verified):
  - One IAM control plane, in `us-gov-west-1`. Each Region has its own data plane.
  - No global STS endpoint.
  - IAM SAML federation uses ACS URL `https://signin.amazonaws-us-gov.com/saml` and
    audience `urn:amazon:webservices:govcloud`.
  - Access Analyzer policy generation isn't available, so write least-privilege policies
    from CloudTrail data or by hand.
- **Root user.** It has no console sign-in and can't use MFA. Access keys are issued only
  on request through AWS Support. Use Organizations root sessions (`RootSessions`) for
  privileged tasks on member accounts.
- **Break-glass.** _Guidance:_ the root user can't serve as break-glass, so keep one or two
  IAM users with hardware MFA in the management account, and alarm on every sign-in.
  SCPs don't restrict the management account, but they do restrict the roles those users
  assume in member accounts. So define a recovery role in each member account (e.g.
  `OrganizationAccountAccessRole`):
  - its trust requires MFA (`aws:MultiFactorAuthPresent`) and only the break-glass
    principals;
  - the deny SCPs exempt it by `aws:PrincipalArn`;
  - an SCP stops anyone else from changing it;
  - test that it can actually recover an account before guardrails roll out, and again
    on a schedule.

## 7. Network

> _Guidance:_ hub-and-spoke is a common SC-7 design, not a FedRAMP requirement.

- **Address planning.** Plan CIDRs with VPC IPAM so ranges don't overlap across accounts
  and Regions.
- **Transit Gateway.** Put it in the network account and share it to workload OUs through
  RAM. Use route tables to segment prod, non-prod, and shared services (KSI-CNA-ULN).
- **Inspection.** Run an inspection VPC with AWS Network Firewall. Set
  `appliance_mode_support = "enable"` on the inspection VPC's TGW attachment, so both
  directions of a flow use the same AZ.
- **Egress.** Centralize it (NAT plus firewall domain allowlists). Workload VPCs have no
  internet gateway (KSI-CNA-RNT, KSI-CNA-MAT).
- **DNS.** Use Route 53 Resolver DNS Firewall and query logging, and private hosted zones
  shared across accounts.
- **VPC endpoints.** Create interface endpoints for the AWS APIs that workloads call.
  Give each an endpoint policy where the service supports one
  (`VpcEndpointPolicySupported`). Where it doesn't, restrict access with security groups
  and the resource or identity policies. Use the FIPS service name where the service offers one
  (e.g. `guardduty-data-fips`), and check the GovCloud endpoints page per service.
  Private connectivity alone doesn't make the TLS FIPS-validated.
- **Runners.** GitHub-hosted runners reach AWS over public endpoints. Self-hosted runners
  in a private subnet reach the VPC endpoints, and are needed if apply has to reach
  private resources. Harden and patch them like any other in-boundary compute.

## 8. Workload account baseline

Apply one baseline module to every account, and to every new account as it joins:

- EBS default encryption with a CMK; account-level S3 Block Public Access; IMDS defaults;
  default VPCs deleted; Access Analyzer; Config recorder; SSM default host management.
- **AWS Backup:** org backup policies aren't available in GovCloud, so deploy backup plans
  per account. Use Vault Lock and a cross-Region or cross-account copy for
  Class C/D (terraform-checks.md §7). _Guidance:_ for Class D, do both: copy to
  `us-gov-east-1` in a separate backup account.
- **Restore testing:** AWS Backup restore testing isn't available in GovCloud. Schedule
  restore jobs yourself and record the measured RTO/RPO (KSI-RPL-TRC, CP-4).
- **Recovery inventory:** include state buckets, KMS keys, DNS, Identity Center
  configuration, and the pipeline itself, not only workload data.
- **Scanning and patching:** Inspector for EC2, ECR, and Lambda (no Lambda code scanning
  in GovCloud), and Patch Manager baselines (terraform-checks.md §8).

## 9. Evidence and the boundary

- Tag every in-boundary resource (`fedramp:boundary`). Tags alone don't define the
  boundary.
- Each week, reconcile three sources: tags, live inventory (AWS Config advanced query or
  Resource Explorer), and `terraform state list`. Unmanaged or untagged resources are
  findings (KSI-PIY-GIV, CM-8).
- Collect the KSI measures in [aws.md](aws.md) on a schedule, and keep the output with its
  collection date. Feed boundary and inventory changes into the CPO and SCN process.

## GovCloud feature gaps that affect this build

Checked 2026-10-15 in the GovCloud User Guide. Re-check before relying on them.

| Service | Gap in GovCloud |
|---|---|
| Organizations | Account creation from GovCloud; backup, chat application, AI opt-out policies |
| Control Tower | Account Factory account creation; AFT for new customers; RCP controls |
| IAM | Root console sign-in and root MFA; global STS endpoint; Access Analyzer policy generation; cross-partition roles |
| AWS Backup | Restore testing; Backup Audit Manager multi-account, multi-Region reporting |
| Inspector | Lambda code scanning; managed code repository scanning (Linux deep inspection plugin isn't FIPS compliant) |
| GuardDuty | Entity lists; CompromisedCredentials finding; some EKS anomaly findings; Marketplace-AMI and EC2/EBS recovery-point malware scans |
| Macie | Not listed for GovCloud on the FedRAMP services-in-scope page (as of 2026-09) |
