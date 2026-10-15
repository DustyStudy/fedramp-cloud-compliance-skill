"""Offline unit tests for scripts/fedramp.py. The live data is replaced with a
small fixture, so these run without network access; CI's `fedramp.py check`
step still validates the real docs against FedRAMP's published data."""

import importlib.util
import pathlib

import pytest

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "skills" / "fedramp-cloud-compliance" / "scripts" / "fedramp.py"
spec = importlib.util.spec_from_file_location("fedramp", SCRIPT)
fedramp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fedramp)

RULES = {
    "info": {"version": "2026.09.22"},
    "FRR": {
        "VDR": {
            "info": {"name": "Vulnerability Detection and Response", "web_name": "vdr"},
            "data": {
                "all": {
                    "TFR": {
                        "VDR-TFR-PVR": {
                            "name": "Persistent vulnerability remediation",
                            "force": "MUST",
                            "statement": "Remediate within the timeframe.",
                            "timeframe_num": 30,
                            "timeframe_type": "days",
                        }
                    }
                }
            },
        }
    },
    "KSI": {
        "IAM": {
            "name": "Identity and Access Management",
            "indicators": {"KSI-IAM-APM": {"name": "Phishing-resistant MFA", "statement": "Use it.", "controls": ["ac-2.1", "IA-2"]}},
        }
    },
    "FRD": {"data": {"all": {}}},
    "CTL": {"AC": {"AC-02-01": {"parameters": [{"parameterId": "ac-2.1_prm_1", "value": "24 hours"}]}}},
}
CONTROLS = {("AC", 2, 1): {"title": "Automated Account Management", "classes": ["C", "D"], "body": ""}, ("IA", 2, None): {"title": "Identification", "classes": ["B", "C", "D"], "body": ""}}


@pytest.mark.parametrize(
    "text, expected",
    [
        ("AC-2", ("AC", 2, None)),
        ("AC-2(1)", ("AC", 2, 1)),
        ("ac-2.1", ("AC", 2, 1)),
        ("SC-013", ("SC", 13, None)),
        (" IA-2 (12) ", ("IA", 2, 12)),
        ("ZZ-1", None),
        ("KSI-IAM-APM", None),
    ],
)
def test_parse_control_id(text, expected):
    assert fedramp.parse_control_id(text) == expected


def test_control_formatting_round_trips():
    assert fedramp.fmt_control("AC", 2, 1) == "AC-2(1)"
    assert fedramp.ctl_key("AC", 6, 1) == "AC-06-01"
    assert fedramp.ctl_key("SC", 13, None) == "SC-13"


def test_timeframe_rendering():
    assert fedramp.timeframe({"timeframe_num": 30, "timeframe_type": "days"}) == " _(timeframe: 30 days)_"
    assert fedramp.timeframe({"timeframe_num_min": 1, "timeframe_num_max": 3, "timeframe_type": "days"}) == " _(timeframe: 1–3 days)_"
    assert fedramp.timeframe({}) == ""


def test_rule_lines_include_force_statement_and_class_variants():
    lines = fedramp.rule_lines(
        "VDR-TFR-X",
        {"name": "Example", "force": "MUST", "statement": "Do it.", "varies_by_class": {"c": {"force": "SHOULD", "statement": "Do less."}}},
    )
    assert lines[0] == "### VDR-TFR-X — Example (MUST)"
    assert "Do it." in lines
    assert "- **Class C (SHOULD):** Do less." in lines


def test_ksi_controls_normalizes_ids():
    assert fedramp.ksi_controls({"controls": ["ac-2.1", "IA-2"]}) == "AC-2(1), IA-2"


def test_ctl_extras_reads_fedramp_parameters():
    assert fedramp.ctl_extras(RULES, ("AC", 2, 1)) == ["- FedRAMP parameter `ac-2.1_prm_1`: 24 hours"]


@pytest.fixture
def skill_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(fedramp, "load_rules", lambda: RULES)
    monkeypatch.setattr(fedramp, "load_controls", lambda: CONTROLS)
    (tmp_path / "references").mkdir()
    (tmp_path / "references" / "aws.md").write_text("ok", encoding="utf-8")
    return tmp_path


def _skill(skill_dir, body):
    (skill_dir / "SKILL.md").write_text(f"---\nname: fedramp-cloud-compliance\ndescription: x\n---\n{body}\n", encoding="utf-8")


def test_check_passes_for_known_ids_and_links(skill_dir):
    _skill(skill_dir, "Use KSI-IAM-APM, VDR-TFR-PVR, AC-2(1) and IA-2. See [AWS](references/aws.md).")

    assert fedramp.check(skill_dir) == 0


@pytest.mark.parametrize(
    "body, problem",
    [
        ("KSI-IAM-XYZ", "unknown KSI KSI-IAM-XYZ"),
        ("VDR-TFR-ZZZ", "unknown rule VDR-TFR-ZZZ"),
        ("AC-2(9)", "unknown control AC-2(9)"),
        ("[gone](references/missing.md)", "broken link references/missing.md"),
    ],
)
def test_check_flags_unknown_ids_and_broken_links(skill_dir, capsys, body, problem):
    _skill(skill_dir, body)

    assert fedramp.check(skill_dir) == 1
    assert problem in capsys.readouterr().out


def test_check_requires_frontmatter(skill_dir, capsys):
    (skill_dir / "SKILL.md").write_text("# no frontmatter\n", encoding="utf-8")

    assert fedramp.check(skill_dir) == 1
    assert "missing or invalid frontmatter" in capsys.readouterr().out


def _load_with_env(monkeypatch, **env):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    mod = importlib.util.module_from_spec(importlib.util.spec_from_file_location("fedramp_pinned", SCRIPT))
    mod.__spec__.loader.exec_module(mod)
    return mod


def test_refs_pin_download_urls(monkeypatch):
    mod = _load_with_env(monkeypatch, FEDRAMP_SKILL_RULES_REF="abc123", FEDRAMP_SKILL_MD_REF="v1.2")
    assert "/FedRAMP/rules/abc123/" in mod.RULES_URL
    assert mod.MD_BASE.endswith("/FedRAMP/2026-markdown/v1.2/")
    assert mod.SOURCES_URL.startswith(mod.MD_BASE)


@pytest.mark.parametrize("ref", ["a b", "../main", "main?x=1"])
def test_invalid_refs_are_rejected(monkeypatch, ref):
    with pytest.raises(SystemExit):
        _load_with_env(monkeypatch, FEDRAMP_SKILL_RULES_REF=ref)


def test_data_banner_goes_to_stderr(capsys):
    fedramp.data_banner(RULES)
    out, err = capsys.readouterr()
    assert out == "" and "2026.09.22" in err
