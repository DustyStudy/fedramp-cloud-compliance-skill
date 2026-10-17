# Security Policy

## What "security" means for this repo

This is an Agent Skill (Markdown references plus a Python helper script), not a
running service. "Security issue" here means:

- guidance that would lead a user to a weaker configuration than it claims, such
  as a wrong encryption, IAM, logging or partition default;
- a misquoted FedRAMP rule, KSI, or timeframe that understates a requirement;
- `scripts/fedramp.py` doing something other than reading FedRAMP's public data
  and writing its cache or `references/generated/`;
- content in the skill or its generated data that tries to instruct the agent
  (prompt injection).

## Reporting a vulnerability

Please **do not open a public GitHub issue** for a security finding. That
publishes the gap before there's a fix.

Use GitHub's private reporting instead: **Security** tab → **Report a
vulnerability**. Include the file and line, what it says versus what it should
say, and a primary source (FedRAMP, the cloud provider's docs, or the Terraform
provider docs).

## Response expectations

This is a personally maintained public repo with no SLA. Expect an
acknowledgment within a few days, and a fix prioritized ahead of new content
once confirmed.

## Supported scope

Only the latest release and `main` are supported.

## Not in scope

- FedRAMP certification questions. The skill supports implementation and
  documentation work; it is not an assessment and never makes a system compliant.
- Changes FedRAMP or a cloud provider made after the snapshot date shown in
  `references/generated/`. Report those as a normal issue.
