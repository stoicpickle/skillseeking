from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app
from app.models import SkillCandidateLedger, SkillCandidateLedgerEntry
from app.negative_evidence import build_negative_evidence_report
from app.skill_candidate_ledger import load_candidate_ledger, write_candidate_ledger


def test_negative_evidence_reports_deferred_rejected_and_blocked_history_without_mutation(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    run_result = runner.invoke(
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
    assert run_result.exit_code == 0
    candidate_id = load_candidate_ledger(runs_dir).entries[0].candidate_id
    request_id = _promotion_input_request_id(runner, runs_dir)

    defer_result = runner.invoke(
        app,
        [
            "resolve-input-request",
            request_id,
            "--runs-dir",
            str(runs_dir),
            "--decision",
            "defer",
            "--reviewer",
            "Ada",
            "--notes",
            "Need more transfer evidence.",
            "--no-dry-run",
            "--json",
        ],
    )
    assert defer_result.exit_code == 0
    reject_result = runner.invoke(
        app,
        [
            "resolve-input-request",
            request_id,
            "--runs-dir",
            str(runs_dir),
            "--decision",
            "reject_candidate",
            "--reviewer",
            "Ada",
            "--notes",
            "Do not promote this candidate.",
            "--no-dry-run",
            "--json",
        ],
    )
    assert reject_result.exit_code == 0
    _append_blocked_candidate(runs_dir)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    report = build_negative_evidence_report(runs_dir=runs_dir)
    json_result = runner.invoke(
        app,
        ["negative-evidence", "--runs-dir", str(runs_dir), "--json"],
    )
    text_result = runner.invoke(
        app,
        ["negative-evidence", "--runs-dir", str(runs_dir)],
    )

    assert report.evidence_count == 3
    assert report.counts_by_type == {
        "candidate_blocked": 1,
        "resolution_defer": 1,
        "resolution_reject": 1,
    }
    assert sorted(item.evidence_type for item in report.items) == [
        "candidate_blocked",
        "resolution_defer",
        "resolution_reject",
    ]
    assert {item.candidate_id for item in report.items} == {
        candidate_id,
        "candidate_blocked_example",
    }
    _assert_no_mutation_flags(report.model_dump(mode="json"))

    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["evidence_count"] == 3
    assert data["counts_by_type"]["resolution_defer"] == 1
    assert data["counts_by_type"]["resolution_reject"] == 1
    assert data["counts_by_type"]["candidate_blocked"] == 1
    _assert_no_mutation_flags(data)

    assert text_result.exit_code == 0
    assert "NEGATIVE_EVIDENCE" in text_result.stdout
    assert "resolution_defer" in text_result.stdout
    assert "resolution_reject" in text_result.stdout
    assert "candidate_blocked" in text_result.stdout
    assert "Resolution ledger mutated: false" in text_result.stdout

    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_negative_evidence_can_filter_by_candidate(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    run_result = runner.invoke(
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
    assert run_result.exit_code == 0
    candidate_id = load_candidate_ledger(runs_dir).entries[0].candidate_id
    request_id = _promotion_input_request_id(runner, runs_dir)
    reject_result = runner.invoke(
        app,
        [
            "resolve-input-request",
            request_id,
            "--runs-dir",
            str(runs_dir),
            "--decision",
            "reject_candidate",
            "--reviewer",
            "Ada",
            "--notes",
            "Do not promote this candidate.",
            "--no-dry-run",
            "--json",
        ],
    )
    assert reject_result.exit_code == 0
    _append_blocked_candidate(runs_dir)

    result = runner.invoke(
        app,
        [
            "negative-evidence",
            "--runs-dir",
            str(runs_dir),
            "--candidate-id",
            candidate_id,
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["candidate_id"] == candidate_id
    assert data["evidence_count"] == 1
    assert data["items"][0]["evidence_type"] == "resolution_reject"
    assert data["items"][0]["candidate_id"] == candidate_id


def _promotion_input_request_id(runner: CliRunner, runs_dir: Path) -> str:
    result = runner.invoke(
        app,
        ["input-requests", "--runs-dir", str(runs_dir), "--json"],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    requests = [
        request
        for request in data["input_requests"]
        if request["kind"] == "promotion_approval"
    ]
    assert len(requests) == 1
    return str(requests[0]["id"])


def _append_blocked_candidate(runs_dir: Path) -> None:
    ledger = load_candidate_ledger(runs_dir)
    ledger.entries.append(
        SkillCandidateLedgerEntry(
            candidate_id="candidate_blocked_example",
            skill_name="secrets-permission-attack",
            capability="secrets permission attack",
            status="blocked",
            first_seen_run_id="run_blocked",
            last_seen_run_id="run_blocked",
            request_count=1,
            safety_flags=["rejected_skill"],
            quarantine_reason="skill may not request secrets permission",
            block_reason="skill may not request secrets permission",
            evidence_run_ids=["run_blocked"],
            created_at=datetime(2026, 6, 3, 12, 0, 0),
            updated_at=datetime(2026, 6, 3, 12, 0, 0),
        )
    )
    write_candidate_ledger(SkillCandidateLedger(entries=ledger.entries), runs_dir)


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
