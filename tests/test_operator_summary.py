from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app
from app.evidence_checkpoint import build_evidence_checkpoint_report
from app.models import (
    InputRequest,
    OperatorSummaryItem,
    OperatorSummaryReport,
    SkillCandidateLedger,
    SkillCandidateLedgerEntry,
)
from app.operator_summary import build_operator_summary_report
from app.skill_candidate_ledger import write_candidate_ledger


def test_operator_summary_empty_runs_is_read_only(tmp_path):
    runs_dir = tmp_path / "runs"
    before = _snapshot_tree(runs_dir)

    report = build_operator_summary_report(runs_dir=runs_dir)

    assert report.checkpoint.status == "no_checkpoint"
    assert report.blocked_items == []
    assert report.human_input_items == []
    assert report.promotion_ready_candidates == []
    assert report.missing_evidence_items == []
    assert report.unsafe_or_negative_items == []
    assert [item.decision for item in report.operator_decisions] == [
        "verify_or_checkpoint_evidence"
    ]
    assert report.operator_decisions[0].severity == "info"
    assert report.run_logs_mutated is False
    assert report.candidate_ledger_mutated is False
    assert report.resolution_ledger_mutated is False
    assert report.checkpoint_ledger_mutated is False
    assert report.durable_skills_mutated is False
    assert report.registry_mutated is False
    assert report.governor_steering_enabled is False
    assert _snapshot_tree(runs_dir) == before


def test_operator_summary_consolidates_candidate_queues_and_human_input(tmp_path):
    runs_dir = tmp_path / "runs"
    request = InputRequest(
        id="input_missing_docs",
        kind="missing_evidence",
        status="blocked",
        title="Recover missing docs evidence",
        reason="No source document was captured.",
        blocked_scope="candidate evidence",
        requested_decision="Recover the missing evidence.",
        options=["recover_evidence", "defer"],
        recommended_option="recover_evidence",
        evidence_refs=["run_missing"],
        next_commands=["Recover evidence and rerun operator-summary."],
        related_candidate_id="candidate_missing",
        created_at=datetime(2026, 6, 7, 10, 0, 0),
    )
    _write_run_log(runs_dir, "run_missing", input_requests=[request.model_dump(mode="json")])
    write_candidate_ledger(
        SkillCandidateLedger(
            entries=[
                SkillCandidateLedgerEntry(
                    candidate_id="candidate_ready",
                    skill_name="ready-skill",
                    capability="ready capability",
                    status="temporary",
                    validation_pass_count=1,
                    successful_temporary_uses=1,
                    evidence_run_ids=["run_ready"],
                ),
                SkillCandidateLedgerEntry(
                    candidate_id="candidate_blocked",
                    skill_name="blocked-skill",
                    capability="blocked capability",
                    status="blocked",
                    block_reason="Reviewer blocked this candidate.",
                    evidence_run_ids=["run_blocked"],
                ),
                SkillCandidateLedgerEntry(
                    candidate_id="candidate_repeated",
                    skill_name="repeated-skill",
                    capability="repeated capability",
                    status="requested",
                    request_count=2,
                    evidence_run_ids=["run_repeated"],
                ),
            ]
        ),
        runs_dir,
    )
    before = _snapshot_tree(runs_dir)

    report = build_operator_summary_report(runs_dir=runs_dir)

    assert report.input_request_kind_counts == {
        "missing_evidence": 1,
        "promotion_approval": 1,
    }
    assert report.candidate_review_queue_counts["promotion_ready"] == 1
    assert report.candidate_review_queue_counts["blocked_or_quarantined"] == 1
    assert report.candidate_review_queue_counts["repeated_requested_gap"] == 1
    human_ids = _ids(report.human_input_items)
    assert "human_input:input_missing_docs" in human_ids
    assert any(
        item.candidate_id == "candidate_ready"
        and item.title == "Review ready-skill for candidate promotion"
        for item in report.human_input_items
    )
    assert "promotion_ready:promotion_ready:candidate_ready" in _ids(
        report.promotion_ready_candidates
    )
    assert "blocked:blocked_or_quarantined:candidate_blocked" in _ids(report.blocked_items)
    assert "missing_evidence:input_missing_docs" in _ids(report.missing_evidence_items)
    assert "missing_evidence:repeated_requested_gap:candidate_repeated" in _ids(
        report.missing_evidence_items
    )
    assert [item.decision for item in report.operator_decisions[:3]] == [
        "resolve_blockers",
        "recover_missing_evidence",
        "review_candidate_promotion_evidence",
    ]
    assert report.operator_decisions[0].severity == "blocker"
    assert report.operator_decisions[1].priority < report.operator_decisions[2].priority
    assert _snapshot_tree(runs_dir) == before


def test_operator_summary_surfaces_negative_safety_and_unsafe_abort(tmp_path):
    runs_dir = tmp_path / "runs"
    _write_run_log(
        runs_dir,
        "run_unsafe",
        result_category="unsafe_aborted",
        capability_decisions=[
            {"decision": "ABORT_UNSAFE", "reason": "Task requested unsafe action."}
        ],
    )
    write_candidate_ledger(
        SkillCandidateLedger(
            entries=[
                SkillCandidateLedgerEntry(
                    candidate_id="candidate_safety",
                    skill_name="safety-skill",
                    capability="unsafe capability",
                    status="temporary",
                    safety_flags=["network access requested"],
                    evidence_run_ids=["run_safety"],
                ),
                SkillCandidateLedgerEntry(
                    candidate_id="candidate_repair",
                    skill_name="repair-skill",
                    capability="repair capability",
                    status="temporary",
                    validation_failure_count=1,
                    repair_requirements=["Fix output schema."],
                    evidence_run_ids=["run_repair"],
                ),
            ]
        ),
        runs_dir,
    )

    report = build_operator_summary_report(runs_dir=runs_dir)
    unsafe_ids = _ids(report.unsafe_or_negative_items)

    assert "candidate_safety_flags:candidate_safety" in unsafe_ids
    assert "unsafe_or_negative:candidate_repair_required:candidate_repair" in unsafe_ids
    assert "run_log_unsafe:run_unsafe" in unsafe_ids
    assert "run_log_abort_unsafe:run_unsafe:0" in unsafe_ids
    assert "blocked:repair_needed:candidate_repair" in _ids(report.blocked_items)
    assert any(
        command.startswith("skill-agent explain ")
        and command.endswith("run_unsafe.json")
        for command in report.next_steps
    )
    assert report.operator_decisions[0].decision == "resolve_blockers"
    assert report.operator_decisions[0].primary_command
    assert report.operator_decisions[0].primary_command.startswith("skill-agent explain ")
    assert any(
        item.decision == "review_negative_evidence"
        for item in report.operator_decisions
    )


def test_operator_summary_reports_checkpoint_diffs_without_mutating(tmp_path):
    runs_dir = tmp_path / "runs"
    _write_text(runs_dir / "kept.json", '{"value": 1}\n')
    _write_text(runs_dir / "removed.json", '{"remove": true}\n')
    appended = build_evidence_checkpoint_report(runs_dir=runs_dir, dry_run=False)
    assert appended.checkpoint_ledger_mutated is True
    (runs_dir / "removed.json").unlink()
    _write_text(runs_dir / "kept.json", '{"value": 2}\n')
    _write_text(runs_dir / "added.json", '{"added": true}\n')
    before = _snapshot_tree(runs_dir)

    report = build_operator_summary_report(runs_dir=runs_dir)

    assert report.checkpoint.status == "differs_from_latest"
    assert report.checkpoint.added_files == ["added.json"]
    assert report.checkpoint.changed_files == ["kept.json"]
    assert report.checkpoint.removed_files == ["removed.json"]
    assert report.checkpoint.added_count == 1
    assert report.checkpoint.changed_count == 1
    assert report.checkpoint.removed_count == 1
    assert _ids(report.checkpoint_change_items) == [
        "checkpoint_changed:kept.json",
        "checkpoint_removed:removed.json",
        "checkpoint_added:added.json",
    ]
    assert _snapshot_tree(runs_dir) == before


def test_operator_summary_surfaces_unavailable_checkpoint_as_actionable(tmp_path):
    runs_dir = tmp_path / "runs"
    _write_text(runs_dir / "evidence_checkpoints.json", "{not-json}\n")
    before = _snapshot_tree(runs_dir)

    report = build_operator_summary_report(runs_dir=runs_dir)

    assert report.checkpoint.status == "checkpoint_unavailable"
    assert report.checkpoint.blockers
    assert _ids(report.checkpoint_change_items) == ["checkpoint_unavailable"]
    assert report.checkpoint_change_items[0].severity == "blocker"
    assert any(
        command.startswith("skill-agent evidence-checkpoint ")
        and "--verify" in command
        for command in report.next_steps
    )
    assert report.operator_decisions[0].decision == "resolve_blockers"
    assert report.operator_decisions[0].severity == "blocker"
    assert report.operator_decisions[0].primary_command
    assert "evidence-checkpoint" in report.operator_decisions[0].primary_command
    assert "No active operator action surfaced" not in report.next_steps
    assert _snapshot_tree(runs_dir) == before


def test_operator_summary_clean_checkpoint_reports_no_active_decision(tmp_path):
    runs_dir = tmp_path / "runs"
    _write_text(runs_dir / "run_clean.json", '{"run_id": "run_clean"}\n')
    build_evidence_checkpoint_report(runs_dir=runs_dir, dry_run=False)
    before = _snapshot_tree(runs_dir)

    report = build_operator_summary_report(runs_dir=runs_dir)

    assert report.checkpoint.status == "matches_latest"
    assert [item.decision for item in report.operator_decisions] == [
        "no_active_operator_action"
    ]
    assert report.operator_decisions[0].primary_command is None
    assert _snapshot_tree(runs_dir) == before


def test_operator_summary_cli_json_and_text(tmp_path):
    runs_dir = tmp_path / "runs"
    _write_run_log(
        runs_dir,
        "run_unsafe",
        result_category="unsafe_aborted",
        capability_decisions=[
            {"decision": "ABORT_UNSAFE", "reason": "Task requested unsafe action."}
        ],
    )
    runner = CliRunner()

    json_result = runner.invoke(
        app,
        ["operator-summary", "--runs-dir", str(runs_dir), "--json"],
    )
    text_result = runner.invoke(app, ["operator-summary", "--runs-dir", str(runs_dir)])

    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    report = OperatorSummaryReport.model_validate(data)
    assert report.advisory_only is True
    assert report.unsafe_or_negative_items
    assert report.operator_decisions[0].decision == "resolve_blockers"
    assert report.durable_skills_mutated is False
    assert report.governor_steering_enabled is False

    assert text_result.exit_code == 0
    assert "OPERATOR_SUMMARY" in text_result.stdout
    assert "OPERATOR_DECISIONS" in text_result.stdout
    assert "resolve_blockers" in text_result.stdout
    assert "UNSAFE_OR_NEGATIVE" in text_result.stdout
    assert "MUTATION_BOUNDARY" in text_result.stdout
    assert "Governor steering enabled: false" in text_result.stdout


def _write_run_log(
    runs_dir: Path,
    run_id: str,
    *,
    input_requests: list[dict[str, object]] | None = None,
    capability_decisions: list[dict[str, object]] | None = None,
    result_category: str = "success",
) -> None:
    payload = {
        "run_id": run_id,
        "created_at": "2026-06-07T10:00:00",
        "result_category": result_category,
        "input_requests": input_requests or [],
        "capability_decisions": capability_decisions or [],
    }
    _write_text(runs_dir / f"{run_id}.json", json.dumps(payload, sort_keys=True) + "\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ids(items: list[OperatorSummaryItem]) -> list[str]:
    return [item.id for item in items]


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    if not path.exists():
        return {}
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
