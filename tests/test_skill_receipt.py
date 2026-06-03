from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app
from app.skill_candidate_ledger import load_candidate_ledger
from app.skill_receipt import build_skill_receipt_report


def test_skill_receipt_summarizes_proof_bundle_without_mutation(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    baseline_result = runner.invoke(
        app,
        [
            "run",
            "Cluster arguments from these sources.",
            "--no-temporary-skills",
            "--skills-dir",
            str(copied_seed_skills),
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
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert treatment_result.exit_code == 0
    treatment_run_id = _only_new_run_id(runs_dir, before_treatment)
    candidate_id = load_candidate_ledger(runs_dir).entries[0].candidate_id
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    report = build_skill_receipt_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        baseline_run_id=baseline_run_id,
        treatment_run_id=treatment_run_id,
    )
    json_result = runner.invoke(
        app,
        [
            "skill-receipt",
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
            "skill-receipt",
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

    assert report.outcome == "blocked"
    proof_statuses = {proof.category: proof.status for proof in report.proofs}
    assert proof_statuses == {
        "approval": "missing",
        "compatibility": "blocked",
        "containment": "present",
        "origin": "present",
        "reversibility": "partial",
        "utility": "present",
    }
    compatibility = next(proof for proof in report.proofs if proof.category == "compatibility")
    assert "promotion_approval_missing" in compatibility.blockers
    reversibility = next(proof for proof in report.proofs if proof.category == "reversibility")
    assert "write_mode_rollback_not_implemented" in reversibility.blockers
    assert report.candidate_usefulness.baseline_comparison_available is True
    assert report.candidate_usefulness.comparison is not None
    assert report.candidate_usefulness.comparison.outcome == "improved"
    assert report.durable_admission_preview.write_plan.plan_digest
    assert report.durable_admission_preview.write_plan.plan_approval_verified is False
    _assert_no_mutation_flags(report.model_dump(mode="json"))

    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["outcome"] == "blocked"
    assert data["candidate_usefulness"]["comparison"]["outcome"] == "improved"
    assert data["durable_admission_preview"]["write_plan"]["plan_digest"]
    assert data["durable_admission_preview"]["write_plan"][
        "plan_approval_verified"
    ] is False
    _assert_no_mutation_flags(data)

    assert text_result.exit_code == 0
    assert "SKILL_RECEIPT" in text_result.stdout
    assert "origin: present" in text_result.stdout
    assert "utility: present" in text_result.stdout
    assert "approval: missing" in text_result.stdout
    assert "Durable skills mutated: false" in text_result.stdout

    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert not (runs_dir / "admission_snapshots").exists()
    assert not (runs_dir / "admission_staging").exists()


def _assert_no_mutation_flags(data: dict) -> None:
    assert data["run_logs_mutated"] is False
    assert data["candidate_ledger_mutated"] is False
    assert data["resolution_ledger_mutated"] is False
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
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
