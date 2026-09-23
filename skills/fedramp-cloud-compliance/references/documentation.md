# FedRAMP documentation guide (CR26 and legacy Rev5)

Under CR26, the monolithic SSP is replaced by:

- a **Certification Package Overview (CPO)** (`CPO-CSO-OVR`, `CPO-CSO-MTD`)
- a **Security Decision Record (SDR)** (`SDR-CSO-FRR`, `SDR-CSO-MTD`, and for 20x
  `SDR-CSX-KSI` / `SDR-CSX-KMT`)

Both must be **human-readable and JSON**, and the JSON must be valid against FedRAMP's
schemas (`FRC-CSO-JSN`, https://github.com/FedRAMP/schemas). Existing Rev5 systems can
still hold legacy SSPs until their ruleset grace dates. Check the SDR and CPO rev5 dates
at the top of those sections in `generated/rules.md`.

## Writing rules (apply to every artifact)

1. Write in the provider's voice and the present tense, specific to *this* offering. Name
   systems, services, roles, frequencies, and where evidence lives.
2. Cover who, what, where, when/how often, and how it's verified.
3. Never invent facts. Mark unknowns as `[VERIFY: what's needed]`, and assumptions as
   `[ASSUMPTION: …]`.
4. Separate provider, inherited (IaaS/PaaS), and customer (agency) responsibilities
   explicitly.
5. Use FedRAMP-defined terms precisely (`generated/definitions.md`), e.g. "federal
   customer data", "persistently", and "likely".
6. Cite the rule/KSI/control IDs being addressed.

## Security Decision Record entry (per rule, `SDR-CSO-FRR`)

`SDR-CSO-FRR` requires each applicable rule to have:

- how it's followed, or why not and the resulting risk to customers
- verification
- validation
- independent verification and validation
- responses to assessor comments
- rule-specific artifacts

Template:

```markdown
### <RULE-ID> — <Rule name> (<FORCE>)
**Decision:** Followed | Partially followed | Not followed (accepted by <senior official>, <date>)
**Implementation:** <how the offering meets the rule; systems, services, owners, frequency>
**Risk to customers (if not fully followed):** <explanation>
**Verification:** <why this implementation is appropriate for the rule; who verified, when>
**Validation:** <evidence it is in place and working: automated check / query / report; location; cadence>
**Independent verification & validation:** <assessor, date, result reference>
**Assessor comments & responses:** <…>
**Artifacts:** <rule-specific artifacts listed in the rule, with locations>
```

For **20x KSIs** (`SDR-CSX-KSI`), also include:
- the measures and their objectives
- the cycle for persistent measures
- verification that the automation is accurate and sufficient
- validation that the measures are produced correctly

Metrics by class (`SDR-CSX-KMT`):
- **Class B:** 30-day and up-to-1-year metric summaries.
- **Class C:** also all daily metric data for up to a year.
- **Class D:** requirements are to be set in the 20x Phase 4 pilot.

Example KSI measure line:
> *KSI-IAM-APM:* Measure "% of interactive sign-ins using phishing-resistant
> authenticators", computed daily from <IdP> sign-in logs by <job>, stored in <location>;
> objective 100% for privileged, ≥99% overall; 30-day value: [VERIFY].

## Certification Package Overview (`CPO-CSO-OVR`)

It must include at least the information from the rules below. Run `lookup` on each for
the exact fields:

- `CPO-CSO-MTD` metadata: accountable official, version, last update, and source of update
- `CDS-CSO-PUB`: public information
- `CDS-CSO-SVC`: public service list
- `CDS-CSO-IRP`: relevant policies
- `MAS-CSO-IIR`: information resources in scope. This must be machine-readable, with an
  explanation of how it was derived and the code used.
- `MAS-CSO-FLO`: information flows and security categories
- `MAS-CSO-TPR`: for each in-scope third-party information resource (e.g. IaaS/PaaS
  services that handle or affect federal customer data), give its usage and
  configuration, justification, mitigations, and compensating controls, as
  machine-readable output. The rule doesn't ask for FedRAMP status, but it's useful
  context.
- `CMU-CSO-CMD`: cryptographic modules and their CMVP validation status
- `IVV-CSO-ICP`: independent V&V inclusion
- For Classes B–D, the assessor's overall summary (`CPO-CSO-OSA`)

## Legacy Rev5 control implementation statement (SSP-style)

Use this when a user still needs Rev5 SSP narratives (existing packages, agency request):

```markdown
#### <CONTROL-ID> — <Title>   [Class B/C/D applicability]
**Responsibility:** Provider | Inherited (<IaaS/PaaS>, <package/CRM reference>) | Shared | Customer
**Parameters:** <each FedRAMP-assigned value from `fedramp.py lookup`, e.g. frequency>
**Part a:** <implementation for requirement a>
**Part b:** <…>
**Evidence:** <config export / policy compliance / log query / procedure doc>
```

Address **every lettered part** and **every organization-defined parameter**. Use the
FedRAMP-assigned value where one exists, and never leave an ODP generic.

## Customer Responsibility Matrix (CRM)

Build it as a table with one row per control or KSI where the agency has a
responsibility:

| ID | Provider implements | Customer (agency) must | How the customer configures it | Secure Configuration Guide ref |
|---|---|---|---|---|

Pair it with the **Secure Configuration Guide** (SCG ruleset). The SCG explains the
security impact of settings the agency controls, and agency tenants SHOULD default to
validated crypto (`CMU-CSO-CAT`).

## Vulnerability reporting (replaces provider POA&Ms): VER/VDR

- **Monthly activity report** (`VER-TFR-MHR`). Accepted vulnerabilities must be marked
  (`VER-TFR-MAV`).
- **Non-accepted vulnerabilities** (`VER-RPT-VDT`; JSON schema: FedRAMP Vulnerability
  Detail Report). Required fields, if applicable:
  - tracking ID
  - time and source of detection
  - time of completed evaluation
  - internet-reachable yes/no (IRV)
  - likely exploitable yes/no (LEV)
  - historical and current PAIN (`VER-EVA-EPA`)
  - time and PAIN of each completed reduction
  - estimated time and target PAIN of the next reduction
  - overdue now, or likely to become overdue, with an explanation
  - supplementary information
  - final disposition
- **Accepted vulnerabilities** (`VER-RPT-AVI`; its own schema):
  - tracking ID
  - time and source of detection
  - time of evaluation
  - IRV
  - LEV
  - current PAIN
  - why it is accepted
  - supplementary information
- **Optional internal extras** (not rule fields; keep them out of the schema-validated
  JSON unless the schema allows them): KEV flag and CISA due date (`VDR-TFR-KEV`,
  SHOULD), and the target date from the class's `VDR-TFR-PVR` table (SHOULD).
- Never irresponsibly disclose sensitive details that are likely to enable exploitation.
  But always give all necessary parties enough information for risk-based decisions
  (`VER-RPT-NID`). Public disclosure is optional (`VER-RPT-RPD`).
- Agencies own **agency** POA&Ms. Providers shouldn't convert their vulnerability lists
  into them.

## Incident reports (IEC)

- **Initial report** (`IEC-CSO-IIR`). Fields:
  - federal IR coordinator contact
  - internal tracking ID
  - description
  - timeline (start, detection time and source, reportability evaluation time)
  - historical and current PAIN, with rationale
  - functional impact on federal agency customers (confidentiality and/or integrity) and the federal customer data types affected
  - recovery plan and milestones
  - likely affected agencies
- **Ongoing reports** (`IEC-CSO-OIR`) and a **final report** (`IEC-CSO-FIR`).
- Deadlines depend on class and PAIN. An unrated incident defaults to PAIN 5
  (`IEC-CSO-DPR`). Always look up the current table and never quote from memory.

## Significant Change Notification (SCN)

- Classify every change first (`SCN-CSO-EVA`): class change → new assessment; routine
  recurring → no notice; transformative; otherwise adaptive.
- Adaptive changes: notify within 10 business days after finishing (`SCN-ADP-NTF`).
- Transformative changes:
  - initial plans ≥30 business days before (`SCN-TRF-NIP`)
  - final plans ≥10 business days before (`SCN-TRF-NFP`)
  - within 5 business days after finishing (`SCN-TRF-NAF`)
  - within 5 business days after verification (`SCN-TRF-NAV`)
  - publish updated service documentation (user guides, Marketplace info) within 30
    business days after finishing (`SCN-TRF-UPD`). This does not mean the certification
    package.
  - SHOULD have a third-party assessor review beforehand if human validation is needed
    (`SCN-TRF-TPR`)
- Notifications must be human- and machine-readable (`SCN-CSO-HRM`) and include the
  information in `SCN-CSO-INF`.

## Ongoing Certification Report (CCM)

Every 3 months (`CCM-OCR-AVL`), cover:

- changes to certification data, and planned changes for at least the next 3 months
- accepted vulnerabilities
- transformative changes
- updated recommendations
- the agencies using the offering
- reportable incidents, or an attestation that there were none
- lessons learned

Class C/D must also hold a quarterly review meeting (`CCM-QTR-MTG`).
