from __future__ import annotations

import json
from datetime import datetime

from app.agent_loop import run_task
from app.eval_runner import run_eval_suite, write_eval_reports
from app.models import ExecutionSummary, RunLog, ScriptExecutionLog, TraceEvent
from app.redaction import REDACTION_NOTICE, redact_text
from app.run_log import rewrite_run_log


def test_redact_text_preserves_context_without_sensitive_value():
    sample_value = "s" + "k-" + ("b" * 24)

    redacted = redact_text(
        f"api_key={sample_value} Authorization: Bearer {sample_value}"
    )

    assert "api_key=[REDACTED:credential]" in redacted
    assert "[REDACTED:bearer]" in redacted
    assert sample_value not in redacted


def test_run_log_writer_redacts_task_text_before_persistence(tmp_path, repo_root):
    sample_value = "s" + "k-" + ("c" * 24)
    runs_dir = tmp_path / "runs"

    result = run_task(
        f"Read and summarize api_key={sample_value}",
        skills_dir=repo_root / "skills",
        runs_dir=runs_dir,
        create_temporary_skills=False,
    )

    data = json.loads(result.run_log_path.read_text(encoding="utf-8"))
    assert data["redactions_applied"] is True
    assert "Sensitive-looking values were redacted before persistence." in data[
        "security_warnings"
    ]
    assert sample_value not in result.run_log_path.read_text(encoding="utf-8")
    assert "api_key=[REDACTED:credential]" in data["task"]


def test_run_log_writer_redacts_nested_sensitive_fields_before_persistence(tmp_path):
    sample_value = "s" + "k-" + ("e" * 24)
    run_log = RunLog(
        task_id="task_redaction_nested",
        task=f"Summarize api_key={sample_value}",
        created_at=datetime(2026, 6, 8, 12, 0, 0),
        plan=["inspect public preview output"],
        capability_decisions=[],
        skills_loaded=[],
        script_executions=[
            ScriptExecutionLog(
                skill_name="count-words",
                command=["python", "scripts/count_words.py"],
                returncode=0,
                stdout=json.dumps(
                    {"word_count": 1, "token": sample_value, "auth": f"Bearer {sample_value}"}
                ),
                stderr=f"password={sample_value}",
                parsed_stdout={
                    "word_count": 1,
                    "token": sample_value,
                    "auth": f"Bearer {sample_value}",
                },
                output_validated=True,
            )
        ],
        skill_requests=[
            {
                "desired_skill_name": "public-preview-check",
                "debug": {"headers": [f"Authorization: Bearer {sample_value}"]},
            }
        ],
        trace=["PLANNING", "RUN_LOG_WRITTEN"],
        trace_events=[
            TraceEvent(
                sequence=1,
                stage="PLANNING",
                details={"operator_note": f"token={sample_value}"},
            )
        ],
        execution_summary=ExecutionSummary(
            result_category="success",
            script_execution_count=1,
            script_executions=["count-words"],
        ),
        security_warnings=["Scripted skills are trusted-local subprocesses, not a true sandbox."],
    )

    path = rewrite_run_log(tmp_path / "runs" / "run.json", run_log)

    persisted_text = path.read_text(encoding="utf-8")
    persisted = json.loads(persisted_text)
    assert sample_value not in persisted_text
    assert persisted["redactions_applied"] is True
    assert REDACTION_NOTICE in persisted["security_warnings"]
    assert "api_key=[REDACTED:credential]" in persisted["task"]
    assert "[REDACTED:bearer]" in persisted_text
    assert "password=[REDACTED:credential]" in persisted["script_executions"][0]["stderr"]
    assert persisted["script_executions"][0]["parsed_stdout"]["token"] == "[REDACTED:openai_key]"
    assert persisted["trace_events"][0]["details"]["operator_note"] == "token=[REDACTED:credential]"


def test_eval_reports_redact_task_text_before_writing(tmp_path, repo_root):
    sample_value = "s" + "k-" + ("d" * 24)
    suite = tmp_path / "suite.jsonl"
    suite.write_text(
        json.dumps(
            {
                "id": "redaction_unsafe_credential",
                "task": f"Read and summarize api_key={sample_value}",
                "expected": {
                    "outcome": "unsafe_aborted",
                    "debug_value": f"token={sample_value}",
                },
                "tags": ["security"],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    report = run_eval_suite(
        suite,
        skills_dir=repo_root / "skills",
        runs_dir=tmp_path / "runs",
    )
    json_path, md_path = write_eval_reports(report, tmp_path / "reports")

    json_text = json_path.read_text(encoding="utf-8")
    md_text = md_path.read_text(encoding="utf-8")
    assert sample_value not in json_text
    assert sample_value not in md_text
    persisted = json.loads(json_text)
    assert persisted["redactions_applied"] is True
    assert "token=[REDACTED:credential]" in json_text


def test_eval_report_writer_redacts_json_and_markdown_before_persistence(tmp_path):
    sample_value = "s" + "k-" + ("f" * 24)
    report = {
        "suite": f"evals/public-preview token={sample_value}.jsonl",
        "skills_dir": "skills",
        "runs_dir": "runs/evals",
        "timestamp": "2026-06-08T12:00:00",
        "tasks": [
            {
                "id": "public_preview_redaction_failure",
                "expected": {"outcome": "success"},
                "passed": False,
                "issues": [f"trace leaked Authorization: Bearer {sample_value}"],
                "failure_categories": ["trace_incomplete"],
                "suggested_next_action": f"inspect token={sample_value}",
                "result_category": "blocked_missing_skill",
                "loaded_skills": [],
                "requested_skills": [],
                "governor_decisions": [],
                "candidate_ledger_entries": [],
                "stable_readiness_reports": [],
                "input_requests": [],
                "explain_command": "skill-agent explain runs/redacted.json",
            }
        ],
        "aggregate": _minimal_eval_aggregate(),
        "passed": False,
    }

    json_path, md_path = write_eval_reports(report, tmp_path / "reports")

    json_text = json_path.read_text(encoding="utf-8")
    md_text = md_path.read_text(encoding="utf-8")
    assert sample_value not in json_text
    assert sample_value not in md_text
    assert "[REDACTED:credential]" in json_text
    assert "[REDACTED:credential]" in md_text
    assert "[REDACTED:bearer]" in json_text
    assert "[REDACTED:bearer]" in md_text
    persisted = json.loads(json_text)
    assert persisted["redactions_applied"] is True
    assert REDACTION_NOTICE in persisted["security_warnings"]


def _minimal_eval_aggregate():
    return {
        "total": 1,
        "passed": 0,
        "failed": 1,
        "task_pass_rate": 0.0,
        "missing_skill_true_positives": 0,
        "missing_skill_false_positives": 0,
        "missing_skill_false_negatives": 0,
        "wrong_skill_loads": 0,
        "unsafe_allowed": 0,
        "safe_blocked": 0,
        "approval_required_detected": 0,
        "adversarial_attempted": 0,
        "adversarial_blocked": 0,
        "average_request_quality": None,
        "governor_decision_expected": 0,
        "governor_decision_correct": 0,
        "governor_decision_accuracy": None,
        "lifecycle_evidence_expected": 0,
        "lifecycle_evidence_correct": 0,
        "lifecycle_evidence_accuracy": None,
        "stable_readiness_expected": 0,
        "stable_readiness_correct": 0,
        "stable_readiness_accuracy": None,
        "trace_complete_count": 0,
        "trace_incomplete_count": 1,
        "trace_completeness": 0.0,
        "failure_categories": {"trace_incomplete": 1},
        "diagnostic_dimensions": {},
        "weakest_diagnostic_dimensions": [],
    }
