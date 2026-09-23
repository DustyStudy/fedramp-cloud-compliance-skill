# Changelog

All notable changes to this repo are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
