from __future__ import annotations

import json
from shutil import copytree

from typer.testing import CliRunner

from app.cli import app
from app.librarian import analyze_library


def test_library_health_reads_usage_requests_failures_and_rejections(tmp_path, seed_skills_dir):
    skills_dir = tmp_path / "skills"
    runs_dir = tmp_path / "runs"
    copytree(seed_skills_dir, skills_dir)
    runs_dir.mkdir()
    (runs_dir / "run_001.json").write_text(
        json.dumps(
            {
                "task_id": "task_001",
                "created_at": "2026-05-29T10:00:00",
                "exit_code": 1,
                "skills_loaded": [
                    {"name": "extract-claims", "temporary": False},
                    {"name": "argument-clustering", "temporary": True},
                ],
                "skill_requests": [
                    {
                        "id": "skillreq_001",
                        "desired_skill_name": "argument-clustering",
                        "temporary_skill": {
                            "skill_name": "argument-clustering",
                            "validation_passed": False,
                        },
                    }
                ],
                "script_executions": [
                    {"skill_name": "count-words", "returncode": 1, "timed_out": False}
                ],
            }
        ),
        encoding="utf-8",
    )

    report = analyze_library(skills_dir, runs_dir)

    metrics = {metric.name: metric for metric in report.metrics}
    assert report.accepted_skills == 5
    assert report.run_logs_read == 1
    assert metrics["extract-claims"].uses == 1
    assert metrics["argument-clustering"].requests == 1
    assert metrics["argument-clustering"].temporary_uses == 1
    assert metrics["count-words"].script_failures == 1
    issue_codes = {issue.code for issue in report.issues}
    assert "temporary_validation_failed" in issue_codes
    assert "script_execution_failed" in issue_codes
    assert "used_in_failed_run" in issue_codes


def test_library_health_detects_duplicate_contracts(tmp_path, seed_skills_dir):
    skills_dir = tmp_path / "skills"
    copytree(seed_skills_dir, skills_dir)
    duplicate_dir = skills_dir / "extract-claims-copy"
    copytree(skills_dir / "extract-claims", duplicate_dir)
    skill_file = duplicate_dir / "SKILL.md"
    text = skill_file.read_text(encoding="utf-8")
    skill_file.write_text(text.replace("name: extract-claims", "name: extract-claims-copy"), encoding="utf-8")

    report = analyze_library(skills_dir, tmp_path / "runs")

    duplicate_issues = [issue for issue in report.issues if issue.code == "duplicate_contract"]
    assert duplicate_issues
    assert "extract-claims-copy" in duplicate_issues[0].message


def test_library_health_tolerates_malformed_numeric_log_fields(tmp_path, seed_skills_dir):
    skills_dir = tmp_path / "skills"
    runs_dir = tmp_path / "runs"
    copytree(seed_skills_dir, skills_dir)
    runs_dir.mkdir()
    (runs_dir / "run_bad_numbers.json").write_text(
        json.dumps(
            {
                "task_id": "task_bad_numbers",
                "created_at": "2026-05-29T11:00:00",
                "exit_code": "not-an-int",
                "skills_loaded": [{"name": "extract-claims", "temporary": False}],
                "script_executions": [
                    {
                        "skill_name": "count-words",
                        "returncode": "not-an-int",
                        "timed_out": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = analyze_library(skills_dir, runs_dir)

    metrics = {metric.name: metric for metric in report.metrics}
    assert report.run_logs_read == 1
    assert metrics["extract-claims"].uses == 1
    assert metrics["count-words"].script_failures == 1
    assert any(issue.code == "script_execution_failed" for issue in report.issues)


def test_library_health_preserves_numeric_zero_returncode(tmp_path, seed_skills_dir):
    skills_dir = tmp_path / "skills"
    runs_dir = tmp_path / "runs"
    copytree(seed_skills_dir, skills_dir)
    runs_dir.mkdir()
    (runs_dir / "run_zero_returncode.json").write_text(
        json.dumps(
            {
                "task_id": "task_zero_returncode",
                "created_at": "2026-05-29T12:00:00",
                "script_executions": [
                    {"skill_name": "count-words", "returncode": 0, "timed_out": False}
                ],
            }
        ),
        encoding="utf-8",
    )

    report = analyze_library(skills_dir, runs_dir)

    assert not any(issue.code == "script_execution_failed" for issue in report.issues)


def test_health_command_outputs_text_and_json(tmp_path, seed_skills_dir):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    runner = CliRunner()

    text_result = runner.invoke(
        app,
        ["health", "--skills-dir", str(seed_skills_dir), "--runs-dir", str(runs_dir)],
    )
    json_result = runner.invoke(
        app,
        ["health", "--skills-dir", str(seed_skills_dir), "--runs-dir", str(runs_dir), "--json"],
    )

    assert text_result.exit_code == 0
    assert "LIBRARY_HEALTH" in text_result.stdout
    assert "SKILL_METRICS" in text_result.stdout
    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["accepted_skills"] == 5
    assert data["run_logs_read"] == 0
