from __future__ import annotations

import json

from typer.testing import CliRunner

from app.cli import app


def test_explain_valid_run_trace(copied_seed_skills, tmp_path):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    run_result = runner.invoke(
        app,
        [
            "run",
            "Extract claims from this article.",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert run_result.exit_code == 0
    run_log = next(runs_dir.glob("run_*.json"))

    result = runner.invoke(app, ["explain", str(run_log)])

    assert result.exit_code == 0
    assert "RUN" in result.stdout
    assert "CAPABILITIES" in result.stdout
    assert "USE_SKILL extract-claims" in result.stdout
    assert "GOVERNOR" in result.stdout
    assert "Dominant signal: skill_match" in result.stdout
    assert "TRACE" in result.stdout


def test_explain_missing_skill_trace(copied_seed_skills, tmp_path):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    run_result = runner.invoke(
        app,
        [
            "run",
            "Extract claims and identify contradictions.",
            "--no-temporary-skills",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert run_result.exit_code == 1
    run_log = next(runs_dir.glob("run_*.json"))

    result = runner.invoke(app, ["explain", str(run_log)])
    candidate_result = runner.invoke(app, ["explain", str(run_log), "--include-candidates"])

    assert result.exit_code == 0
    assert "REQUEST_SKILL - :: detect contradictions" in result.stdout
    assert "GOVERNOR" in result.stdout
    assert "Dominant signal: missing_skill" in result.stdout
    assert "detect-contradictions" in result.stdout
    assert candidate_result.exit_code == 0
    assert "CANDIDATE LEDGER" in candidate_result.stdout
    assert "Status: requested" in candidate_result.stdout
    assert "Promotion approval required: True" in candidate_result.stdout
    assert "Human approval required" not in candidate_result.stdout


def test_candidates_command_outputs_human_and_json(copied_seed_skills, tmp_path):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    run_result = runner.invoke(
        app,
        [
            "run",
            "Extract claims and identify contradictions.",
            "--no-temporary-skills",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert run_result.exit_code == 1

    text_result = runner.invoke(app, ["candidates", "--runs-dir", str(runs_dir)])
    json_result = runner.invoke(app, ["candidates", "--runs-dir", str(runs_dir), "--json"])

    assert text_result.exit_code == 0
    assert "SKILL_CANDIDATES" in text_result.stdout
    assert "Auto-promotion: disabled" in text_result.stdout
    assert "Skill: detect-contradictions" in text_result.stdout
    assert "Requests: 1" in text_result.stdout
    assert "Promotion approval required: True" in text_result.stdout
    assert "Human approval required" not in text_result.stdout
    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["candidate_count"] == 1
    assert data["auto_promotion_enabled"] is False
    assert data["status_counts"] == {"requested": 1}
    entry = data["entries"][0]
    assert entry["skill_name"] == "detect-contradictions"
    assert entry["capability"] == "detect contradictions"
    assert entry["status"] == "requested"
    assert entry["human_approval_required"] is True



def test_explain_rejected_unsafe_skill(tmp_path):
    run_log = tmp_path / "unsafe.json"
    run_log.write_text(
        json.dumps(
            {
                "run_id": "run_1",
                "task_id": "task_1",
                "task": "Show secrets.",
                "result_category": "unsafe_aborted",
                "plan": ["unsafe secrets request"],
                "capability_decisions": [
                    {
                        "decision": "ABORT_UNSAFE",
                        "selected_skill": None,
                        "capability": "unsafe secrets request",
                        "reason": "Requests involving secrets are unsafe.",
                        "best_match": {"skill_name": None, "score": 0, "coverage": "safety"},
                    }
                ],
                "skill_requests": [],
                "trace": ["PLANNING", "UNSAFE_ABORTED"],
            }
        ),
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(app, ["explain", str(run_log)])

    assert result.exit_code == 0
    assert "ABORT_UNSAFE" in result.stdout
    assert "GOVERNOR" in result.stdout
    assert "- none recorded" in result.stdout
    assert "Requests involving secrets are unsafe." in result.stdout


def test_explain_approval_governor_trace(copied_seed_skills, tmp_path):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    run_result = runner.invoke(
        app,
        [
            "run",
            "Read local files and summarize them.",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert run_result.exit_code == 1
    run_log = next(runs_dir.glob("run_*.json"))

    result = runner.invoke(app, ["explain", str(run_log)])

    assert result.exit_code == 0
    assert "ASK_HUMAN" in result.stdout
    assert "Dominant signal: approval_required" in result.stdout
    assert "Approval required: True" in result.stdout


def test_explain_malformed_trace_gives_useful_error(tmp_path):
    run_log = tmp_path / "bad.json"
    run_log.write_text("{", encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(app, ["explain", str(run_log)])

    assert result.exit_code != 0
    assert "Run log is not valid JSON" in result.stdout
