#!/usr/bin/env python3
"""Build and query FedRAMP reference data from FedRAMP's official machine-readable sources.

Sources (both published by FedRAMP on GitHub):
  - FedRAMP/rules         fedramp-consolidated-rules.json  (rules, KSIs, FedRAMP control parameters)
  - FedRAMP/2026-markdown reference/controls/*.md           (NIST SP 800-53 Rev5 text + Class B/C/D baselines)

Usage:
  fedramp.py lookup <ID> [<ID> ...]   Print official text for a KSI, rule, or control ID.
                                       e.g. KSI-IAM-APM, VDR-TFR-NMV, AC-2(1), ac-2.1, SC-13
  fedramp.py search <text>            Case-insensitive search across KSIs and rule statements.
  fedramp.py build [--out DIR]        Regenerate references/generated/*.md.
  fedramp.py baseline <b|c|d> [FAM]   List controls in a Rev5 class baseline (optionally one family).
  fedramp.py check                    Verify every rule/KSI/control ID cited in the skill's docs exists.

Stdlib only. Downloads are cached for 24h in ~/.cache/fedramp-skill (override: FEDRAMP_SKILL_CACHE).
Set FEDRAMP_SKILL_OFFLINE=1 to use the cache regardless of age.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

RULES_URL = "https://raw.githubusercontent.com/FedRAMP/rules/main/fedramp-consolidated-rules.json"
MD_BASE = "https://raw.githubusercontent.com/FedRAMP/2026-markdown/main/"
SOURCES_URL = MD_BASE + "_sources.json"
SITE = "https://www.fedramp.gov/2026/"

CONTROL_FAMILIES = {
    "AC": "access-control",
    "AT": "awareness-and-training",
    "AU": "audit-and-accountability",
    "CA": "assessment-authorization-and-monitoring",
    "CM": "configuration-management",
    "CP": "contingency-planning",
    "IA": "identification-and-authentication",
    "IR": "incident-response",
    "MA": "maintenance",
    "MP": "media-protection",
    "PE": "physical-and-environmental-protection",
    "PL": "planning",
    "PM": "program-management",
    "PS": "personnel-security",
    "PT": "personally-identifiable-information-processing-and-transparency",
    "RA": "risk-assessment",
    "SA": "system-and-services-acquisition",
    "SC": "system-and-communications-protection",
    "SI": "system-and-information-integrity",
    "SR": "supply-chain-risk-management",
}
FAMILY_NAMES = {k: v.replace("-", " ").title().replace(" And ", " and ").replace(" Of ", " of ") for k, v in CONTROL_FAMILIES.items()}
FAMILY_NAMES["PT"] = "PII Processing and Transparency"

CACHE = Path(os.environ.get("FEDRAMP_SKILL_CACHE", Path.home() / ".cache" / "fedramp-skill"))
TTL = 24 * 3600


# --------------------------------------------------------------------------- fetching

def fetch(url: str) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / re.sub(r"[^A-Za-z0-9._-]", "_", url.split("githubusercontent.com/")[-1])
    offline = os.environ.get("FEDRAMP_SKILL_OFFLINE") == "1"
    if path.exists() and (offline or time.time() - path.stat().st_mtime < TTL):
        return path.read_text(encoding="utf-8")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fedramp-cloud-compliance-skill"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8")
    except OSError as exc:
        if path.exists():
            print(f"warning: {url} unreachable ({exc}); using stale cache", file=sys.stderr)
            return path.read_text(encoding="utf-8")
        raise SystemExit(f"error: cannot download {url}: {exc}")
    path.write_text(text, encoding="utf-8")
    return text


def load_rules() -> dict:
    return json.loads(fetch(RULES_URL))


def load_sources() -> dict:
    try:
        return json.loads(fetch(SOURCES_URL))
    except (SystemExit, json.JSONDecodeError):
        return {}


# --------------------------------------------------------------------------- control IDs

CTRL_RE = re.compile(r"^\s*([A-Za-z]{2})[-_ ]?0*(\d+)(?:\s*[(.\-_ ]\s*0*(\d+)\)?)?\s*$")


def parse_control_id(text: str):
    m = CTRL_RE.match(text)
    if not m or m.group(1).upper() not in CONTROL_FAMILIES:
        return None
    return m.group(1).upper(), int(m.group(2)), int(m.group(3)) if m.group(3) else None


def fmt_control(fam: str, num: int, enh: int | None) -> str:
    return f"{fam}-{num}" + (f"({enh})" if enh else "")


def ctl_key(fam: str, num: int, enh: int | None) -> str:
    """Key format used in the rules JSON CTL section, e.g. AC-06-01."""
    return f"{fam}-{num:02d}" + (f"-{enh:02d}" if enh else "")


HEADING_RE = re.compile(r"^## ([A-Z]{2})-(\d+)(?: \((\d+)\))? \((.+?)\) \{ #")


def load_controls() -> dict:
    """Return {(fam,num,enh): {"title", "classes", "body"}} from FedRAMP/2026-markdown."""
    controls = {}
    for fam, slug in CONTROL_FAMILIES.items():
        text = fetch(f"{MD_BASE}reference/controls/{slug}.md")
        sections = re.split(r"(?m)^(?=## [A-Z]{2}-\d+)", text)
        for sec in sections[1:]:
            m = HEADING_RE.match(sec)
            if not m:
                continue
            key = (m.group(1), int(m.group(2)), int(m.group(3)) if m.group(3) else None)
            classes = re.findall(r'subset-applicability__tag">Class ([A-D])', sec)
            body = sec.split("\n", 1)[1]
            body = re.sub(r"<div.*?</div>", "", body, flags=re.S)
            body = body.split("**External Link", 1)[0].split("!!! info", 1)[0]
            body = re.sub(r"(?m)^!!! quote \"\"\s*$", "", body)
            body = re.sub(r"(?m)^    ", "", body)
            body = re.sub(r"\n\s*---\s*\n", "\n", body)
            body = re.sub(r"\n{3,}", "\n\n", body).strip()
            controls[key] = {"title": m.group(4), "classes": sorted(set(classes)), "body": body}
    return controls


# --------------------------------------------------------------------------- rules helpers

def iter_rules(data: dict):
    """Yield (family_code, family_info, scope, subset, rule_id, rule)."""
    for fam, v in data["FRR"].items():
        for scope, subsets in v["data"].items():
            for subset, rules in subsets.items():
                for rid, rule in rules.items():
                    yield fam, v["info"], scope, subset, rid, rule


def iter_ksis(data: dict):
    for code, cluster in data["KSI"].items():
        for kid, ind in cluster["indicators"].items():
            yield code, cluster, kid, ind


def timeframe(r: dict) -> str:
    num, typ = r.get("timeframe_num"), r.get("timeframe_type")
    if typ and num is not None:
        return f" _(timeframe: {num} {typ})_"
    if typ:
        return f" _(timeframe: {typ})_"
    return ""


def pain_lines(pt: dict | None, indent: str = "") -> list[str]:
    """Render PAIN (Potential Agency Impact N-rating) timeframe tables."""
    out = []
    for n, entries in (pt or {}).items():
        parts = [f"{e['description']} {e['timeframe_num']} {e['timeframe_type']}" for e in entries.values()]
        if parts:
            out.append(f"{indent}- PAIN {n}: " + "; ".join(parts))
    return out


def rule_lines(rid: str, r: dict) -> list[str]:
    out = [f"### {rid} — {r['name']}" + (f" ({r['force']})" if r.get("force") else "")]
    if r.get("statement"):
        out.append(r["statement"] + timeframe(r))
    for bullet in (r.get("following_information") or []) + (r.get("following_information_bullets") or []):
        out.append(f"- {bullet}")
    out += pain_lines(r.get("pain_timeframes"))
    for cls, cv in (r.get("varies_by_class") or {}).items():
        stmt = cv.get("statement", "")
        force = f" ({cv['force']})" if cv.get("force") else ""
        out.append(f"- **Class {cls.upper()}{force}:** {stmt}{timeframe(cv)}".rstrip())
        for bullet in cv.get("following_information", []) or []:
            out.append(f"    - {bullet}")
        out += pain_lines(cv.get("pain_timeframes"), "    ")
        if cv.get("rev5_controls_list"):
            out.append(f"    - Rev5 controls: {', '.join(cv['rev5_controls_list'])}")
    for note in [r["note"]] if r.get("note") else (r.get("notes") or []):
        out.append(f"- _Note:_ {note}")
    arts = (r.get("artifacts") or {}).get("all")
    if arts:
        out.append("- _Evidence artifacts:_ " + " | ".join(arts))
    if r.get("reference_url"):
        out.append(f"- _Reference:_ {r.get('reference', '')} {r['reference_url']}".rstrip())
    return out


def applicability(info: dict) -> list[str]:
    out = []
    for name, sub in (info.get("subsets") or {}).items():
        a = sub.get("applicability", {})
        out.append(
            f"- Subset **{name}** ({sub.get('name', '')}): types {'/'.join(a.get('types', []))}; "
            f"paths {'/'.join(a.get('paths', []))}; classes {'/'.join(a.get('classes', []))}; "
            f"affects {', '.join(a.get('affects', []))}"
        )
    for typ in ("20x", "rev5"):
        eff = (info.get(typ) or {}).get("effective")
        if eff:
            d = eff.get("date", {})
            g = d.get("grace", {})
            out.append(
                f"- **{typ}** — {eff.get('is')}; obtain {d.get('obtain')}, maintain {d.get('maintain')}, "
                f"optional adoption {d.get('optional_adoption')}, grace ends {g.get('default')}"
                + (" (or next assessment)" if g.get("until_next_assessment") else "")
            )
    if info.get("effective") and not any(info.get(t) for t in ("20x", "rev5")):
        eff = info["effective"]
        out.append(f"- Effective: {eff.get('is')} {json.dumps(eff.get('date', ''))}")
    return out


def ksi_statement(ind: dict) -> str:
    if ind.get("statement"):
        return ind["statement"]
    return "\n".join(f"- **Class {c.upper()}:** {v.get('statement', '')}" for c, v in (ind.get("varies_by_class") or {}).items())


def ksi_controls(ind: dict) -> str:
    ctrls = []
    for c in ind.get("controls", []):
        p = parse_control_id(c)
        ctrls.append(fmt_control(*p) if p else c.upper())
    return ", ".join(ctrls)


def ctl_extras(data: dict, key3) -> list[str]:
    fam, num, enh = key3
    entry = data.get("CTL", {}).get(fam, {}).get(ctl_key(fam, num, enh))
    if not entry:
        return []
    out = []

    def emit(e: dict, prefix: str = ""):
        for p in e.get("parameters", []) or []:
            out.append(f"- {prefix}FedRAMP parameter `{p.get('parameterId')}`: {p.get('value')}")
        for g in e.get("guidance", []) or []:
            out.append(f"- {prefix}FedRAMP guidance: {g}")

    emit(entry)
    for cls, cv in (entry.get("varies_by_class") or {}).items():
        emit(cv, f"Class {cls.upper()} ")
    return out


# --------------------------------------------------------------------------- build

def header(title: str, src: dict, version: str) -> list[str]:
    rules_sha = src.get("rules", {}).get("sha", "unknown")[:12]
    site_sha = src.get("site", {}).get("sha", "unknown")[:12]
    return [
        f"# {title}",
        "",
        "<!-- GENERATED by scripts/fedramp.py build — do not edit by hand. -->",
        f"_Generated from FedRAMP Consolidated Rules **{version}** "
        f"(FedRAMP/rules@{rules_sha}, FedRAMP/2026-markdown site@{site_sha})._",
        "_Authoritative source: https://www.fedramp.gov/2026/ — verify anything load-bearing with "
        "`scripts/fedramp.py lookup <ID>`, which pulls the live data._",
        "",
    ]


def build(out_dir: Path) -> None:
    data = load_rules()
    src = load_sources()
    version = data["info"]["version"]
    controls = load_controls()
    out_dir.mkdir(parents=True, exist_ok=True)

    # KSIs -------------------------------------------------------------------
    lines = header("FedRAMP 20x Key Security Indicators (KSIs)", src, version)
    lines += ["KSIs apply to the 20x certification type. Each indicator lists its related SP 800-53 Rev5 controls.", ""]
    last = None
    for code, cluster, kid, ind in iter_ksis(data):
        if code != last:
            last = code
            lines += [f"## KSI-{code} — {cluster['name']}", ""]
        lines += [f"### {kid} — {ind['name']}", ksi_statement(ind), ""]
        if ind.get("controls"):
            lines += [f"Related controls: {ksi_controls(ind)}", ""]
    (out_dir / "ksi.md").write_text("\n".join(lines), encoding="utf-8")

    # Rules ------------------------------------------------------------------
    lines = header("FedRAMP Consolidated Rules for 2026 — rule digest", src, version)
    lines += [
        "One section per ruleset. Search by rule ID (e.g. `VDR-TFR-NMV`) or ruleset code (e.g. `## SCN`).",
        "Force words (MUST/SHOULD/MAY) are FedRAMP-defined terms; class-varying rules show each class.",
        "",
    ]
    seen = set()
    for fam, info, scope, subset, rid, rule in iter_rules(data):
        if fam not in seen:
            seen.add(fam)
            lines += ["", f"## {fam} — {info['name']}", "", info.get("purpose", ""), ""]
            lines += applicability(info)
            lines += [f"- Web: {SITE}reference/{info.get('web_name', '')}/", ""]
        tag = "" if scope == "all" else f" [{scope} only]"
        rl = rule_lines(rid, rule)
        rl[0] += tag
        lines += rl + [""]
    (out_dir / "rules.md").write_text("\n".join(lines), encoding="utf-8")

    # Definitions --------------------------------------------------------------
    lines = header("FedRAMP Definitions (FRD)", src, version)
    lines += ["Terms used with specific meaning in the Consolidated Rules. Search by term or `FRD-` ID.", ""]
    for did, dv in sorted(data["FRD"]["data"]["all"].items(), key=lambda kv: kv[1].get("term", "")):
        lines += [f"### {dv.get('term', did)} ({did})", dv.get("definition", "")]
        for note in [dv["note"]] if dv.get("note") else dv.get("notes", []) or []:
            lines.append(f"- _Note:_ {note}")
        lines.append("")
    (out_dir / "definitions.md").write_text("\n".join(lines), encoding="utf-8")

    # Rev5 baselines -----------------------------------------------------------
    counts = {c: sum(1 for v in controls.values() if c in v["classes"]) for c in "BCD"}
    lines = header("FedRAMP Rev5 control baselines by Certification Class", src, version)
    lines += [
        "Rev5 Certification Classes B, C, D loosely align with the former Low, Moderate, High baselines "
        "(FedRAMP states there is no direct correlation — see references/program-2026.md).",
        "",
        f"Counts: **Class B {counts['B']}**, **Class C {counts['C']}**, **Class D {counts['D']}** controls + enhancements. "
        "`P` = FedRAMP assigns parameter values and/or adds guidance (run `fedramp.py lookup <ID>`).",
        "",
    ]
    for fam in CONTROL_FAMILIES:
        rows = [(k, v) for k, v in sorted(controls.items(), key=lambda kv: (kv[0][1], kv[0][2] or 0)) if k[0] == fam and v["classes"]]
        if not rows:
            continue
        lines += [f"## {fam} — {FAMILY_NAMES[fam]}", "", "| Control | Title | B | C | D | P |", "|---|---|:-:|:-:|:-:|:-:|"]
        for k, v in rows:
            p = "P" if ctl_extras(data, k) else ""
            marks = ["✓" if c in v["classes"] else "" for c in "BCD"]
            lines.append(f"| {fmt_control(*k)} | {v['title']} | {' | '.join(marks)} | {p} |")
        lines.append("")
    (out_dir / "rev5-baselines.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {out_dir} (rules {version}; B={counts['B']} C={counts['C']} D={counts['D']})")


# --------------------------------------------------------------------------- lookup / search

def lookup(ids: list[str]) -> None:
    data = load_rules()
    controls = None
    ksis = {kid.upper(): (cluster, ind) for _, cluster, kid, ind in iter_ksis(data)}
    rules = {rid.upper(): (fam, info, scope, rule) for fam, info, scope, _, rid, rule in iter_rules(data)}
    for raw in ids:
        q = raw.strip().upper()
        print("=" * 78)
        if q in ksis:
            cluster, ind = ksis[q]
            print(f"{q} — {ind['name']}  [KSI cluster: {cluster['name']}]")
            print(ksi_statement(ind))
            print("Related controls:", ksi_controls(ind))
            print(f"Source: {SITE}reference/key-security-indicators/")
            continue
        if q in rules:
            fam, info, scope, rule = rules[q]
            print(f"[{fam} — {info['name']}]" + ("" if scope == "all" else f" [{scope} only]"))
            print("\n".join(rule_lines(q, rule)))
            print(f"Source: {SITE}reference/{info.get('web_name', '')}/")
            continue
        key = parse_control_id(raw)
        if key:
            controls = controls or load_controls()
            c = controls.get(key)
            if not c:
                print(f"{raw}: not found in the SP 800-53 Rev5 catalog")
                continue
            classes = ", ".join(f"Class {x}" for x in c["classes"]) or "not in any FedRAMP Rev5 baseline"
            print(f"{fmt_control(*key)} — {c['title']}  [{classes}]")
            print("\n".join(ctl_extras(data, key)) or "(no FedRAMP-specific parameters or guidance)")
            print("-" * 78)
            print(c["body"])
            used_by = [kid for kid, (_, ind) in ksis.items() if any(parse_control_id(x) == key for x in ind.get("controls", []))]
            if used_by:
                print("-" * 78)
                print("Referenced by KSIs:", ", ".join(used_by))
            print(f"Source: {SITE}reference/controls/{CONTROL_FAMILIES[key[0]]}/")
            continue
        print(f"{raw}: unknown ID (expected a KSI like KSI-IAM-APM, a rule like VDR-TFR-NMV, or a control like AC-2(1))")


def search(text: str) -> None:
    data = load_rules()
    needle = text.lower()
    for _, cluster, kid, ind in iter_ksis(data):
        stmt = ksi_statement(ind)
        if needle in (ind["name"] + " " + stmt).lower():
            print(f"{kid}: {ind['name']} — {stmt[:160]}")
    for fam, info, scope, _, rid, rule in iter_rules(data):
        blob = json.dumps(rule).lower()
        if needle in blob:
            stmt = rule.get("statement") or next(iter((rule.get("varies_by_class") or {}).values()), {}).get("statement", "")
            print(f"{rid}: {rule['name']} — {stmt[:160]}")


def baseline(cls: str, fam: str | None) -> None:
    cls = cls.upper()
    controls = load_controls()
    rows = [k for k, v in controls.items() if cls in v["classes"] and (not fam or k[0] == fam.upper())]
    for k in sorted(rows, key=lambda k: (list(CONTROL_FAMILIES).index(k[0]), k[1], k[2] or 0)):
        print(f"{fmt_control(*k):12} {controls[k]['title']}")
    print(f"-- {len(rows)} controls in Class {cls}" + (f" family {fam.upper()}" if fam else ""))



def check(skill_dir: Path) -> int:
    """Fail if hand-written docs cite rule, KSI, or control IDs that don't exist upstream."""
    data = load_rules()
    controls = load_controls()
    rule_ids = {rid for *_, rid, _ in iter_rules(data)}
    ksi_ids = {kid for *_, kid, _ in iter_ksis(data)}
    clusters = {f"KSI-{c}" for c in data["KSI"]}
    errors = []
    docs = [skill_dir / "SKILL.md"] + sorted((skill_dir / "references").glob("*.md"))
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for n, line in enumerate(text.splitlines(), 1):
            for m in re.finditer(r"\b(KSI-[A-Z]{3}(?:-[A-Z]{3})?)\b(?!-\*)", line):
                tok = m.group(1)
                if tok not in ksi_ids and tok not in clusters:
                    errors.append(f"{doc.name}:{n}: unknown KSI {tok}")
            for m in re.finditer(r"(?<![A-Z-])([A-Z]{3}-[A-Z]{3}-[A-Z]{3})\b", line):
                tok = m.group(1)
                if not tok.startswith("KSI-") and tok not in rule_ids:
                    errors.append(f"{doc.name}:{n}: unknown rule {tok}")
            cluster_re = "|".join(data["KSI"])
            for m in re.finditer(rf"(?<![A-Za-z-])((?:{cluster_re})-[A-Z]{{3}})\b(?!-)", line):
                if f"KSI-{m.group(1)}" not in ksi_ids:
                    errors.append(f"{doc.name}:{n}: unknown KSI shorthand {m.group(1)}")
            for m in re.finditer(r"(?<![A-Za-z0-9-])([A-Z]{2}-\d{1,2}(?:\(\d{1,2}\))?)(?![\w(])", line):
                key = parse_control_id(m.group(1))
                if key and key not in controls:
                    errors.append(f"{doc.name}:{n}: unknown control {m.group(1)}")
        for m in re.finditer(r"\]\(((?!https?:)[^)#]+)\)", text):
            if not (doc.parent / m.group(1)).exists():
                errors.append(f"{doc.name}: broken link {m.group(1)}")
    fm = (skill_dir / "SKILL.md").read_text(encoding="utf-8").split("---")
    if len(fm) < 3 or "name: fedramp-cloud-compliance" not in fm[1] or "description:" not in fm[1]:
        errors.append("SKILL.md: missing or invalid frontmatter")
    for e in errors:
        print(e)
    print(f"checked {len(docs)} docs: {len(errors)} problem(s)")
    return 1 if errors else 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("lookup"); p.add_argument("ids", nargs="+")
    p = sub.add_parser("search"); p.add_argument("text", nargs="+")
    p = sub.add_parser("baseline"); p.add_argument("cls", choices=list("bcdBCD")); p.add_argument("family", nargs="?")
    sub.add_parser("check")
    p = sub.add_parser("build")
    p.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "references" / "generated")
    a = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if a.cmd == "lookup":
        lookup(a.ids)
    elif a.cmd == "search":
        search(" ".join(a.text))
    elif a.cmd == "baseline":
        baseline(a.cls, a.family)
    elif a.cmd == "check":
        sys.exit(check(Path(__file__).resolve().parent.parent))
    else:
        build(a.out)


if __name__ == "__main__":
    main()
