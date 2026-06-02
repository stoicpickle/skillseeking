from __future__ import annotations

import json
import os
from datetime import datetime

import pytest

from app.agent_loop import run_task
from app.models import RunLog, SkillCandidateLedger, SkillCandidateLedgerEntry
from app.skill_candidate_ledger import (
    LOCK_FILENAME,
    SkillCandidateLedgerError,
    approve_candidate_promotion,
    candidate_id_for,
    candidate_review_queue_counts,
    candidate_review_queue_names,
    candidate_review_queues,
    ledger_path,
    load_candidate_ledger,
    record_run_in_candidate_ledger,
    write_candidate_ledger,
)


def _run_log(
    run_id: str,
    *,
    skill_requests: list[dict] | None = None,
    skill_repair_requests: list[dict] | None = None,
    rejected_skills: list[dict] | None = None,
) -> RunLog:
    return RunLog(
        run_id=run_id,
        task_id=f"task_{run_id}",
        task="test task",
        created_at=datetime(2026, 6, 1, 12, 0, 0),
        exit_code=0,
        result_category="success",
        plan=[],
        capability_decisions=[],
        governor_decisions=[],
        skills_loaded=[],
        skill_requests=skill_requests or [],
        skill_repair_requests=skill_repair_requests or [],
        rejected_skills=rejected_skills or [],
        trace=[],
    )


def _request(
    *,
    request_id: str = "skillreq_test",
    skill_name: str = "detect-contradictions",
    capability: str = "detect contradictions",
    input_schema: dict[str, str] | None = None,
    output_schema: dict[str, str] | None = None,
    temporary_skill: dict | None = None,
) -> dict:
    request = {
        "id": request_id,
        "task_id": "task_test",
        "missing_capability": capability,
        "reason": "No existing skill met threshold.",
        "desired_skill_name": skill_name,
        "input_schema": input_schema or {"claims": "array"},
        "output_schema": output_schema or {"contradictions": "array"},
        "success_criteria": ["Finds direct contradictions"],
        "failure_modes": ["Return none when claims do not conflict"],
        "risk_level": "low",
        "approval_required": False,
        "control_summary": {
            "governor_decision": "REQUEST_SKILL",
            "dominant_signal": "missing_skill",
            "confidence": 0.35,
            "risk_level": "low",
            "reversibility": "reversible",
            "approval_required": False,
            "approval_gate": "none",
            "blocked_reason": None,
            "evidence_to_promote": [
                "Metadata validation passes",
                "Human approval is recorded before durable promotion",
            ],
        },
        "status": "requested",
    }
    if temporary_skill is not None:
        request["temporary_skill"] = temporary_skill
    return request


def test_missing_skill_requests_increment_one_persistent_ledger_entry(tmp_path):
    runs_dir = tmp_path / "runs"
    request = _request()

    record_run_in_candidate_ledger(_run_log("run_a", skill_requests=[request]), runs_dir)
    record_run_in_candidate_ledger(_run_log("run_b", skill_requests=[request]), runs_dir)

    path = ledger_path(runs_dir)
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    ledger = load_candidate_ledger(runs_dir)
    assert len(ledger.entries) == 1
    entry = ledger.entries[0]
    assert entry.candidate_id == candidate_id_for("detect-contradictions", "detect contradictions")
    assert entry.status == "requested"
    assert entry.request_count == 2
    assert entry.evidence_run_ids == ["run_a", "run_b"]
    assert entry.first_seen_run_id == "run_a"
    assert entry.last_seen_run_id == "run_b"
    assert entry.human_approval_required
    assert "Human approval is recorded before durable promotion" in entry.promotion_requirements


def test_replaying_existing_run_does_not_regress_latest_evidence(tmp_path):
    runs_dir = tmp_path / "runs"
    run_a = _run_log("run_a", skill_requests=[_request()])
    run_b = _run_log("run_b", skill_requests=[_request()])

    record_run_in_candidate_ledger(run_a, runs_dir)
    record_run_in_candidate_ledger(run_b, runs_dir)
    before = load_candidate_ledger(runs_dir).entries[0]

    replay_path = record_run_in_candidate_ledger(run_a, runs_dir)

    after = load_candidate_ledger(runs_dir).entries[0]
    assert replay_path is None
    assert after.request_count == 2
    assert after.evidence_run_ids == ["run_a", "run_b"]
    assert after.last_seen_run_id == "run_b"
    assert after.updated_at == before.updated_at


def test_invalid_ledger_is_not_silently_overwritten(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    path = ledger_path(runs_dir)
    path.write_text("{not valid json", encoding="utf-8")

    with pytest.raises(SkillCandidateLedgerError):
        record_run_in_candidate_ledger(_run_log("run_a", skill_requests=[_request()]), runs_dir)

    assert path.read_text(encoding="utf-8") == "{not valid json"


def test_temporary_validation_success_records_temporary_evidence_without_promotion(tmp_path):
    runs_dir = tmp_path / "runs"
    request = _request(
        temporary_skill={
            "skill_name": "detect-contradictions",
            "skill_path": str(runs_dir / "artifacts" / "run_temp" / "skills" / "detect-contradictions" / "SKILL.md"),
            "validation_passed": True,
            "validation_reasons": [],
            "loaded": True,
        }
    )

    record_run_in_candidate_ledger(_run_log("run_temp", skill_requests=[request]), runs_dir)

    entry = load_candidate_ledger(runs_dir).entries[0]
    assert entry.status == "temporary"
    assert entry.validation_pass_count == 1
    assert entry.validation_failure_count == 0
    assert entry.successful_temporary_uses == 1
    assert entry.human_approval_required
    assert entry.status != "candidate"


def test_validation_failure_and_repair_request_record_repair_requirements(tmp_path):
    runs_dir = tmp_path / "runs"
    request = _request(
        request_id="skillreq_local",
        skill_name="local-python-analysis",
        capability="run local python analysis",
        temporary_skill={
            "skill_name": "local-python-analysis",
            "skill_path": str(runs_dir / "artifacts" / "run_fail" / "skills" / "local-python-analysis" / "SKILL.md"),
            "validation_passed": False,
            "validation_reasons": ["non-scripted skills must be low risk"],
            "loaded": False,
        },
    )
    repair = {
        "id": "repairreq_local",
        "task_id": "task_test",
        "skill_request_id": "skillreq_local",
        "skill_name": "local-python-analysis",
        "failed_capability": "run local python analysis",
        "failed_skill_path": request["temporary_skill"]["skill_path"],
        "failure_reasons": ["non-scripted skills must be low risk"],
        "repair_objective": "Revise the temporary Markdown skill so it satisfies the validator.",
        "constraints": ["Do not auto-load the repaired skill without a fresh validation pass."],
        "status": "requested",
    }

    record_run_in_candidate_ledger(
        _run_log("run_fail", skill_requests=[request], skill_repair_requests=[repair]),
        runs_dir,
    )

    entry = load_candidate_ledger(runs_dir).entries[0]
    assert entry.status == "draft"
    assert entry.validation_failure_count == 1
    assert entry.successful_temporary_uses == 0
    assert any("non-scripted skills must be low risk" in item for item in entry.repair_requirements)
    assert any("repairreq_local" in item for item in entry.repair_requirements)
    assert any("Do not auto-load" in item for item in entry.repair_requirements)


def test_rejected_skill_is_quarantined_and_blocked(tmp_path):
    runs_dir = tmp_path / "runs"
    rejection = {
        "name": "secrets-permission-attack",
        "path": str(tmp_path / "skills" / "secrets-permission-attack" / "SKILL.md"),
        "reasons": ["skill may not request secrets permission"],
    }

    record_run_in_candidate_ledger(_run_log("run_reject", rejected_skills=[rejection]), runs_dir)

    entry = load_candidate_ledger(runs_dir).entries[0]
    assert entry.skill_name == "secrets-permission-attack"
    assert entry.status == "blocked"
    assert entry.quarantine_reason == "skill may not request secrets permission"
    assert entry.block_reason == "skill may not request secrets permission"
    assert "rejected_skill" in entry.safety_flags
    assert entry.evidence_run_ids == ["run_reject"]


def test_duplicate_candidate_contracts_are_flagged_without_deleting_entries(tmp_path):
    runs_dir = tmp_path / "runs"
    first = _request(
        request_id="skillreq_a",
        skill_name="summarize-source",
        capability="summarize source",
        input_schema={"text": "string"},
        output_schema={"summary": "string"},
    )
    second = _request(
        request_id="skillreq_b",
        skill_name="source-summary",
        capability="source summary",
        input_schema={"text": "string"},
        output_schema={"summary": "string"},
    )

    record_run_in_candidate_ledger(_run_log("run_dup_a", skill_requests=[first]), runs_dir)
    record_run_in_candidate_ledger(_run_log("run_dup_b", skill_requests=[second]), runs_dir)

    ledger = load_candidate_ledger(runs_dir)
    assert len(ledger.entries) == 2
    duplicates = [entry for entry in ledger.entries if entry.duplicate_of]
    assert len(duplicates) == 1
    original = next(entry for entry in ledger.entries if entry.candidate_id == duplicates[0].duplicate_of)
    assert duplicates[0].duplicate_evidence == [
        f"matches input/output contract for {original.skill_name}"
    ]


def test_candidate_review_queues_classify_advisory_work(tmp_path):
    ledger = SkillCandidateLedger(
        entries=[
            SkillCandidateLedgerEntry(
                candidate_id="candidate_repeated",
                skill_name="detect-contradictions",
                capability="detect contradictions",
                status="requested",
                request_count=2,
                evidence_run_ids=["run_a", "run_b"],
            ),
            SkillCandidateLedgerEntry(
                candidate_id="candidate_ready",
                skill_name="argument-clustering",
                capability="argument clustering",
                status="temporary",
                request_count=1,
                validation_pass_count=1,
                successful_temporary_uses=1,
                human_approval_required=True,
                evidence_run_ids=["run_temp"],
            ),
            SkillCandidateLedgerEntry(
                candidate_id="candidate_repair",
                skill_name="local-python-analysis",
                capability="run local python analysis",
                status="draft",
                validation_failure_count=1,
                repair_requirements=["repair required: non-scripted skills must be low risk"],
                evidence_run_ids=["run_repair"],
            ),
            SkillCandidateLedgerEntry(
                candidate_id="candidate_blocked",
                skill_name="secrets-helper",
                capability="read secrets",
                status="blocked",
                block_reason="skill may not request secrets permission",
                evidence_run_ids=["run_blocked"],
            ),
            SkillCandidateLedgerEntry(
                candidate_id="candidate_duplicate",
                skill_name="source-summary",
                capability="source summary",
                status="requested",
                duplicate_of="candidate_original",
                duplicate_evidence=["matches input/output contract for summarize-source"],
                evidence_run_ids=["run_dup"],
            ),
        ]
    )

    queues = candidate_review_queues(ledger)

    assert [item.candidate_id for item in queues["repeated_requested_gap"]] == [
        "candidate_repeated"
    ]
    assert [item.candidate_id for item in queues["promotion_ready"]] == [
        "candidate_ready"
    ]
    assert [item.candidate_id for item in queues["repair_needed"]] == [
        "candidate_repair"
    ]
    assert [item.candidate_id for item in queues["blocked_or_quarantined"]] == [
        "candidate_blocked"
    ]
    assert [item.candidate_id for item in queues["duplicate_merge_needed"]] == [
        "candidate_duplicate"
    ]
    assert candidate_review_queue_counts(ledger) == {
        "blocked_or_quarantined": 1,
        "duplicate_merge_needed": 1,
        "promotion_ready": 1,
        "repair_needed": 1,
        "repeated_requested_gap": 1,
    }
    assert candidate_review_queue_names(ledger.entries[1]) == ["promotion_ready"]


def test_replaying_duplicate_run_does_not_rewrite_ledger(tmp_path):
    runs_dir = tmp_path / "runs"
    first = _request(
        request_id="skillreq_a",
        skill_name="summarize-source",
        capability="summarize source",
        input_schema={"text": "string"},
        output_schema={"summary": "string"},
    )
    second = _request(
        request_id="skillreq_b",
        skill_name="source-summary",
        capability="source summary",
        input_schema={"text": "string"},
        output_schema={"summary": "string"},
    )
    run_a = _run_log("run_dup_a", skill_requests=[first])
    run_b = _run_log("run_dup_b", skill_requests=[second])

    record_run_in_candidate_ledger(run_a, runs_dir)
    record_run_in_candidate_ledger(run_b, runs_dir)
    before = ledger_path(runs_dir).read_text(encoding="utf-8")

    replay_path = record_run_in_candidate_ledger(run_b, runs_dir)

    assert replay_path is None
    assert ledger_path(runs_dir).read_text(encoding="utf-8") == before


def test_stale_candidate_ledger_lock_is_recovered(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    lock_path = runs_dir / LOCK_FILENAME
    lock_path.write_text("pid=999999999\n", encoding="utf-8")

    record_run_in_candidate_ledger(_run_log("run_a", skill_requests=[_request()]), runs_dir)

    assert ledger_path(runs_dir).exists()
    assert not lock_path.exists()


def test_failed_lock_pid_write_closes_fd_and_removes_lock(tmp_path, monkeypatch):
    runs_dir = tmp_path / "runs"
    original_close = os.close
    closed_fds: list[int] = []

    def fail_write(fd: int, data: bytes) -> int:
        raise OSError("simulated write failure")

    def track_close(fd: int) -> None:
        closed_fds.append(fd)
        original_close(fd)

    monkeypatch.setattr(os, "write", fail_write)
    monkeypatch.setattr(os, "close", track_close)

    with pytest.raises(OSError, match="simulated write failure"):
        record_run_in_candidate_ledger(_run_log("run_a", skill_requests=[_request()]), runs_dir)

    assert closed_fds
    assert not (runs_dir / LOCK_FILENAME).exists()


def test_agent_loop_records_missing_skill_request_in_ledger(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"

    result = run_task(
        "Extract claims from these two sources and identify contradictions.",
        copied_seed_skills,
        runs_dir,
        create_temporary_skills=False,
    )

    assert result.exit_code == 1
    ledger = load_candidate_ledger(runs_dir)
    assert len(ledger.entries) == 1
    entry = ledger.entries[0]
    assert entry.skill_name == "detect-contradictions"
    assert entry.capability == "detect contradictions"
    assert entry.request_count == 1
    assert entry.evidence_run_ids == [result.run_log.run_id]


def test_agent_loop_preserves_run_when_candidate_ledger_is_corrupt(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    corrupt_ledger = ledger_path(runs_dir)
    corrupt_ledger.write_text("{not valid json", encoding="utf-8")

    result = run_task(
        "Extract claims from these two sources and identify contradictions.",
        copied_seed_skills,
        runs_dir,
        create_temporary_skills=False,
    )

    assert result.exit_code == 1
    assert result.run_log_path.exists()
    assert corrupt_ledger.read_text(encoding="utf-8") == "{not valid json"
    assert "LEDGER_RECORD_FAILED" in result.run_log.trace
    assert result.run_log.trace_events[-1].stage == "LEDGER_RECORD_FAILED"
    assert "invalid skill candidate ledger" in result.run_log.trace_events[-1].details["error"]


def _promotable_entry() -> SkillCandidateLedgerEntry:
    return SkillCandidateLedgerEntry(
        candidate_id="candidate_promotable",
        skill_name="argument-clustering",
        capability="argument clustering",
        status="temporary",
        request_count=1,
        successful_temporary_uses=1,
        validation_pass_count=1,
        promotion_requirements=["Human approval is recorded before durable promotion"],
        evidence_run_ids=["run_temp"],
    )


def test_approve_candidate_promotion_records_human_approval_without_installing(tmp_path):
    runs_dir = tmp_path / "runs"
    write_candidate_ledger(SkillCandidateLedger(entries=[_promotable_entry()]), runs_dir)

    entry = approve_candidate_promotion(
        runs_dir,
        "candidate_promotable",
        reviewer="Ada",
        notes="Validated temp use and reviewed promotion evidence.",
    )

    assert entry.status == "candidate"
    assert not entry.human_approval_required
    assert entry.promotion_approved_by == "Ada"
    assert entry.promotion_approved_at is not None
    assert entry.promotion_approval_notes == "Validated temp use and reviewed promotion evidence."
    persisted = load_candidate_ledger(runs_dir).entries[0]
    assert persisted.status == "candidate"
    assert persisted.promotion_approved_by == "Ada"


def test_approve_candidate_promotion_rejects_requested_or_blocked_entries(tmp_path):
    runs_dir = tmp_path / "runs"
    requested = _promotable_entry()
    requested.status = "requested"
    blocked = _promotable_entry()
    blocked.candidate_id = "candidate_blocked"
    blocked.status = "blocked"
    blocked.block_reason = "unsafe"
    write_candidate_ledger(SkillCandidateLedger(entries=[requested, blocked]), runs_dir)

    with pytest.raises(SkillCandidateLedgerError, match="only temporary candidates"):
        approve_candidate_promotion(runs_dir, "candidate_promotable", "Ada", "Reviewed")
    with pytest.raises(SkillCandidateLedgerError, match="blocked candidates"):
        approve_candidate_promotion(runs_dir, "candidate_blocked", "Ada", "Reviewed")
