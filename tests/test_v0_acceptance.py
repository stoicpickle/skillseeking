from __future__ import annotations

import json
import subprocess
from pathlib import Path
from shutil import copytree

import pytest
from textwrap import dedent
from typer.testing import CliRunner

from app.cli import app


def assert_contains(stdout: str, landmarks: list[str]) -> None:
    for landmark in landmarks:
        assert landmark in stdout


def assert_in_order(stdout: str, landmarks: list[str]) -> None:
    position = -1
    for landmark in landmarks:
        next_position = stdout.find(landmark, position + 1)
        assert next_position != -1, f"{landmark!r} was not found after offset {position}"
        position = next_position


def read_single_run_log(runs_dir: Path) -> tuple[Path, dict]:
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    return logs[0], json.loads(logs[0].read_text(encoding="utf-8"))


def assert_no_markdown_body(run_log_path: Path) -> None:
    assert "markdown_body" not in run_log_path.read_text(encoding="utf-8")


def test_acceptance_existing_skill_loads_without_requests(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"
    result = CliRunner().invoke(
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
    assert_in_order(result.stdout, ["PLANNING", "CHECKING_SKILLS", "LOADING_SKILL", "RESULT"])
    assert_contains(
        result.stdout,
        [
            "USE_SKILL extract-claims",
            "USE_SKILL source-quality-check",
            "USE_SKILL write-structured-answer",
            "Exit code: 0",
        ],
    )
    log_path, data = read_single_run_log(runs_dir)
    assert_no_markdown_body(log_path)
    loaded_names = {skill["name"] for skill in data["skills_loaded"]}
    assert {"extract-claims", "source-quality-check", "write-structured-answer"} <= loaded_names
    assert data["schema_version"] == 2
    assert data["run_id"] in log_path.name
    assert data["result_category"] == "success"
    assert [event["sequence"] for event in data["trace_events"]] == list(range(1, len(data["trace_events"]) + 1))
    assert [event["stage"] for event in data["trace_events"]] == data["trace"]
    assert data["execution_summary"]["loaded_skills"]
    assert data["execution_summary"]["skill_request_count"] == 0
    assert not (runs_dir / "artifacts").exists()
    assert data["skill_requests"] == []
    assert data["skill_repair_requests"] == []


def test_acceptance_temporary_skill_success_records_loaded_temp(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"
    durable_entries_before = {path.name for path in copied_seed_skills.iterdir()}
    result = CliRunner().invoke(
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
    assert_in_order(
        result.stdout,
        [
            "PLANNING",
            "CHECKING_SKILLS",
            "BLOCKED_MISSING_SKILL",
            "REQUESTING_SKILL",
            "DRAFTING_TEMP_SKILL",
            "VALIDATION_PASSED",
            "LOADING_TEMP_SKILL",
            "RESULT",
        ],
    )
    assert_contains(
        result.stdout,
        [
            "Temporary skill: argument-clustering",
            "Validation passed: True",
            "Loaded: True",
            "Temporary skills: argument-clustering",
            "Exit code: 0",
        ],
    )
    assert not (copied_seed_skills / "argument-clustering" / "SKILL.md").exists()
    assert {path.name for path in copied_seed_skills.iterdir()} == durable_entries_before
    log_path, data = read_single_run_log(runs_dir)
    assert_no_markdown_body(log_path)
    artifact_skill = runs_dir / "artifacts" / data["run_id"] / "skills" / "argument-clustering" / "SKILL.md"
    assert artifact_skill.exists()
    request = data["skill_requests"][0]
    assert request["desired_skill_name"] == "argument-clustering"
    assert Path(request["temporary_skill"]["skill_path"]) == artifact_skill
    assert request["temporary_skill"]["validation_passed"]
    assert request["temporary_skill"]["loaded"]
    assert data["result_category"] == "success"
    assert data["execution_summary"]["temporary_skills"] == ["argument-clustering"]
    assert data["execution_summary"]["skill_request_count"] == 1
    assert data["skill_repair_requests"] == []
    loaded_temp = next(skill for skill in data["skills_loaded"] if skill["name"] == "argument-clustering")
    assert loaded_temp["temporary"]
    assert loaded_temp["lifecycle"]["run_id"] == data["run_id"]


def test_acceptance_blocked_no_temp_skill_does_not_mutate_skills(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"
    result = CliRunner().invoke(
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
    assert_in_order(
        result.stdout,
        ["PLANNING", "CHECKING_SKILLS", "BLOCKED_MISSING_SKILL", "REQUESTING_SKILL", "RESULT"],
    )
    assert_contains(
        result.stdout,
        [
            "REQUEST_SKILL - :: detect contradictions",
            "Missing capability: detect contradictions",
            "Requested skill: detect-contradictions",
            "Exit code: 1",
        ],
    )
    assert "DRAFTING_TEMP_SKILL" not in result.stdout
    assert not (copied_seed_skills / "detect-contradictions").exists()
    assert not (runs_dir / "artifacts").exists()
    log_path, data = read_single_run_log(runs_dir)
    assert_no_markdown_body(log_path)
    assert data["result_category"] == "blocked_missing_skill"
    assert data["execution_summary"]["requested_skills"] == ["detect-contradictions"]
    assert data["skill_requests"][0]["desired_skill_name"] == "detect-contradictions"
    assert "temporary_skill" not in data["skill_requests"][0]
    assert data["skill_repair_requests"] == []


def test_acceptance_validation_failure_emits_repair_request(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"
    result = CliRunner().invoke(
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
    assert_in_order(
        result.stdout,
        [
            "DRAFTING_TEMP_SKILL",
            "VALIDATION_FAILED",
            "REQUESTING_REPAIR",
            "REPAIR_REQUESTED",
            "RESULT",
        ],
    )
    assert_contains(
        result.stdout,
        [
            "Temporary skill: local-python-analysis",
            "Validation passed: False",
            "Loaded: False",
            "Skill: local-python-analysis",
            "Failure reason: non-scripted skills must be low risk",
            "Exit code: 1",
        ],
    )
    assert not (copied_seed_skills / "local-python-analysis").exists()
    log_path, data = read_single_run_log(runs_dir)
    assert_no_markdown_body(log_path)
    artifact_skill = runs_dir / "artifacts" / data["run_id"] / "skills" / "local-python-analysis" / "SKILL.md"
    assert artifact_skill.exists()
    request = data["skill_requests"][0]
    repair = data["skill_repair_requests"][0]
    assert not request["temporary_skill"]["validation_passed"]
    assert request["temporary_skill"]["loaded"] is False
    assert Path(request["temporary_skill"]["skill_path"]) == artifact_skill
    assert data["result_category"] == "repair_requested"
    assert data["execution_summary"]["temporary_skills"] == ["local-python-analysis"]
    assert data["execution_summary"]["repair_requested_skills"] == ["local-python-analysis"]
    assert repair["skill_request_id"] == request["id"]
    assert repair["skill_name"] == "local-python-analysis"
    assert repair["failed_capability"] == "run local python analysis"
    assert repair["status"] == "requested"


def test_acceptance_malicious_registry_quarantines_unsafe_fixtures(malicious_skills_dir):
    result = CliRunner().invoke(app, ["registry", "--skills-dir", str(malicious_skills_dir)])

    assert result.exit_code == 0
    assert_contains(
        result.stdout,
        [
            "safe-research-note",
            "REJECTED",
            "metadata-routing-attack",
            "body-prompt-injection",
            "obfuscated-instruction",
            "secrets-permission-attack",
        ],
    )


def test_acceptance_scripted_skill_opt_in_records_execution(tmp_path, repo_root: Path):
    skills_dir = tmp_path / "scripted-skills"
    copytree(repo_root / "tests" / "fixtures" / "scripted-skills", skills_dir)
    runs_dir = tmp_path / "runs"

    result = CliRunner().invoke(
        app,
        [
            "run",
            "Count words in one two three.",
            "--scripted-skills",
            "--no-temporary-skills",
            "--skills-dir",
            str(skills_dir),
            "--runs-dir",
            str(runs_dir),
        ],
    )

    assert result.exit_code == 0
    assert_in_order(result.stdout, ["LOADING_SKILL", "EXECUTING_SCRIPT", "SCRIPT_EXECUTED", "RESULT"])
    assert_contains(result.stdout, ["Skill: count-words", "Return code: 0", "Exit code: 0"])
    log_path, data = read_single_run_log(runs_dir)
    assert_no_markdown_body(log_path)
    execution = data["script_executions"][0]
    assert data["execution_summary"]["script_execution_count"] == 1
    assert data["execution_summary"]["failed_script_count"] == 0
    assert execution["skill_name"] == "count-words"
    assert execution["returncode"] == 0
    assert json.loads(execution["stdout"]) == {"word_count": 6}
    assert execution["parsed_stdout"] == {"word_count": 6}
    assert execution["output_validated"]
    assert execution["failure_category"] is None


def test_acceptance_scripted_failure_sets_result_category(tmp_path, repo_root: Path):
    skills_dir = tmp_path / "scripted-skills"
    copytree(repo_root / "tests" / "fixtures" / "scripted-skills", skills_dir)
    script = skills_dir / "count-words" / "scripts" / "count_words.py"
    script.write_text(
        dedent(
            '''
            from __future__ import annotations
            import json
            import sys

            payload = json.loads(sys.stdin.read() or "{}")
            text = str(payload.get("text", ""))
            if text == "one two two":
                print(json.dumps({"word_count": 3}))
            else:
                print("not json")
            '''
        ),
        encoding="utf-8",
    )
    runs_dir = tmp_path / "runs"

    result = CliRunner().invoke(
        app,
        [
            "run",
            "Count words in one two three.",
            "--scripted-skills",
            "--no-temporary-skills",
            "--skills-dir",
            str(skills_dir),
            "--runs-dir",
            str(runs_dir),
        ],
    )

    assert result.exit_code == 1
    assert_contains(result.stdout, ["SCRIPT_EXECUTED", "Failure category: invalid_json", "Result category: script_failed"])
    log_path, data = read_single_run_log(runs_dir)
    assert_no_markdown_body(log_path)
    assert data["result_category"] == "script_failed"
    assert data["script_executions"][0]["failure_category"] == "invalid_json"
    assert data["execution_summary"]["failed_script_count"] == 1



def test_acceptance_packaged_cli_entrypoint_smoke(tmp_path, repo_root: Path):
    entrypoint = repo_root / ".venv" / "bin" / "skill-agent"
    if not entrypoint.exists():
        pytest.skip("packaged skill-agent entrypoint is not available")

    skills_dir = tmp_path / "skills"
    copytree(repo_root / "skills", skills_dir)
    runs_dir = tmp_path / "runs"

    result = subprocess.run(
        [
            str(entrypoint),
            "run",
            "Cluster arguments from these sources.",
            "--skills-dir",
            str(skills_dir),
            "--runs-dir",
            str(runs_dir),
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert_in_order(
        result.stdout,
        ["PLANNING", "REQUESTING_SKILL", "VALIDATION_PASSED", "LOADING_TEMP_SKILL", "RESULT"],
    )
    log_path, data = read_single_run_log(runs_dir)
    assert_no_markdown_body(log_path)
    artifact_skill = runs_dir / "artifacts" / data["run_id"] / "skills" / "argument-clustering" / "SKILL.md"
    assert artifact_skill.exists()
    assert not (skills_dir / "argument-clustering" / "SKILL.md").exists()
    assert data["skill_requests"][0]["temporary_skill"]["loaded"]
