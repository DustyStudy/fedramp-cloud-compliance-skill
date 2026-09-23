# Changelog

All notable changes to this repo are documented here. Format loosely
follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
