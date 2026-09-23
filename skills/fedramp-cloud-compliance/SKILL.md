---
name: fedramp-cloud-compliance
description: FedRAMP compliance for workloads on AWS, Azure, and Google Cloud under the FedRAMP Consolidated Rules for 2026 (20x and Rev5). Use when mapping NIST SP 800-53 Rev5 controls or 20x Key Security Indicators (KSIs) to cloud services, reviewing Terraform for FedRAMP issues, drafting Security Decision Records / Certification Package Overviews / legacy SSP narratives / customer responsibility matrices, planning a certification path or class (A/B/C/D), or answering questions about FedRAMP rules such as vulnerability response timeframes, incident reporting, significant change notification, continuous monitoring, and cryptographic modules. Triggers include FedRAMP, 20x, KSI, Rev5, Class B/C/D, Low/Moderate/High baseline, 800-53, ATO, 3PAO, ConMon, POA&M, GovCloud, Azure Government, Assured Workloads, FIPS 140.
---

# FedRAMP Cloud Compliance

Helps engineers and GRC teams design, build, review, and document AWS, Azure, and GCP
systems for FedRAMP. The **2026 Consolidated Rules (CR26)** are authoritative. They are
current as of the data snapshot in `references/generated/`, and `scripts/fedramp.py`
can refresh them from FedRAMP's live machine-readable sources.

## Ground rules

0. **Facts vs. guidance.** Rule text, IDs, dates, Terraform arguments, and service facts
   were verified against primary sources on 2026-09-23. Content marked _Guidance_ (KSI
   measure ideas, severity tiers, "usual choice" advice) is a recommendation. Present
   it as a recommendation, never as a FedRAMP requirement.
1. **Cite rule, KSI, and control IDs.** Use IDs such as `VDR-TFR-PVR`, `KSI-IAM-APM`,
   and `AC-2(1)`. Don't paraphrase a requirement without its ID. If a timeframe,
   parameter value, or force word (MUST/SHOULD/MAY) matters, confirm it with
   `python scripts/fedramp.py lookup <ID>`, which prints the official text from
   FedRAMP's current data.
2. **Only FedRAMP sources are authoritative.** For current requirements, rely only on
   the generated references and the lookup script. Both are built from `FedRAMP/rules`
   and `FedRAMP/2026-markdown` (published at fedramp.gov/2026). Older fedramp.gov/docs
   pages, blog posts, and memory of pre-2026 FedRAMP are *historical*; label them as such.
3. **Cloud-provider details change often.** Before telling a user a service "is
   FedRAMP authorized" or "meets" a control, point them to that provider's live
   services-in-scope list (links are in each cloud reference). Treat the cloud mappings
   here as starting points for the implementation, not proof that a control is met.
4. **Separate provider, customer, and shared responsibility.** Whichever cloud they use,
   the CSP inherits only the controls the IaaS/PaaS provider actually implements. The
   rest is theirs.
5. **This does not replace an assessment.** Certification requires FedRAMP (or an
   agency) plus an independent assessment. Never state that something "is compliant".
   Say it "supports" or "provides evidence toward" a rule or control.

## Orientation: what changed in 2026 (read first if the user uses old terms)

- "Authorization" became **Certification**. There are two types: **20x**, which is
  outcome-based and assessed against KSIs, and **Rev5**, the legacy SP 800-53
  control baselines.
- There are four **classes**. Class A is 20x-only and uses SOC 2 Type II, GovRAMP, or
  prior FedRAMP work. Rev5 Classes B/C/D *loosely* align with Low/Moderate/High.
  FedRAMP says there is no direct correlation.
- For the SSP/POA&M replacements, see [references/documentation.md](references/documentation.md):
  - The **Security Decision Record (SDR)** and **Certification Package Overview (CPO)**
    replace the base SSP. Both are human-readable plus JSON.
  - **VDR/VER** vulnerability reporting replaces provider-maintained POA&Ms.
- Key dates:
  - 2026-12-07: VDR/VER vulnerability rules become mandatory (CISA BOD 26-04; grace
    period to 2027-03-07). This is earlier than the general date.
  - 2027-01-01: CR26 becomes mandatory, subject to per-ruleset effective dates.
  - 2027-06-11: FedRAMP stops accepting new Rev5 certification applications.
  - The full timeline is in [references/program-2026.md](references/program-2026.md).

## Pick the reference for the task

| Task | Load |
|---|---|
| Path/class selection, timeline, what each ruleset covers, 20x vs Rev5 | [references/program-2026.md](references/program-2026.md) |
| Exact rule text (VDR, VER, IEC, SCN, CCM, CMU, MAS, SDR, CPO, FRC, …) | `grep` [references/generated/rules.md](references/generated/rules.md) for the rule ID or `## <CODE>` — don't load the whole file (~200 KB) |
| KSI statements and their related 800-53 controls | [references/generated/ksi.md](references/generated/ksi.md) |
| Is control X in Class B/C/D? FedRAMP parameters? | [references/generated/rev5-baselines.md](references/generated/rev5-baselines.md), then `fedramp.py lookup` |
| AWS implementation (GovCloud, FIPS endpoints, Security Hub, Config, KMS…) | [references/aws.md](references/aws.md) |
| Azure implementation (Azure Government, Policy initiatives, Entra, Defender…) | [references/azure.md](references/azure.md) |
| GCP implementation (Assured Workloads, org policy, SCC, VPC-SC…) | [references/gcp.md](references/gcp.md) |
| Reviewing Terraform / IaC | [references/terraform-checks.md](references/terraform-checks.md) + the cloud file |
| SDR entries, CPO, legacy SSP narratives, CRM, incident/vuln reports, SCNs | [references/documentation.md](references/documentation.md) |

## Workflows

### Map a control or KSI to a cloud implementation
1. Run `python scripts/fedramp.py lookup <ID>`. For a KSI, it lists the related 800-53
   controls. For a control, it shows class applicability, FedRAMP parameters, and the
   KSIs that reference it.
2. Open the cloud reference and find the matching family row. Name the concrete
   services and settings, what the cloud provider covers, and what the customer
   must configure or operate.
3. Say what evidence would demonstrate it, such as a config export, policy compliance
   state, a log query, or a Terraform plan. For 20x, favor evidence that is
   machine-generated and produced persistently.

### Review Terraform for FedRAMP issues
1. Identify the target type/class, cloud(s), and whether it runs in a government region
   or in Assured Workloads.
2. Walk through [references/terraform-checks.md](references/terraform-checks.md). Report
   each finding with file:line, the problem, the fix, and the control/KSI/rule IDs.
   Put the highest-risk findings first: public exposure, no encryption or non-validated
   crypto, missing audit logging, wildcard IAM.
3. Don't claim that a clean review means the system is compliant. Also list the
   controls Terraform cannot show at all, like training, IR procedures, and recovery
   testing.

### Draft documentation
Follow [references/documentation.md](references/documentation.md). Write in the
provider's voice, in the present tense, specific to *this* system. Cover who, what,
where, and how often. Mark every assumption `[VERIFY: …]` rather than inventing facts.

### Answer a "what does FedRAMP require…" question
Look up the ruleset in `rules.md` by grepping for its code, confirm the details with
`fedramp.py lookup`, and answer with the rule IDs. Also give the class-specific
variation and the effective or grace date.

## Script reference

All paths in this skill (`scripts/…`, `references/…`) are relative to **this skill's base
directory**, not the user's working directory. Use the absolute path, e.g.
`python "<skill base dir>/scripts/fedramp.py" lookup …`.

```
python <skill>/scripts/fedramp.py lookup KSI-IAM-APM VDR-TFR-PVR "AC-2(1)" sc-13
python <skill>/scripts/fedramp.py search "significant change"
python <skill>/scripts/fedramp.py baseline c AU   # Class C controls in the AU family
python <skill>/scripts/fedramp.py check           # verify cited IDs and links
```

`lookup`, `search`, `baseline`, and `check` are read-only. They fetch FedRAMP's live data
so answers aren't stale, and cache it for 24 hours under `~/.cache/fedramp-skill`.
`build` **overwrites** `references/generated/*`. Run it only when the user asks to refresh
the bundled snapshot; a weekly CI workflow already does this upstream.

**Offline / air-gapped:** the script uses a stale cache if the network fails, and
`FEDRAMP_SKILL_OFFLINE=1` forces cache-only. With no cache, don't use the script. Grep
`references/generated/` (rules, KSIs, definitions, baselines) instead, and say which
snapshot version the answer is based on (shown in each file's header). The snapshot
doesn't include control statement text, so cite the control ID and point to
fedramp.gov for the wording.
