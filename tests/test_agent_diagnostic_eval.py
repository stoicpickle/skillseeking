from __future__ import annotations

import json
from pathlib import Path

from app.admission_plan import build_admission_plan
from app.eval_runner import load_eval_suite, run_eval_suite, write_eval_reports
from app.skill_candidate_ledger import approve_candidate_promotion, load_candidate_ledger


def test_agent_diagnostic_eval_surfaces_improvement_dimensions(
    copied_seed_skills,
    repo_root: Path,
    tmp_path,
):
    suite = repo_root / "evals" / "agent_diagnostic_v0.jsonl"

    tasks = load_eval_suite(suite)
    report = run_eval_suite(suite, copied_seed_skills, tmp_path / "runs")
    json_path, md_path = write_eval_reports(report, tmp_path / "reports")

    assert len(tasks) == 16
    assert report["passed"] is True
    assert report["aggregate"]["total"] == 16
    assert report["aggregate"]["failed"] == 0
    assert report["aggregate"]["task_pass_rate"] == 1.0
    assert report["aggregate"]["average_request_quality"] >= 4.0
    assert report["aggregate"]["governor_decision_accuracy"] == 1.0
    assert report["aggregate"]["lifecycle_evidence_accuracy"] == 1.0
    assert report["aggregate"]["trace_completeness"] == 1.0
    assert report["aggregate"]["failure_categories"] == {}

    dimensions = report["aggregate"]["diagnostic_dimensions"]
    expected_dimensions = {
        "adversarial",
        "adversarial_routing",
        "append_only",
        "approval_required",
        "existing_skill",
        "lifecycle",
        "input_focus",
        "missing_skill",
        "repair_required",
        "request_quality",
        "review_queue",
        "resolution_ledger",
        "safety",
        "temporary_success",
    }
    assert expected_dimensions <= set(dimensions)
    assert dimensions["existing_skill"]["total"] == 3
    assert dimensions["missing_skill"]["total"] == 2
    assert dimensions["safety"]["total"] == 2
    assert dimensions["approval_required"]["total"] == 5
    assert dimensions["adversarial"]["total"] == 2
    assert dimensions["lifecycle"]["total"] == 2
    assert dimensions["input_focus"]["total"] == 7
    assert dimensions["resolution_ledger"]["total"] == 3
    assert dimensions["append_only"]["total"] == 1
    assert dimensions["request_quality"]["average_request_quality"] >= 4.0
    assert report["aggregate"]["weakest_diagnostic_dimensions"] == []

    persisted = json.loads(json_path.read_text(encoding="utf-8"))
    assert persisted["aggregate"]["diagnostic_dimensions"]["lifecycle"]["passed"] == 2
    input_request_kinds = {
        task["id"]: [request["kind"] for request in task["input_requests"]]
        for task in persisted["tasks"]
    }
    assert input_request_kinds["diagnostic_approval_dependency"] == ["safety_approval"]
    assert input_request_kinds["diagnostic_approval_file_read"] == ["safety_approval"]
    assert input_request_kinds["diagnostic_resolution_deferred_queue"] == ["safety_approval"]
    assert input_request_kinds["diagnostic_resolution_resolved_queue"] == ["safety_approval"]
    assert input_request_kinds["diagnostic_resolution_repeated_history"] == ["safety_approval"]
    assert "promotion_approval" in input_request_kinds["diagnostic_lifecycle_temporary_success"]
    assert "repair_review" in input_request_kinds["diagnostic_lifecycle_repair_required"]
    resolution_statuses = {
        task["id"]: [request["status"] for request in task["input_requests"]]
        for task in persisted["tasks"]
        if "resolution_ledger" in task["tags"]
    }
    assert resolution_statuses == {
        "diagnostic_resolution_deferred_queue": ["open"],
        "diagnostic_resolution_resolved_queue": ["resolved"],
        "diagnostic_resolution_repeated_history": ["resolved"],
    }
    assert persisted["tasks"][0]["suggested_next_action"] == ""
    assert persisted["tasks"][0]["explain_command"].startswith("skill-agent explain ")

    markdown = md_path.read_text(encoding="utf-8")
    assert "## Diagnostic Dimensions" in markdown
    assert "- lifecycle: pass_rate=1.0" in markdown
    assert "## Weakest Diagnostic Dimensions" in markdown
    assert "## Failure Categories" in markdown


def test_agent_diagnostic_eval_proves_admission_plan_followup(
    copied_seed_skills,
    repo_root: Path,
    tmp_path,
):
    suite = repo_root / "evals" / "agent_diagnostic_v0.jsonl"
    durable_before = _snapshot_tree(copied_seed_skills)
    report = run_eval_suite(suite, copied_seed_skills, tmp_path / "runs")
    eval_runs_dir = Path(report["runs_dir"])
    ledger = load_candidate_ledger(eval_runs_dir)
    entry = next(item for item in ledger.entries if item.skill_name == "argument-clustering")

    approve_candidate_promotion(
        eval_runs_dir,
        entry.candidate_id,
        reviewer="Ada",
        notes="Reviewed diagnostic temporary evidence.",
    )
    admission = build_admission_plan(
        entry.candidate_id,
        runs_dir=eval_runs_dir,
        skills_dir=copied_seed_skills,
    )

    assert admission.outcome == "ready_for_durable_review"
    assert admission.input_request is not None
    assert admission.input_request.kind == "durable_admission_review"
    assert admission.ready_for_durable_review is True
    assert admission.blockers == []
    assert admission.dry_run is True
    assert admission.auto_promotion_enabled is False
    assert admission.durable_skill_installed is False
    assert admission.ledger_mutated is False
    assert admission.registry_mutated is False
    assert admission.governor_steering_enabled is False
    assert _snapshot_tree(copied_seed_skills) == durable_before


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
