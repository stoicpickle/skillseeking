from __future__ import annotations

import json
from pathlib import Path
from shutil import copytree

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.models import SkillCandidateLedger
from app.skill_candidate_ledger import (
    approve_candidate_promotion,
    load_candidate_ledger,
    write_candidate_ledger,
)
from app.stable_readiness import StableReadinessError, build_stable_readiness_report
from app.skill_receipt import SkillReceiptError


def test_stable_readiness_reports_ready_for_review_without_authorizing_routing(
    copied_seed_skills,
    tmp_path,
):
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
    candidate_id = load_candidate_ledger(runs_dir).entries[0].candidate_id
    approve_candidate_promotion(
        runs_dir,
        candidate_id,
        reviewer="Ada",
        notes="Validated candidate evidence before stable readiness review.",
    )
    ledger = load_candidate_ledger(runs_dir)
    ledger.entries[0].successful_temporary_uses = 10
    write_candidate_ledger(ledger, runs_dir)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    report = build_stable_readiness_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )
    json_result = runner.invoke(
        app,
        [
            "stable-readiness",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--json",
        ],
    )
    text_result = runner.invoke(
        app,
        [
            "stable-readiness",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
        ],
    )

    assert report.outcome == "ready_for_stable_review"
    assert report.ready_for_stable_review is True
    assert report.successful_temporary_uses == 10
    assert report.stable_review_approval_required is True
    assert report.stable_review_authorized is False
    assert report.stable_promotion_authorized is False
    assert report.stable_routing_enabled is False
    assert report.negative_evidence is not None
    assert report.negative_evidence.evidence_count == 0
    assert report.skill_receipt is not None
    assert _check_statuses(report) == {
        "candidate_duplicate": "pass",
        "durable_registry_conflict": "pass",
        "lifecycle": "pass",
        "negative_evidence": "pass",
        "proof_receipt": "warning",
        "stable_use_threshold": "pass",
        "validation_and_repair": "pass",
    }
    _assert_no_mutation_flags(report.model_dump(mode="json"))

    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["outcome"] == "ready_for_stable_review"
    assert data["ready_for_stable_review"] is True
    assert data["stable_review_authorized"] is False
    assert data["stable_promotion_authorized"] is False
    assert data["stable_routing_enabled"] is False
    assert data["negative_evidence"]["evidence_count"] == 0
    _assert_no_mutation_flags(data)

    assert text_result.exit_code == 0
    assert "STABLE_READINESS" in text_result.stdout
    assert "Outcome: ready_for_stable_review" in text_result.stdout
    assert "Ready for stable review: true" in text_result.stdout
    assert "Stable review authorized: false" in text_result.stdout
    assert "Stable promotion authorized: false" in text_result.stdout
    assert "Stable routing enabled: false" in text_result.stdout
    assert "Durable skills mutated: false" in text_result.stdout
    assert any("advisory stable-review evidence only for v1" in step for step in data["next_steps"])
    assert any("post-v1 workflow" in step for step in data["next_steps"])

    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_stable_readiness_blocks_duplicate_negative_candidate_evidence(
    copied_seed_skills,
    tmp_path,
):
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
    ledger = load_candidate_ledger(runs_dir)
    entry = ledger.entries[0]
    entry.duplicate_of = "candidate_existing"
    entry.duplicate_evidence = ["matches input/output contract for existing skill"]
    write_candidate_ledger(SkillCandidateLedger(entries=[entry]), runs_dir)

    report = build_stable_readiness_report(
        entry.candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )

    assert report.outcome == "blocked"
    assert report.ready_for_stable_review is False
    assert "candidate_duplicate" in report.blockers
    assert "negative_evidence_present" in report.blockers
    assert report.next_steps == [
        "Resolve blocked checks before stable review.",
        "Use negative-evidence and skill-receipt for the blocking proof details.",
    ]
    assert report.negative_evidence is not None
    assert report.negative_evidence.counts_by_type == {"candidate_duplicate": 1}
    _assert_no_mutation_flags(report.model_dump(mode="json"))


def test_stable_readiness_requires_recorded_candidate_promotion_evidence(
    copied_seed_skills,
    tmp_path,
):
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
    ledger = load_candidate_ledger(runs_dir)
    entry = ledger.entries[0]
    entry.status = "candidate"
    entry.successful_temporary_uses = 10
    entry.human_approval_required = True
    entry.promotion_approved_by = None
    entry.promotion_approved_at = None
    write_candidate_ledger(SkillCandidateLedger(entries=[entry]), runs_dir)

    report = build_stable_readiness_report(
        entry.candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )

    assert report.outcome == "blocked"
    assert "candidate_promotion_evidence_missing" in report.blockers
    assert "receipt_blocked" in report.blockers
    assert _check_statuses(report)["lifecycle"] == "missing"


def test_stable_readiness_blocks_same_name_durable_registry_conflict(
    copied_seed_skills,
    tmp_path,
):
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
    candidate_id = load_candidate_ledger(runs_dir).entries[0].candidate_id
    approve_candidate_promotion(runs_dir, candidate_id, "Ada", "Reviewed")
    ledger = load_candidate_ledger(runs_dir)
    entry = ledger.entries[0]
    entry.successful_temporary_uses = 10
    write_candidate_ledger(ledger, runs_dir)
    source_skill_dir = next(runs_dir.rglob(f"{entry.skill_name}/SKILL.md")).parent
    copytree(source_skill_dir, copied_seed_skills / entry.skill_name)

    report = build_stable_readiness_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )

    assert report.outcome == "blocked"
    assert "durable_skill_name_conflict" in report.blockers
    conflict = next(
        check for check in report.checks if check.category == "durable_registry_conflict"
    )
    assert conflict.status == "blocker"
    assert conflict.evidence_refs == [
        str(copied_seed_skills / entry.skill_name / "SKILL.md")
    ]


def test_stable_readiness_rejects_invalid_success_threshold(tmp_path):
    with pytest.raises(StableReadinessError, match="at least 1"):
        build_stable_readiness_report(
            "candidate_any",
            runs_dir=tmp_path / "runs",
            skills_dir=tmp_path / "skills",
            required_successful_temporary_uses=0,
        )


def test_stable_readiness_blocks_when_skill_receipt_unavailable(
    copied_seed_skills,
    tmp_path,
    monkeypatch,
):
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
    candidate_id = load_candidate_ledger(runs_dir).entries[0].candidate_id
    approve_candidate_promotion(runs_dir, candidate_id, "Ada", "Reviewed")
    ledger = load_candidate_ledger(runs_dir)
    ledger.entries[0].successful_temporary_uses = 10
    write_candidate_ledger(ledger, runs_dir)

    def fail_receipt(*args, **kwargs):
        raise SkillReceiptError("receipt source unavailable")

    monkeypatch.setattr("app.stable_readiness.build_skill_receipt_report", fail_receipt)

    report = build_stable_readiness_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )

    assert report.outcome == "blocked"
    assert report.ready_for_stable_review is False
    assert "skill_receipt_unavailable" in report.blockers
    assert report.skill_receipt is None
    assert report.warnings == [
        "skill_receipt_unavailable:receipt source unavailable"
    ]


def _check_statuses(report) -> dict[str, str]:
    return {check.category: check.status for check in report.checks}


def _assert_no_mutation_flags(data: dict) -> None:
    assert data["run_logs_mutated"] is False
    assert data["candidate_ledger_mutated"] is False
    assert data["resolution_ledger_mutated"] is False
    assert data["durable_skills_mutated"] is False
    assert data["registry_mutated"] is False
    assert data["governor_steering_enabled"] is False


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
