from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app
from app.models import SkillCandidateLedger, SkillCandidateLedgerEntry
from app.skill_candidate_ledger import write_candidate_ledger


def test_resolve_input_request_dry_run_classifies_all_kinds_without_mutation(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    run_log = runs_dir / "run_resolution.json"
    requests = [
        _request("inputreq_safety", "safety_approval", ["approve_workflow", "revise_task", "defer"]),
        _request("inputreq_promotion", "promotion_approval", ["approve_promotion", "repair_candidate", "reject_candidate", "defer"]),
        _request("inputreq_admission", "durable_admission_review", ["approve_review", "repair_candidate", "block", "defer"]),
        _request("inputreq_repair", "repair_review", ["repair_candidate", "reject_candidate", "defer"]),
        _request("inputreq_ambiguity", "ambiguity_resolution", ["merge_candidate", "keep_separate", "reject_candidate", "defer"]),
        _request("inputreq_missing", "missing_evidence", ["repair_candidate", "recover_evidence", "block", "defer"], status="blocked"),
    ]
    run_log.write_text(
        json.dumps(
            {
                "run_id": "run_resolution",
                "created_at": "2026-06-03T12:00:00",
                "input_requests": requests,
            }
        ),
        encoding="utf-8",
    )
    before = _snapshot_tree(runs_dir)
    runner = CliRunner()

    cases = [
        ("inputreq_safety", "approve_workflow", "approve", "resolved", None, "Inspect"),
        ("inputreq_safety", "revise_task", "revise", "resolved", "test scope", "Revise"),
        ("inputreq_safety", "defer", "defer", "open", "test scope", "open"),
        ("inputreq_promotion", "approve_promotion", "approve", "resolved", None, "promote-candidate"),
        ("inputreq_promotion", "repair_candidate", "repair", "resolved", "test scope", "Repair"),
        ("inputreq_promotion", "reject_candidate", "reject", "resolved", "test scope", "durable promotion"),
        ("inputreq_admission", "approve_review", "approve", "resolved", None, "durable admission"),
        ("inputreq_admission", "block", "block", "resolved", "test scope", "blocked"),
        ("inputreq_repair", "reject_candidate", "reject", "resolved", "test scope", "durable promotion"),
        ("inputreq_ambiguity", "merge_candidate", "merge", "resolved", None, "Inspect"),
        ("inputreq_ambiguity", "keep_separate", "keep_separate", "resolved", None, "Inspect"),
        ("inputreq_missing", "recover_evidence", "recover", "resolved", None, "Recover"),
    ]

    for request_id, decision, resolution_class, proposed_status, remaining_scope, next_step in cases:
        result = runner.invoke(
            app,
            [
                "resolve-input-request",
                request_id,
                "--runs-dir",
                str(runs_dir),
                "--decision",
                decision,
                "--reviewer",
                "Ada",
                "--notes",
                f"Reviewed {request_id}.",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["dry_run"] is True
        assert data["decision"] == decision
        assert data["resolution_class"] == resolution_class
        assert data["proposed_status"] == proposed_status
        assert data["remaining_blocked_scope"] == remaining_scope
        assert next_step in " ".join(data["next_steps"])
        assert data["request"]["kind"] == next(
            request["kind"] for request in requests if request["id"] == request_id
        )
        assert data["sources"][0]["source_type"] == "run_log"
        assert data["run_logs_mutated"] is False
        assert data["candidate_ledger_mutated"] is False
        assert data["resolution_ledger_mutated"] is False
        assert data["durable_skills_mutated"] is False
        assert data["governor_steering_enabled"] is False

    assert _snapshot_tree(runs_dir) == before


def test_resolve_input_request_reads_candidate_ledger_without_mutating_it(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    write_candidate_ledger(
        SkillCandidateLedger(
            entries=[
                SkillCandidateLedgerEntry(
                    candidate_id="candidate_ledger_resolution",
                    skill_name="ledger-resolution",
                    capability="ledger resolution",
                    status="temporary",
                    request_count=2,
                    successful_temporary_uses=1,
                    validation_pass_count=1,
                    evidence_run_ids=["run_ledger_resolution"],
                    human_approval_required=True,
                )
            ]
        ),
        runs_dir,
    )
    before = _snapshot_tree(runs_dir)
    runner = CliRunner()

    queue_result = runner.invoke(app, ["input-requests", "--runs-dir", str(runs_dir), "--json"])
    assert queue_result.exit_code == 0
    queue = json.loads(queue_result.stdout)
    request_id = queue["input_request_items"][0]["request"]["id"]

    result = runner.invoke(
        app,
        [
            "resolve-input-request",
            request_id,
            "--runs-dir",
            str(runs_dir),
            "--decision",
            "approve_promotion",
            "--reviewer",
            "Ada",
            "--notes",
            "Reviewed ledger evidence.",
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["resolution_class"] == "approve"
    assert data["proposed_status"] == "resolved"
    assert data["sources"][0]["source_type"] == "candidate_ledger"
    assert data["sources"][0]["source_path"].endswith("skill_candidate_ledger.json")
    assert data["candidate_ledger_mutated"] is False
    assert _snapshot_tree(runs_dir) == before


def test_resolve_input_request_rejects_invalid_decision_and_non_dry_run(tmp_path):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    (runs_dir / "run_resolution.json").write_text(
        json.dumps(
            {
                "run_id": "run_resolution",
                "created_at": "2026-06-03T12:00:00",
                "input_requests": [
                    _request("inputreq_safety", "safety_approval", ["approve_workflow", "defer"])
                ],
            }
        ),
        encoding="utf-8",
    )
    before = _snapshot_tree(runs_dir)
    runner = CliRunner()

    invalid = runner.invoke(
        app,
        [
            "resolve-input-request",
            "inputreq_safety",
            "--runs-dir",
            str(runs_dir),
            "--decision",
            "repair_candidate",
            "--reviewer",
            "Ada",
            "--notes",
            "Reviewed.",
        ],
    )
    missing_decision = runner.invoke(
        app,
        [
            "resolve-input-request",
            "inputreq_safety",
            "--runs-dir",
            str(runs_dir),
            "--reviewer",
            "Ada",
            "--notes",
            "Reviewed.",
        ],
    )
    non_dry_run = runner.invoke(
        app,
        [
            "resolve-input-request",
            "inputreq_safety",
            "--runs-dir",
            str(runs_dir),
            "--decision",
            "approve_workflow",
            "--reviewer",
            "Ada",
            "--notes",
            "Reviewed.",
            "--no-dry-run",
        ],
    )

    assert invalid.exit_code == 1
    assert "is not valid" in invalid.stdout
    assert missing_decision.exit_code == 1
    assert "decision is required" in missing_decision.stdout
    assert non_dry_run.exit_code == 1
    assert "dry-run only" in non_dry_run.stdout
    assert _snapshot_tree(runs_dir) == before


def _request(
    request_id: str,
    kind: str,
    options: list[str],
    status: str = "open",
) -> dict[str, object]:
    return {
        "id": request_id,
        "kind": kind,
        "status": status,
        "title": f"Resolve {kind}",
        "reason": "Test request.",
        "blocked_scope": "test scope",
        "requested_decision": "Choose an option.",
        "options": options,
        "recommended_option": options[0],
        "evidence_refs": ["run_resolution"],
        "next_commands": ["Inspect evidence."],
        "related_run_id": "run_resolution",
        "related_candidate_id": "candidate_resolution",
        "related_skill_request_id": "skillreq_resolution",
        "created_at": "2026-06-03T12:00:00",
    }


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
