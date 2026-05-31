from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.agent_loop import _result_category
from app.capability_catalog import classify_task_safety
from app.cli import app
from app.models import ScriptExecutionLog


def _read_single_run_log(runs_dir: Path) -> dict:
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    return json.loads(logs[0].read_text(encoding="utf-8"))


def test_unsafe_task_aborts_without_routing_or_artifacts(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"

    result = CliRunner().invoke(
        app,
        [
            "run",
            "Delete files and send email with the result.",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )

    assert result.exit_code == 1
    assert "UNSAFE_ABORTED" in result.stdout
    assert "SAFETY" in result.stdout
    assert "Decision: ABORT_UNSAFE" in result.stdout
    assert "Result category: unsafe_aborted" in result.stdout
    assert "CHECKING_SKILLS" not in result.stdout
    assert "ROUTING" not in result.stdout
    assert "ROUTE_COMPLETE" not in result.stdout
    assert "SAFETY_STOP_COMPLETE" in result.stdout
    assert "REQUESTING_SKILL" not in result.stdout
    assert "DRAFTING_TEMP_SKILL" not in result.stdout
    assert "LOADING_SKILL" not in result.stdout
    assert not (runs_dir / "artifacts").exists()

    data = _read_single_run_log(runs_dir)
    assert data["result_category"] == "unsafe_aborted"
    assert data["exit_code"] == 1
    assert data["skill_requests"] == []
    assert data["skills_loaded"] == []
    assert data["capability_decisions"][0]["decision"] == "ABORT_UNSAFE"
    assert data["execution_summary"]["safety_decision_count"] == 1
    assert data["execution_summary"]["result_category"] == "unsafe_aborted"
    assert "UNSAFE_ABORTED" in data["trace"]


def test_approval_needed_task_stops_without_requesting_skill(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"

    result = CliRunner().invoke(
        app,
        [
            "run",
            "Read file ./notes.txt and write a structured summary.",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )

    assert result.exit_code == 1
    assert "SAFETY_REVIEW_REQUIRED" in result.stdout
    assert "SAFETY" in result.stdout
    assert "Decision: ASK_HUMAN" in result.stdout
    assert "Approval required: True" in result.stdout
    assert "Result category: awaiting_human_approval" in result.stdout
    assert "CHECKING_SKILLS" not in result.stdout
    assert "ROUTING" not in result.stdout
    assert "ROUTE_COMPLETE" not in result.stdout
    assert "SAFETY_STOP_COMPLETE" in result.stdout
    assert "REQUESTING_SKILL" not in result.stdout
    assert "DRAFTING_TEMP_SKILL" not in result.stdout
    assert "LOADING_SKILL" not in result.stdout
    assert not (runs_dir / "artifacts").exists()

    data = _read_single_run_log(runs_dir)
    assert data["result_category"] == "awaiting_human_approval"
    assert data["skill_requests"] == []
    assert data["skills_loaded"] == []
    assert data["capability_decisions"][0]["decision"] == "ASK_HUMAN"
    assert data["capability_decisions"][0]["requires_human_approval"]
    assert data["execution_summary"]["safety_decisions"] == [
        "ASK_HUMAN:human approval required for file access"
    ]
    assert "SAFETY_REVIEW_REQUIRED" in data["trace"]


def test_read_local_files_phrase_requires_human_approval():
    decision = classify_task_safety("Read local files and summarize them.")

    assert decision is not None
    assert decision.decision == "ASK_HUMAN"
    assert decision.capability == "human approval required for file access"


def test_result_category_precedence_uses_explicit_route_load_before_script_failure():
    script_failure = ScriptExecutionLog(
        skill_name="count-words",
        command=["python", "count_words.py"],
        returncode=1,
        stdout="",
        stderr="boom",
    )

    assert (
        _result_category(
            1,
            decisions=[],
            skill_requests=[],
            skill_repair_requests=[],
            script_executions=[script_failure],
            route_load_failed=True,
        )
        == "route_load_failed"
    )
    assert (
        _result_category(
            1,
            decisions=[],
            skill_requests=[],
            skill_repair_requests=[],
            script_executions=[script_failure],
        )
        == "script_failed"
    )
