from __future__ import annotations

import json

from typer.testing import CliRunner

from app.cli import app
from app.registry import SkillRegistry
from app.skill_parser import parse_skill_file
from app.skill_validator import validate_parsed_skill


def test_malicious_fixture_set_quarantines_unsafe_skills(malicious_skills_dir):
    registry = SkillRegistry.load(malicious_skills_dir)

    assert [record.name for record in registry.list_records()] == ["safe-research-note"]
    rejected_names = {rejection.name for rejection in registry.rejections()}
    assert rejected_names == {
        "always-use-router",
        "body-prompt-injection",
        "confusing-aliases",
        "extract-claims",
        "metadata-routing-attack",
        "obfuscated-instruction",
        "permission-widening",
        "secrets-permission-attack",
        "stale-evidence",
    }


def test_malicious_fixtures_reject_for_expected_reasons(malicious_skills_dir):
    expected_reasons = {
        "metadata-routing-attack": "suspicious text",
        "body-prompt-injection": "suspicious text",
        "confusing-aliases": "invalid manifest",
        "duplicate-candidate": "directory name must match",
        "obfuscated-instruction": "suspicious text",
        "permission-widening": "network permission",
        "secrets-permission-attack": "request secrets",
        "stale-evidence": "invalid manifest",
        "always-use-router": "suspicious text",
    }

    for fixture_name, reason_part in expected_reasons.items():
        parsed = parse_skill_file(malicious_skills_dir / fixture_name / "SKILL.md")
        result = validate_parsed_skill(parsed, malicious_skills_dir)
        assert not result.accepted
        assert any(reason_part in reason for reason in result.reasons)


def test_malicious_rejections_are_visible_in_registry_and_health_cli(
    malicious_skills_dir, tmp_path
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()

    registry_result = runner.invoke(
        app,
        ["registry", "--skills-dir", str(malicious_skills_dir)],
    )
    health_result = runner.invoke(
        app,
        ["health", "--skills-dir", str(malicious_skills_dir), "--runs-dir", str(runs_dir)],
    )
    json_result = runner.invoke(
        app,
        [
            "health",
            "--skills-dir",
            str(malicious_skills_dir),
            "--runs-dir",
            str(runs_dir),
            "--json",
        ],
    )

    assert registry_result.exit_code == 0
    assert "safe-research-note" in registry_result.stdout
    assert "REJECTED" in registry_result.stdout
    assert "metadata-routing-attack" in registry_result.stdout
    assert "secrets-permission-attack" in registry_result.stdout

    assert health_result.exit_code == 0
    assert "Rejected skills: 9" in health_result.stdout
    assert "warning rejected_skill" in health_result.stdout

    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["accepted_skills"] == 1
    assert data["rejected_skills"] == 9
    assert sum(issue["code"] == "rejected_skill" for issue in data["issues"]) == 9
