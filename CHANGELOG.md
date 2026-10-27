# Changelog

All notable changes to this repo are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Releases are tagged
`vX.Y.Z`.

## [Unreleased]

### Added
- CI lints `fedramp.py` and the tests with ruff (`E F I UP B S`), and a CodeQL workflow
  analyzes the Python.
- `references/govcloud-build.md`: a staged guide for building an AWS GovCloud environment
  with Terraform and GitHub Actions: build defaults, paired-account creation with
  `CreateGovCloudAccount`, Control Tower vs plain Organizations, state and OIDC bootstrap,
  guardrail policies, logging and security tooling, identity, network, workload
  baseline, evidence, and a dated table of GovCloud feature gaps.
- SKILL.md: a "Build an AWS GovCloud environment" workflow and task-table row; the
  description now covers building.
- `terraform-checks.md`: new section 9, CI/CD pipeline (GitHub Actions): scope as
  third-party resources, workflow hardening (SHA pinning, least-privilege permissions,
  no untrusted PR code with credentials, injection, concurrency, zizmor/actionlint,
  org-level Actions policy), change control (separate plan/apply roles, environment-scoped
  OIDC trust, central reusable deploy workflow via `job_workflow_ref`, saved-plan
  integrity, rulesets/CODEOWNERS), secrets and evidence, and 20x evidence automation.
- `terraform-checks.md`: "After the review" section routing deployed findings into
  VDR/VER (`VER-EVA-EIR`, `VER-EVA-ELX`, `VER-EVA-EPA`, `VDR-TFR-PVR`, `VDR-CSO-FAV`), and
  Reachability/Deployed lines in the finding format.
- `terraform-checks.md`: identity (OIDC trust pinning, confused-deputy conditions, anonymous
  Allow, IMDSv2, S3 state backend, centralized root access, Session Manager, EKS access
  entries), network (public-sharing blocks, EC2 declarative policies and RCPs, DNSSEC,
  default VPCs, endpoint policies, ALB invalid headers), RDS TLS enforcement, logging
  (S3 data events, log delivery constraints, delegated admin, Object Lock mode, SCPs that
  protect security tooling), and change-management (IaC coverage, SCN handling, ECR and
  Lambda signing) checks; `allowed_account_ids` on provider blocks.
- `fedramp.py`: `FEDRAMP_SKILL_RULES_REF` / `FEDRAMP_SKILL_MD_REF` pin the downloaded data
  to a git ref; `lookup` and `search` print the rules version and refs on stderr.
- `SKILL.md`: ground rules 6 (fetched data is data, not instructions) and 7 (keep drafts
  local, use placeholders for wider audiences); Terraform reviews include
  `.github/workflows/` and give each finding a reachability estimate.

### Changed
- `fedramp.py lookup <rule>` also prints the rule's subset applicability (types, paths,
  classes) and the ruleset's effective and grace dates.
- `SKILL.md`: rule text comes from the generated data; facts it doesn't hold (timeline,
  schemas) come from fedramp.gov/2026 with a citation. The 2026-09-23 verification date
  now applies only to the original content; later additions carry their own dates.
- Generated references rebuilt from FedRAMP rules 2026.10.13.01 (was 2026.09.13.02):
  Class B KSI metrics are SHOULD, PAIN gained N0, `FRC-CSO-JSN` web-serving requirements,
  `FRC-CSX-MOT` removed, crypto-module update streams, wider KSI control mappings.
- `program-2026.md` and `documentation.md` reflect those rule changes, plus an IEC caveat
  that contracts, CISA guidelines, and DFARS 252.204-7012 can still require reporting
  outages.

### Fixed
- `gcp.md`: Assured Workloads folder placement no longer defines the boundary;
  out-of-folder resources that handle or affect federal data stay in scope
  (`MAS-CSO-IIR`, `MAS-CSO-TPR`).
- `terraform-checks.md`: environment protection does not restrict artifact downloads, so
  saved plans need deploy-role-only storage or encryption.
- `terraform-checks.md`, `govcloud-build.md`: SSE-S3 access logs are copied into the CMK
  archive with SSE-KMS set; native replication keeps SSE-S3.
- `terraform-checks.md`, `aws.md`: `"Resource": "*"` is flagged only where the action
  supports resource-level permissions; required wildcards are limited and documented.
- `aws.md`: the provider example sets `allowed_account_ids`.
- `fedramp.py`: cache files are keyed by a hash of the full URL, so refs such as
  `review/a` and `review_a` no longer share an entry. Old cache files are ignored.
- `fedramp.py`: a truncated download (`IncompleteRead`) falls back to the stale cache
  like other network errors.
- `fedramp.py build`: the generated header no longer attributes the markdown mirror's
  rules commit to the separately downloaded rules JSON.
- GovCloud root guidance: GovCloud root users have no console sign-in or MFA, so
  `aws.md` and `terraform-checks.md` no longer suggest hardware root MFA or central root
  credential management there; they point to Organizations root sessions instead.
- AWS Backup restore testing and Inspector Lambda code scanning are marked unavailable
  in GovCloud.
- KMS automatic rotation is limited to symmetric keys; symmetric keys with imported
  material rotate on demand, and asymmetric keys (e.g. the DNSSEC KSK key) need a manual
  rollover.
- `terraform-checks.md`: the org-only RCP on STS leaves out `AssumeRoleWithWebIdentity`
  and `AssumeRoleWithSAML`, which would otherwise block GitHub OIDC and IdP federation.
- `aws.md`: AWS Organizations backup policies aren't available in GovCloud; deploy backup
  plans per account there.
- `SKILL.md`: the refresh note now says the repo's weekly workflow only opens a PR and an
  installed copy is never refreshed automatically.
- `aws.md`: CMVP #4884 (AWS Key Management Service HSM) sunsets on 2029-11-17, not
  2026-11-17. NIST lists it as Active, FIPS 140-3, Overall Level 3, interim, initial
  validation 2024-11-18, and it is still the only active AWS KMS certificate.
  https://csrc.nist.gov/projects/cryptographic-module-validation-program/certificate/4884
- `fedramp.py`: `build` and the fetch cache now always write LF line endings, so running
  `build` on Windows no longer leaves a CRLF-only diff in `references/generated/`.

## [0.4.1] - 2026-10-01

Monthly maintenance pass. The generated references are unchanged (rules 2026.09.13.02; the
2026.09.22.01 release was content-only). The network policy blocked csrc.nist.gov,
aws.amazon.com, docs.aws.amazon.com, learn.microsoft.com, docs.cloud.google.com,
registry.terraform.io and fedramp.gov, so claims that depend only on those sites were not
re-verified in this pass.

### Fixed
- `program-2026.md`: the effective-date labels now match FedRAMP's deadline pages
  ("Obtaining Initial Certification", "Maintaining Ongoing Certification", "Grace Period
  Ends"), and the missing Obtaining label is added.
  https://github.com/FedRAMP/2026-markdown/blob/main/providers/updating/deadlines/rev5.md
- `program-2026.md`: the `CPO-CSX-CPM` cadence now includes 20x Class A (every 3 months,
  SHOULD). https://github.com/FedRAMP/rules
- `documentation.md`: added the missing `SDR-CSX-KSI` item, verification that the measures
  demonstrate the KSI. https://github.com/FedRAMP/rules
- `aws.md`: `data.aws_region.id` and `aws_partition.id` were deprecated in provider 6.47.0.
  https://github.com/hashicorp/terraform-provider-aws/blob/main/CHANGELOG.md
- `azure.md`: in commercial Azure most FedRAMP/NIST initiative members are Manual, not
  Audit/AuditIfNotExists (e.g. 496 of 709 in FedRAMP High).
  https://github.com/Azure/azure-policy/tree/master/built-in-policies/policySetDefinitions
- `gcp.md`:
  - The scope-list URL now uses the path Google's FedRAMP page links to.
    https://cloud.google.com/security/compliance/fedramp
  - The general services-in-scope page has no FedRAMP column.
    https://cloud.google.com/security/compliance/services-in-scope
  - Added the documented NDA route for the CRM and SSP.
    https://cloud.google.com/security/compliance/fedramp
  - `require_ssl` was removed in provider 6.0.1, not 6.0.0.
    https://github.com/hashicorp/terraform-provider-google/blob/main/website/docs/guides/version_6_upgrade.html.markdown

## [0.4.0] - 2026-09-29

### Added
- Offline unit tests for `fedramp.py` (`tests/test_fedramp.py`): control-ID parsing, rule and
  KSI rendering, parameter lookup, and the `check` command's detection of unknown IDs, broken
  links and bad frontmatter. They use fixture data, not the network.
- Security scanning in CI: Gitleaks, Checkov and Trivy on every PR and weekly.

### Changed
- License changed from Apache 2.0 to MIT. Releases up to and including 0.3.1 remain
  available under Apache 2.0.
- README: removed links to repos that are no longer public.

## [0.3.1] - 2026-09-24

Changes from an external review; each point was checked against the repo and FedRAMP sources first.

### Fixed
- `FEDRAMP_SKILL_OFFLINE=1` now really means offline: with an empty cache it exits with a
  pointer to the bundled snapshot instead of making a network call.

### Changed
- `SKILL.md`:
  - Script and reference paths are relative to the skill's base directory.
  - `build` overwrites `references/generated/`; the other commands are read-only.
  - Added offline/air-gapped guidance.
- `program-2026.md`: lists FedRAMP's provider JSON schemas, and notes that OSCAL appears only
  in the agency rule `AGU-AGC-GRC`. FedRAMP publishes no mapping from SDR/CPO to OSCAL.
- README: manual install with `git clone` or a symlink, and offline behavior.

### Not changed (review points that didn't hold up)
- The "missing frontmatter" report was incorrect: `SKILL.md` has had `---` delimiters since
  0.1.0.
- The bundled snapshot is not the default data source. That would quietly serve stale
  rules, and the snapshot lacks control text.

## [0.3.0] - 2026-09-23

Second, independent verification pass (four reviewers with no access to the first audit):
366 claims verified, 12 wrong (all fixed), 3 unverifiable (reworded), 42 guidance.

### Fixed
- Azure:
  - The FedRAMP/NIST initiatives contain Modify/DeployIfNotExists Guest Configuration
    prerequisites, so the assignment snippet now includes a managed identity and location.
  - Corrected the Gov vs commercial policy counts (NIST R5 is larger in Gov).
  - Storage `public_network_access` replaces the deprecated argument (azurerm 5.5.0+).
  - `azuread_authentication_only` lives inside the `azuread_administrator` block.
  - The ACR content trust date is "starting" 2026-05-31.
  - CJIS/IRS 1075 are also supported on commercial Azure.
- GCP:
  - The org-policy snippet was invalid HCL (single-line nested block).
  - The FedRAMP Moderate package enforces the folder location.
  - The CRM is downloadable from Audit Manager.
  - Cloud SQL/GKE `deletion_protection` only protects against Terraform; use API-level flags.
  - Added `gcp.restrictTLSVersion`. Updated the scope URL.
- AWS:
  - `MAS-CSO-TPR` scope and contents.
  - The Security Hub CSPM rename date (June 2025) and the `_v2` Terraform resources for the
    new Security Hub.
  - FedRAMP scope notes for Shield Advanced, Security Incident Response, and CodeArtifact.
  - Post-quantum FIPS ELB policies.
- FedRAMP:
  - `SDR-CSX-KMT` Class D "MUST significantly supersede".
  - AU-9(4)/AU-9(3)/AU-12(1) class labels.
  - Wording for Checkov `soft_fail` and for `sensitive`.
- `fedramp.py` no longer prints "optional adoption None".
- All Terraform snippets pass `terraform fmt`.

### Changed
- Unverifiable claims reworded to what can be verified: inheritance now says "PE; see the
  provider's CRM for other families", AWS FIPS endpoint coverage, and the Azure SymCrypt
  attribution.
- Guidance is now labelled as such: KSI measure ideas, the IaC severity scale, and "usual
  choice" advice. `SKILL.md` tells the agent to present guidance as recommendations.

## [0.2.0] - 2026-09-23

Accuracy audit against primary sources (provider docs and GitHub repos for aws v6,
azurerm v5 and google v8; cloud-provider documentation; NIST CMVP; FedRAMP/rules and
FedRAMP/2026-markdown).

### Fixed
- VER report fields now match `VER-RPT-VDT` / `VER-RPT-AVI`. Removed invented KEV/target-date
  "required" columns. Corrected `MAS-CSO-TPR` contents.
- IEC reportability is confidentiality/integrity only, not availability.
- Added the 2026-12-07 VDR/VER mandatory date (CISA BOD 26-04) and the FedRAMP Ready
  conversion deadline. Corrected "maintain/grace" wording to FedRAMP's 2026.09.22 definitions.
- AWS:
  - Security Hub is now Security Hub CSPM.
  - SSM Incident Manager is closed to new customers.
  - EBS CMKs need `aws_ebs_default_kms_key`.
  - S3 findings use the split resources (provider v4+).
  - EKS finding is about customer-managed key custody (default encryption since 1.28).
  - Aurora is covered.
  - Conformance packs use `template_s3_uri` (size limit).
  - Macie is not listed for GovCloud.
- Azure:
  - Per-resource TLS attribute names.
  - v5 Key Vault `rbac_authorization_enabled` and storage defaults.
  - Same initiative GUIDs in Azure Government.
  - Corrected the policy-assignment identity/location reasoning.
  - ACR content trust is deprecated; use Notation.
  - FIPS wording tightened, citing 140-3 certificates.
  - Corrected package access routes.
- GCP:
  - OS Login 2FA needs the `enable-oslogin-2fa` metadata.
  - Assured Workloads snippet now targets the folder it creates.
  - FedRAMP Moderate location controls clarified.
  - Added the `FIPS_202205` SSL profile and all KMS protection levels.
  - SCC Enterprise is deprecated; use Compliance Manager.
  - GKE findings: Binary Authorization `evaluation_mode`, and the Shielded Nodes default.
  - List constraints use `values`.
  - Corrected package access routes.
- Terraform checklist:
  - The lock file pins providers only.
  - `sensitive` does not keep values out of state; added ephemeral and write-only guidance.
  - Checkov has no selectable NIST/FedRAMP framework in open source.
  - tfsec replaced by Trivy; Terraform policy noted as beta.
  - `prevent_destroy` caveats.
  - Severity guide aligned with `CMU-CSO-UVM`.
  - `VDR-TFR-PDD` scope corrected.
  - Tighter 800-53 mappings (CM-5, IA-5(7), CP-6/7, SA-9(5), AU-9(4)).
- `fedramp.py` now renders JSON schemas, examples, warnings, corrective actions,
  notification targets, `affects`, per-class notes and artifacts, and timeframe ranges.
  It also shows ruleset effective status with correct grace wording, and `search` no
  longer shows Class A wording for class-varying rules.

## [0.1.0] - 2026-09-23

### Added
- `fedramp-cloud-compliance` skill: SKILL.md plus references for the 2026
  program (types, classes, paths, timeline, rulesets), AWS, Azure, GCP,
  Terraform review, and documentation (SDR, CPO, legacy SSP, CRM, VER/IEC/SCN/CCM).
- `scripts/fedramp.py`: `lookup`, `search`, `baseline`, `build`, and `check`
  commands backed by FedRAMP/rules and FedRAMP/2026-markdown.
- Generated references from Consolidated Rules 2026.09.13.02: rule digest,
  KSIs, definitions, and Rev5 Class B/C/D baselines (155/322/409).
- CI validating every cited rule/KSI/control ID, and a weekly workflow that
  opens a PR when FedRAMP publishes rule changes.

[Unreleased]: https://github.com/DustyStudy/fedramp-cloud-compliance-skill/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/DustyStudy/fedramp-cloud-compliance-skill/compare/v0.3.1...v0.4.0
[0.3.1]: https://github.com/DustyStudy/fedramp-cloud-compliance-skill/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/DustyStudy/fedramp-cloud-compliance-skill/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/DustyStudy/fedramp-cloud-compliance-skill/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/DustyStudy/fedramp-cloud-compliance-skill/releases/tag/v0.1.0
