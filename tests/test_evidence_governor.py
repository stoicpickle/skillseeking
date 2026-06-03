from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app
from app.evidence_governor import build_evidence_governor_report
from app.skill_candidate_ledger import load_candidate_ledger


def test_evidence_governor_recommends_test_more_without_checkpoint_or_pair(
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
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = runner.invoke(
        app,
        [
            "evidence-governor",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["recommendation"] == "test_more"
    assert data["advisory_only"] is True
    assert data["approval_granted"] is False
    assert data["install_authorized"] is False
    assert data["route_steering_enabled"] is False
    assert data["evidence_checkpoint"]["outcome"] == "blocked"
    assert _signal(data, "evidence_checkpoint")["status"] == "missing"
    _assert_no_mutation_flags(data)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_evidence_governor_recommends_ask_when_approval_is_missing(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    baseline_run_id, treatment_run_id, candidate_id = _baseline_treatment_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    _append_checkpoint(runner, runs_dir)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    report = build_evidence_governor_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        baseline_run_id=baseline_run_id,
        treatment_run_id=treatment_run_id,
    )
    result = runner.invoke(
        app,
        [
            "evidence-governor",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--baseline-run-id",
            baseline_run_id,
            "--treatment-run-id",
            treatment_run_id,
            "--json",
        ],
    )
    text_result = runner.invoke(
        app,
        [
            "evidence-governor",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--baseline-run-id",
            baseline_run_id,
            "--treatment-run-id",
            treatment_run_id,
        ],
    )

    assert report.recommendation == "ask"
    assert report.approval_granted is False
    _assert_no_mutation_flags(report.model_dump(mode="json"))

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["recommendation"] == "ask"
    assert data["skill_receipt"]["candidate_usefulness"]["comparison"]["outcome"] == "improved"
    assert _signal(data, "receipt:utility")["status"] == "present"
    assert _signal(data, "receipt:approval")["status"] == "missing"
    assert _signal(data, "evidence_checkpoint")["status"] == "present"
    assert data["approval_granted"] is False
    assert data["promotion_authorized"] is False
    _assert_no_mutation_flags(data)

    assert text_result.exit_code == 0
    assert "EVIDENCE_GOVERNOR" in text_result.stdout
    assert "Recommendation: ask" in text_result.stdout
    assert "Approval granted: false" in text_result.stdout
    assert "Route steering enabled: false" in text_result.stdout

    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_evidence_governor_recommends_deny_when_negative_block_evidence_exists(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    baseline_run_id, treatment_run_id, candidate_id = _baseline_treatment_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
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
    _append_checkpoint(runner, runs_dir)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = runner.invoke(
        app,
        [
            "evidence-governor",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--baseline-run-id",
            baseline_run_id,
            "--treatment-run-id",
            treatment_run_id,
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["recommendation"] == "deny"
    assert "resolution_reject" in _signal(data, "negative_evidence")["blockers"]
    assert data["negative_evidence"]["evidence_count"] == 1
    assert data["approval_granted"] is False
    assert data["install_authorized"] is False
    _assert_no_mutation_flags(data)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_evidence_governor_recommends_defer_even_with_strong_review_proof(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    baseline_run_id, treatment_run_id, candidate_id = _baseline_treatment_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    _promote_and_approve_plan(runner, candidate_id, runs_dir, copied_seed_skills)
    _append_checkpoint(runner, runs_dir)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = runner.invoke(
        app,
        [
            "evidence-governor",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--baseline-run-id",
            baseline_run_id,
            "--treatment-run-id",
            treatment_run_id,
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["recommendation"] == "defer"
    assert _signal(data, "receipt:utility")["status"] == "present"
    assert _signal(data, "receipt:approval")["status"] == "present"
    assert _signal(data, "evidence_checkpoint")["status"] == "present"
    assert "write_mode_rollback_not_implemented" in _signal(
        data,
        "receipt:reversibility",
    )["blockers"]
    assert data["approval_granted"] is False
    assert data["install_authorized"] is False
    assert data["permission_widening_authorized"] is False
    assert data["route_steering_enabled"] is False
    _assert_no_mutation_flags(data)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def _baseline_treatment_candidate(
    runner: CliRunner,
    skills_dir: Path,
    runs_dir: Path,
) -> tuple[str, str, str]:
    baseline_result = runner.invoke(
        app,
        [
            "run",
            "Cluster arguments from these sources.",
            "--no-temporary-skills",
            "--skills-dir",
            str(skills_dir),
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert baseline_result.exit_code == 1
    baseline_run_id = _only_new_run_id(runs_dir, set())
    before_treatment = set(_run_ids(runs_dir))
    treatment_result = runner.invoke(
        app,
        [
            "run",
            "Cluster arguments from these sources.",
            "--skills-dir",
            str(skills_dir),
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert treatment_result.exit_code == 0
    treatment_run_id = _only_new_run_id(runs_dir, before_treatment)
    candidate_id = load_candidate_ledger(runs_dir).entries[0].candidate_id
    return baseline_run_id, treatment_run_id, candidate_id


def _promote_and_approve_plan(
    runner: CliRunner,
    candidate_id: str,
    runs_dir: Path,
    skills_dir: Path,
) -> None:
    promote_result = runner.invoke(
        app,
        [
            "promote-candidate",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--reviewer",
            "Ada",
            "--notes",
            "Reviewed temporary evidence.",
            "--json",
        ],
    )
    assert promote_result.exit_code == 0
    preview_result = runner.invoke(
        app,
        [
            "admit-candidate",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(skills_dir),
            "--json",
        ],
    )
    assert preview_result.exit_code == 0
    plan_digest = json.loads(preview_result.stdout)["write_plan"]["plan_digest"]
    admission_result = runner.invoke(
        app,
        [
            "admission-plan",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(skills_dir),
            "--json",
        ],
    )
    assert admission_result.exit_code == 0
    input_request = json.loads(admission_result.stdout)["input_request"]
    resolve_result = runner.invoke(
        app,
        [
            "resolve-input-request",
            input_request["id"],
            "--runs-dir",
            str(runs_dir),
            "--decision",
            "approve_review",
            "--reviewer",
            "Ada",
            "--notes",
            f"Reviewed durable admission evidence. plan_digest={plan_digest} expires_at=2099-01-01T00:00:00Z",
            "--no-dry-run",
            "--json",
        ],
    )
    assert resolve_result.exit_code == 0


def _append_checkpoint(runner: CliRunner, runs_dir: Path) -> None:
    result = runner.invoke(
        app,
        ["evidence-checkpoint", "--runs-dir", str(runs_dir), "--no-dry-run", "--json"],
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["outcome"] == "checkpoint_appended"


def _promotion_input_request_id(runner: CliRunner, runs_dir: Path) -> str:
    result = runner.invoke(
        app,
        ["input-requests", "--runs-dir", str(runs_dir), "--json"],
    )
    assert result.exit_code == 0
    requests = [
        request
        for request in json.loads(result.stdout)["input_requests"]
        if request["kind"] == "promotion_approval"
    ]
    assert len(requests) == 1
    return str(requests[0]["id"])


def _signal(data: dict, name: str) -> dict:
    matches = [signal for signal in data["signals"] if signal["name"] == name]
    assert len(matches) == 1
    return matches[0]


def _assert_no_mutation_flags(data: dict) -> None:
    assert data["run_logs_mutated"] is False
    assert data["candidate_ledger_mutated"] is False
    assert data["resolution_ledger_mutated"] is False
    assert data["checkpoint_ledger_mutated"] is False
    assert data["durable_skills_mutated"] is False
    assert data["registry_mutated"] is False
    assert data["governor_steering_enabled"] is False


def _run_ids(runs_dir: Path) -> list[str]:
    return [
        str(json.loads(path.read_text(encoding="utf-8"))["run_id"])
        for path in sorted(runs_dir.glob("run_*.json"))
    ]


def _only_new_run_id(runs_dir: Path, before: set[str]) -> str:
    new_run_ids = set(_run_ids(runs_dir)) - before
    assert len(new_run_ids) == 1
    return next(iter(new_run_ids))


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    if not path.exists():
        return {}
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
