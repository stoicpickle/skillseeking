from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app


def test_registry_command_lists_seed_skills(seed_skills_dir):
    runner = CliRunner()

    result = runner.invoke(app, ["registry", "--skills-dir", str(seed_skills_dir)])

    assert result.exit_code == 0
    assert "extract-claims" in result.stdout
    assert "write-structured-answer" in result.stdout


def test_registry_json_lists_accepted_and_rejected(seed_skills_dir):
    runner = CliRunner()

    result = runner.invoke(app, ["registry", "--skills-dir", str(seed_skills_dir), "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert {record["name"] for record in data["accepted"]} >= {"extract-claims", "write-structured-answer"}
    assert data["rejected"] == []


def test_run_json_outputs_machine_readable_result(copied_seed_skills, tmp_path):
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
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert "TRACE" not in result.stdout
    data = json.loads(result.stdout)
    assert data["exit_code"] == 0
    assert data["result_category"] == "success"
    assert data["run_id"] in data["run_log_path"]
    assert data["execution_summary"]["loaded_skills"]
    assert data["decisions"][0]["ranked_candidates"]
    assert data["governor_decisions"][0]["decision"] == "USE_SKILL"
    assert data["governor_decisions"][0]["dominant_signal"] == "skill_match"



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
    assert "NEXT_ACTION" in result.stdout
    assert "Start with summary: skill-agent operator-summary --runs-dir" in result.stdout
    assert "Explain this run: skill-agent explain" in result.stdout
    assert "Boundary: no durable skill admission or stable routing happened automatically." in result.stdout
    assert not (copied_seed_skills / "detect-contradictions").exists()
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    data = json.loads(logs[0].read_text(encoding="utf-8"))
    assert data["skill_requests"]
    request = data["skill_requests"][0]
    assert request["desired_skill_name"] == "detect-contradictions"
    assert request["status"] == "requested"
    assert request["output_schema"]["contradictions"] == "array"
    assert request["control_summary"]["governor_decision"] == "REQUEST_SKILL"
    assert request["control_summary"]["dominant_signal"] == "missing_skill"
    assert request["control_summary"]["approval_gate"] == "none"


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
    assert not (copied_seed_skills / "argument-clustering" / "SKILL.md").exists()
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    assert f"Run log: {logs[0]}" in result.stdout
    data = json.loads(logs[0].read_text(encoding="utf-8"))
    artifact_skill = runs_dir / "artifacts" / data["run_id"] / "skills" / "argument-clustering" / "SKILL.md"
    assert artifact_skill.exists()
    request = data["skill_requests"][0]
    assert request["control_summary"]["governor_decision"] == "REQUEST_SKILL"
    assert request["control_summary"]["approval_gate"] == "none"
    assert request["temporary_skill"]["validation_passed"]
    assert request["temporary_skill"]["loaded"]
    assert Path(request["temporary_skill"]["skill_path"]) == artifact_skill
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
            "Run local Python analysis on this text.",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )

    assert result.exit_code == 1
    assert "DRAFTING_TEMP_SKILL" in result.stdout
    assert "VALIDATION_FAILED" in result.stdout
    assert "REQUESTING_REPAIR" in result.stdout
    assert "REPAIR_REQUESTED" in result.stdout
    assert "RESULT" in result.stdout
    assert "Exit code: 1" in result.stdout
    assert "Temporary skill: local-python-analysis" in result.stdout
    assert "Validation passed: False" in result.stdout
    assert "Loaded: False" in result.stdout
    assert "Skill: local-python-analysis" in result.stdout
    assert "Failed capability: run local python analysis" in result.stdout
    assert "Failure reason: non-scripted skills must be low risk" in result.stdout
    assert "Loaded skills: -" in result.stdout
    assert "Temporary skills: -" in result.stdout
    assert not (copied_seed_skills / "local-python-analysis").exists()
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    data = json.loads(logs[0].read_text(encoding="utf-8"))
    artifact_skill = runs_dir / "artifacts" / data["run_id"] / "skills" / "local-python-analysis" / "SKILL.md"
    assert artifact_skill.exists()
    request = data["skill_requests"][0]
    assert request["control_summary"]["governor_decision"] == "REQUEST_SKILL"
    assert request["control_summary"]["risk_level"] == "medium"
    assert request["control_summary"]["approval_gate"] == "sandbox"
    assert not request["temporary_skill"]["validation_passed"]
    assert not request["temporary_skill"]["loaded"]
    repair_request = data["skill_repair_requests"][0]
    assert repair_request["skill_request_id"] == request["id"]
    assert repair_request["skill_name"] == "local-python-analysis"
    assert repair_request["failed_capability"] == "run local python analysis"
    assert repair_request["status"] == "requested"
    assert "non-scripted skills must be low risk" in repair_request["failure_reasons"]
