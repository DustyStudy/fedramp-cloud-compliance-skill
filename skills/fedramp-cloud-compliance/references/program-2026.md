# FedRAMP program orientation — Consolidated Rules for 2026 (CR26)

Hand-written summary, checked against FedRAMP Consolidated Rules **2026.09.13.02**
and the fedramp.gov/2026 site as of 2026-09-23. Rule IDs are given so you can confirm any
detail with `python scripts/fedramp.py lookup <ID>`. The generated files in
`generated/` are the verbatim source, and this file is only a map to them.

## Vocabulary: old term → 2026 term

| Before CR26 | CR26 |
|---|---|
| FedRAMP Authorization / ATO / P-ATO | FedRAMP **Certification** (Rev5 or 20x *type*) |
| Low / Moderate / High baseline | Rev5 **Class B / C / D**. They loosely align, but FedRAMP says there is "not a direct correlation", because providers tailor and agencies categorize their own systems (FIPS 199/200) |
| FedRAMP Ready | Retired. No Ready submissions after 2026-07-28, so seek **20x Class A** instead. Existing Ready holders MUST convert by the later of their annual-assessment expiry or 2026-11-17 (`FRC-CSF-RDY`). Ready status is removed entirely on 2027-12-31 |
| JAB P-ATO / agency ATO | **Program Certification** (by FedRAMP, no sponsor) vs **Agency Certification** (agency sponsor, Rev5 only) |
| System Security Plan (SSP) | **Certification Package Overview (CPO)** + **Security Decision Record (SDR)**, both human-readable **and** JSON (`CPO-CSO-OVR`, `SDR-CSO-FRR`) |
| Provider POA&M / monthly ConMon deliverables | **VDR/VER** vulnerability detection, evaluation, and reporting (`VER-TFR-MHR` monthly report) + **Ongoing Certification Report** every 3 months (`CCM-OCR-AVL`). Agencies keep POA&Ms only for *agency-owned* actions |
| Significant Change Request (SCR) | **Significant Change Notification (SCN)**: adaptive / transformative / routine recurring (`SCN-CSO-EVA`) |
| Continuous | **Persistently** (FRD-PER): repeated in cycles, status always known |
| 3PAO | FedRAMP **Recognized** independent assessment service (REC ruleset) |

## Certification types, classes, paths

| Type | Class | Program path | Agency path |
|---|---|---|---|
| 20x | A | Required | Unavailable |
| 20x | B | Required | Unavailable |
| 20x | C | Required | Unavailable |
| 20x | D | Coming in 2027 | Unavailable |
| Rev5 | A | Unavailable | Unavailable |
| Rev5 | B | Limited | Generally required |
| Rev5 | C | Limited | Generally required |
| Rev5 | D | Unavailable | Required |

- **Class A (20x only):** for existing commercial products. It requires a completed SOC 2
  Type II, GovRAMP, or FedRAMP Rev5 (including Ready) certification within the past 12
  months (`FRC-CLA-ASF`). It has a mandatory rule subset (`FRC-CLA-MFR`), including KSIs
  CMT-LMC, CNA-RNT, CED-RAT, IAM-AAM, IAM-APM, INR-RIR, and SVC-SIN. FedRAMP's guidance is
  that most new entrants should start here.
- **Classes B/C/D** add assurance, federal process maturity, automation, and cost. FedRAMP
  warns against going straight to C or D without an existing agency contract that
  requires it.
- **You can't hold both program types:** a provider must not seek both Rev5 and 20x
  Program Certification for the same offering (`FRC-CSO-POP`).
- **Temporary Rev5 Program pipelines** (Ready Conversion / Lost Sponsor), for Class B or C
  only, opened 2026-08-10. The CR26 grace period ends 2027-02-19, and the pipelines close
  2027-06-11. Eligibility criteria are on fedramp.gov/2026/providers/start/path.
- **Class vs agency use:**
  - A covers most non-sensitive uses.
  - B covers most Low and some Moderate/High objectives.
  - C covers most Low/Moderate and some High.
  - D covers most use cases (not classified).

### Mapping a user's "Moderate/High" ask
If a user says "we need FedRAMP Moderate", that usually means **Rev5 Class C** (control
baseline) or **20x Class C** (KSIs). Ask which type their agency customer expects. New
Rev5 applications stop on 2027-06-11, so new engagements should default to 20x unless an
agency sponsor requires Rev5.

## Timeline

| Date | Milestone |
|---|---|
| 2026-06-24 | CR26 official launch |
| 2026-07-04 | Optional early adoption begins |
| 2026-07-06 | Initial Implementation Marketplace listings open |
| 2026-07-28 | FedRAMP Ready becomes legacy (no new submissions) |
| 2026-08-03 | 20x Class A pipeline opens |
| 2026-08-10 | Temporary Rev5 Program pipelines (B/C) open |
| 2026-08-31 | 20x Class B & C pipelines open |
| 2026-11-17 | Earliest deadline for existing FedRAMP Ready holders to convert (`FRC-CSF-RDY`; later of this or annual-assessment expiry) |
| 2026-12-07 | VDR and VER mandatory ("Mandated by CISA BOD 26-04"); grace to 2027-03-07 |
| 2027-01-01 | CR26 mandatory for all stakeholders (per-ruleset dates vary; see below) |
| 2027-06-11 | No new Rev5 certification applications accepted |

Each ruleset has its own dates for 20x and for Rev5. They are listed at the top of every
ruleset section in `generated/rules.md`. FedRAMP's 2026.09.22 wording:

- **Maintaining certification:** existing providers SHOULD adopt the ruleset by this date,
  or a corrective action plan is required.
- **Grace period ends:** they MUST have adopted by then, or certification is revoked. For
  some rulesets the grace period is "the first FedRAMP independent assessment started
  after <date>".

Example: existing Rev5 providers SHOULD adopt SDR by 2027-08-01, and MUST adopt it by
their first independent assessment started after 2027-08-01. CMU's Rev5 grace period ends
2027-06-01. Always quote the ruleset-specific date.

## Rulesets at a glance (grep `generated/rules.md` for `## <CODE>`)

| Code | Ruleset | What engineers usually need from it |
|---|---|---|
| FRC | FedRAMP Certification | Package contents (`FRC-CSO-PKG`), JSON schema validity (`FRC-CSO-JSN`), Class A rules, applying, class changes |
| CPO | Certification Package Overview | Replaces the base SSP. Package maintenance cadence: 20x B monthly / C every 2 weeks / D weekly; Rev5 B/C yearly, D every 6 months (`CPO-CSX-CPM`, `CPO-CSF-CPM`) |
| SDR | Security Decision Record | Per-rule explanation + verification + validation + independent V&V; 20x adds KSI measures and metrics |
| MAS | Minimum Assessment Scope | Boundary = every information resource likely to handle, or affect the CIA of, federal customer data (`MAS-CSO-IIR`); flows; third-party resources |
| CMU | Cryptographic Module Use | Document all modules (`CMU-CSO-CMD`). Validated (CMVP) modules: Class A/B MAY, C SHOULD, D MUST (`CMU-CSO-UVM`). Agency tenants SHOULD default to validated crypto (`CMU-CSO-CAT`) |
| SCG | Secure Configuration Guide | Customer-facing guide explaining the security impact of settings |
| VDR | Vulnerability Detection & Response | Mandatory 2026-12-07 (CISA BOD 26-04). Machine V&V cadence: 20x A monthly (SHOULD), B every 7 days, C every 3 days (MUST) (`VDR-TFR-MVX`); Rev5 monthly (B SHOULD, C/D MUST) (`VDR-TFR-MVF`). Non-machine resources every 3 months (`VDR-TFR-NMV`, MUST). Mitigation timeframes by PAIN × internet-reachability × exploitability (`VDR-TFR-PVR`, SHOULD). KEVs per CISA due dates (`VDR-TFR-KEV`, SHOULD) |
| VER | Vulnerability Evaluation & Reporting | PAIN N1–N5 rating (`VER-EVA-EPA`), assume automatable, monthly activity report (`VER-TFR-MHR`), accepted vulnerabilities |
| IEC | Incident Evaluation & Communication | Reportable = affects, or is likely to affect, the **confidentiality or integrity** of federal customer data (`IEC-CSO-EFR`). Availability-only events are not reportable incidents under this rule. Default PAIN 5 unless rated (`IEC-CSO-DPR`). Initial/ongoing/final reports with PAIN-based deadlines. Initial report (`IEC-CSO-IIR`): A/B N1–N2 1 business day, N3–N5 6 h; C N1 1 business day, N2 24 h, N3–N5 1 h; D N1–N2 1 h, N3–N5 15 min |
| SCN | Significant Change Notification | Adaptive: notify within 10 business days after. Transformative: initial plans ≥30 business days before, final plans ≥10 business days before, then within 5 business days after finishing and 5 after verification. Routine recurring: no notification |
| CCM | Collaborative Continuous Monitoring | Ongoing Certification Report every 3 months. Quarterly review meeting (C/D MUST, B SHOULD) |
| IVV | Independent V&V | 20x: all KSIs assessed yearly (B–D). Rev5: all applicable controls over each 3-year cycle |
| CDS | Certification Data Sharing | Public info, trust centers, per-service materials, availability reporting |
| AFC | Addressing FedRAMP Communication | Security inbox, receiving email without disruption, completing required actions |
| MKT | Marketplace Listing | Listing first (`FRC-APP-MLF`), continuous progress |
| AGU / REC | Agency use / assessor recognition | Mostly agency- and assessor-facing |

## 20x Key Security Indicators (10 clusters)

CED (education) · CMT (change mgmt) · CNA (cloud-native architecture) · IAM · INR (incident
response) · MLA (monitoring/logging/auditing) · PIY (policy & inventory) · RPL (recovery
planning) · SCR (supply chain) · SVC (service configuration). There are 46 indicators in
total. Five are **Optional** for Class B but required for Class C: `KSI-CNA-EIS`,
`KSI-MLA-ALA`, `KSI-SVC-PRR`, `KSI-SVC-RUD`, and `KSI-SVC-VCM`. The full text and related controls are in
`generated/ksi.md`.

KSIs are outcome statements. They are validated by assessing the provider's *measures*
(`SDR-CSX-KSI`), which should be automated and produce metrics wherever possible. `SDR-CSX-KMT`
sets the metric requirements by class:
- Class B must supply 30-day and up-to-1-year metric summaries.
- Class C must also supply all daily metric data for up to a year.
- Class D MUST significantly supersede the lower classes, with specifics to be set in the
  20x Phase 4 pilot.

When mapping cloud features to KSIs, name the measure, how often it runs, and where its
output is stored.

## Machine-readable package

JSON Schemas for FedRAMP submissions are at https://github.com/FedRAMP/schemas.
`FRC-CSO-JSN` requires JSON that validates against the schema whenever a rule references
one. The provider-side schemas (as of 2026-09-24) are FedRAMP's own JSON formats:
- Certification Package Overview, Security Decision Record, Ongoing Certification Report
- Vulnerability Detail Report, Accepted Vulnerability Info, Historical VER Activity
- Incident Report, Significant Change Notifications
- Assessor and advisor information, plus common definitions

These are not OSCAL. In CR26, OSCAL appears only in `AGU-AGC-GRC`, which requires
*agency* GRC and inventory tools to produce and ingest OSCAL and JSON. FedRAMP publishes no
mapping from SDR/CPO to OSCAL, so don't invent one. Pre-2026 OSCAL SSP/SAP/SAR/POA&M tooling
targets the legacy process. Check the schemas repo before recommending OSCAL-based
generators.

## Authoritative sources

- Rules site: https://www.fedramp.gov/2026/ (changelog: /2026/changelog/)
- Structured rules: https://github.com/FedRAMP/rules (`fedramp-consolidated-rules.json`)
- LLM-friendly markdown mirror: https://github.com/FedRAMP/2026-markdown
- Schemas: https://github.com/FedRAMP/schemas
- Marketplace data: https://github.com/FedRAMP/marketplace-fedramp-gov-data
