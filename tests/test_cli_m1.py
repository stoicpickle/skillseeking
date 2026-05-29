from __future__ import annotations

import json

from typer.testing import CliRunner

from app.cli import app


def test_registry_command_lists_seed_skills(seed_skills_dir):
    runner = CliRunner()

    result = runner.invoke(app, ["registry", "--skills-dir", str(seed_skills_dir)])

    assert result.exit_code == 0
    assert "extract-claims" in result.stdout
    assert "write-structured-answer" in result.stdout


def test_existing_skill_demo(copied_seed_skills, tmp_path):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"

    result = runner.invoke(
        app,
        [
            "run",
            "Extract claims from this article and write a structured summary with source-quality notes.",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )

    assert result.exit_code == 0
    assert "PLANNING" in result.stdout
    assert "USE_SKILL extract-claims" in result.stdout
    assert "USE_SKILL source-quality-check" in result.stdout
    assert "USE_SKILL write-structured-answer" in result.stdout
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    data = json.loads(logs[0].read_text(encoding="utf-8"))
    loaded_names = {skill["name"] for skill in data["skills_loaded"]}
    assert {"extract-claims", "source-quality-check", "write-structured-answer"} <= loaded_names
    assert data["skill_requests"] == []
    assert "markdown_body" not in logs[0].read_text(encoding="utf-8")


def test_missing_skill_demo_emits_structured_request(copied_seed_skills, tmp_path):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"

    result = runner.invoke(
        app,
        [
            "run",
            "Extract claims from these two sources and identify contradictions.",
            "--no-temporary-skills",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )

    assert result.exit_code == 1
    assert "BLOCKED_MISSING_SKILL" in result.stdout
    assert "REQUESTING_SKILL" in result.stdout
    assert "BLOCKED" in result.stdout
    assert "REQUEST_SKILL - :: detect contradictions" in result.stdout
    assert "Missing capability: detect contradictions" in result.stdout
    assert "Requested skill: detect-contradictions" in result.stdout
    assert not (copied_seed_skills / "detect-contradictions").exists()
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    data = json.loads(logs[0].read_text(encoding="utf-8"))
    assert data["skill_requests"]
    request = data["skill_requests"][0]
    assert request["desired_skill_name"] == "detect-contradictions"
    assert request["status"] == "requested"
    assert request["output_schema"]["contradictions"] == "array"


def test_temporary_skill_demo_drafts_validates_and_loads_skill(copied_seed_skills, tmp_path):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"

    result = runner.invoke(
        app,
        [
            "run",
            "Cluster arguments from these sources.",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )

    assert result.exit_code == 0
    for landmark in [
        "PLANNING",
        "CHECKING_SKILLS",
        "BLOCKED_MISSING_SKILL",
        "REQUESTING_SKILL",
        "VALIDATION_PASSED",
        "LOADING_TEMP_SKILL",
        "ROUTE_COMPLETE",
        "RESULT",
    ]:
        assert landmark in result.stdout
    assert "DRAFTING_TEMP_SKILL" in result.stdout
    assert "Temporary skill: argument-clustering" in result.stdout
    assert "Validation passed: True" in result.stdout
    assert "Loaded: True" in result.stdout
    assert "Exit code: 0" in result.stdout
    assert "Loaded skills: argument-clustering" in result.stdout
    assert "Temporary skills: argument-clustering" in result.stdout
    assert (copied_seed_skills / "argument-clustering" / "SKILL.md").exists()
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    assert f"Run log: {logs[0]}" in result.stdout
    data = json.loads(logs[0].read_text(encoding="utf-8"))
    request = data["skill_requests"][0]
    assert request["temporary_skill"]["validation_passed"]
    assert request["temporary_skill"]["loaded"]
    loaded_names = {skill["name"] for skill in data["skills_loaded"]}
    assert "argument-clustering" in loaded_names


def test_medium_risk_temporary_skill_fails_validation_and_stays_blocked(
    copied_seed_skills, tmp_path
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"

    result = runner.invoke(
        app,
        [
            "run",
            "Extract claims from these two sources and identify contradictions.",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )

    assert result.exit_code == 1
    assert "DRAFTING_TEMP_SKILL" in result.stdout
    assert "VALIDATION_FAILED" in result.stdout
    assert "RESULT" in result.stdout
    assert "Exit code: 1" in result.stdout
    assert "Temporary skill: detect-contradictions" in result.stdout
    assert "Validation passed: False" in result.stdout
    assert "Loaded: False" in result.stdout
    assert "Loaded skills: extract-claims" in result.stdout
    assert "Temporary skills: -" in result.stdout
    assert not (copied_seed_skills / "detect-contradictions").exists()
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    data = json.loads(logs[0].read_text(encoding="utf-8"))
    request = data["skill_requests"][0]
    assert not request["temporary_skill"]["validation_passed"]
    assert not request["temporary_skill"]["loaded"]
