from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.candidate_usefulness import build_candidate_usefulness_report
from app.cli import app
from app.models import SkillCandidateLedger, SkillCandidateLedgerEntry
from app.skill_candidate_ledger import load_candidate_ledger, write_candidate_ledger


def test_candidate_usefulness_reports_successful_temporary_skill_without_mutation(
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

    report = build_candidate_usefulness_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )
    json_result = runner.invoke(
        app,
        [
            "candidate-usefulness",
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
            "candidate-usefulness",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
        ],
    )

    assert report.outcome == "usefulness_supported"
    assert report.usefulness_supported is True
    assert report.baseline_comparison_available is False
    assert report.successful_temporary_uses == 1
    assert report.validation_pass_count == 1
    assert report.validation_failure_count == 0
    assert report.admission_plan_outcome == "needs_promotion_approval"
    assert report.admission_plan_ready is False
    assert report.matching_successful_run_ids == [report.evidence_runs[0].run_id]
    assert report.evidence_runs[0].successful is True
    assert report.evidence_runs[0].validation_passed is True
    assert report.evidence_runs[0].loaded is True
    assert report.warnings == ["baseline_comparison_missing"]
    _assert_no_mutation_flags(report.model_dump(mode="json"))

    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["outcome"] == "usefulness_supported"
    assert data["usefulness_supported"] is True
    assert data["matching_successful_run_ids"] == report.matching_successful_run_ids
    _assert_no_mutation_flags(data)
    assert text_result.exit_code == 0
    assert "CANDIDATE_USEFULNESS" in text_result.stdout
    assert "Outcome: usefulness_supported" in text_result.stdout
    assert "Usefulness supported: true" in text_result.stdout
    assert "Run logs mutated: false" in text_result.stdout

    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert not (runs_dir / "admission_snapshots").exists()
    assert not (runs_dir / "admission_staging").exists()


def test_candidate_usefulness_reports_repair_required_candidate(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    run_result = runner.invoke(
        app,
        [
            "run",
            "Run local Python analysis on this text.",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert run_result.exit_code == 1
    candidate_id = load_candidate_ledger(runs_dir).entries[0].candidate_id
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = runner.invoke(
        app,
        [
            "candidate-usefulness",
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
    assert data["outcome"] == "repair_required"
    assert data["usefulness_supported"] is False
    assert data["validation_failure_count"] == 1
    assert data["evidence_runs"][0]["repair_requested"] is True
    assert "candidate_repair_required" in data["blockers"]
    _assert_no_mutation_flags(data)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_candidate_usefulness_reports_requested_candidate_needs_temporary_use(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    run_result = runner.invoke(
        app,
        [
            "run",
            "Extract claims from these two sources and identify contradictions.",
            "--no-temporary-skills",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert run_result.exit_code == 1
    candidate_id = load_candidate_ledger(runs_dir).entries[0].candidate_id
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = runner.invoke(
        app,
        [
            "candidate-usefulness",
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
    assert data["outcome"] == "needs_successful_temporary_use"
    assert data["usefulness_supported"] is False
    assert data["successful_temporary_uses"] == 0
    assert data["matching_successful_run_ids"] == []
    assert data["blockers"] == []
    assert data["evidence_runs"][0]["matching_request_ids"]
    assert data["evidence_runs"][0]["temporary_skill_paths"] == []
    _assert_no_mutation_flags(data)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_candidate_usefulness_reports_missing_evidence_without_rewriting_ledger(
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    write_candidate_ledger(
        SkillCandidateLedger(
            entries=[
                SkillCandidateLedgerEntry(
                    candidate_id="candidate_missing_evidence",
                    skill_name="missing-evidence",
                    capability="missing evidence",
                    status="temporary",
                    successful_temporary_uses=1,
                    validation_pass_count=1,
                    evidence_run_ids=["run_missing"],
                )
            ]
        ),
        runs_dir,
    )
    ledger_before = (runs_dir / "skill_candidate_ledger.json").read_bytes()

    result = CliRunner().invoke(
        app,
        [
            "candidate-usefulness",
            "candidate_missing_evidence",
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["outcome"] == "evidence_missing"
    assert "evidence_run_log_missing" in data["blockers"]
    assert data["evidence_runs"] == [
        {
            "found": False,
            "loaded": None,
            "matching_request_ids": [],
            "repair_requested": False,
            "result_category": None,
            "run_id": "run_missing",
            "run_log_path": None,
            "successful": False,
            "temporary_skill_paths": [],
            "validation_passed": None,
        }
    ]
    _assert_no_mutation_flags(data)
    assert (runs_dir / "skill_candidate_ledger.json").read_bytes() == ledger_before


def test_candidate_usefulness_blocks_counter_only_candidate_without_run_evidence(
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    write_candidate_ledger(
        SkillCandidateLedger(
            entries=[
                SkillCandidateLedgerEntry(
                    candidate_id="candidate_counter_only",
                    skill_name="counter-only",
                    capability="counter only",
                    status="temporary",
                    successful_temporary_uses=1,
                    validation_pass_count=1,
                )
            ]
        ),
        runs_dir,
    )
    ledger_before = (runs_dir / "skill_candidate_ledger.json").read_bytes()

    result = CliRunner().invoke(
        app,
        [
            "candidate-usefulness",
            "candidate_counter_only",
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["outcome"] == "evidence_missing"
    assert "candidate_evidence_runs_missing" in data["blockers"]
    assert data["matching_successful_run_ids"] == []
    _assert_no_mutation_flags(data)
    assert (runs_dir / "skill_candidate_ledger.json").read_bytes() == ledger_before


def test_candidate_usefulness_rejects_unknown_candidate_without_rewriting_ledger(
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    write_candidate_ledger(SkillCandidateLedger(), runs_dir)
    ledger_before = (runs_dir / "skill_candidate_ledger.json").read_bytes()

    result = CliRunner().invoke(
        app,
        [
            "candidate-usefulness",
            "candidate_missing",
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(tmp_path / "skills"),
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert "candidate not found: candidate_missing" in result.stdout
    assert (runs_dir / "skill_candidate_ledger.json").read_bytes() == ledger_before


def _assert_no_mutation_flags(data: dict) -> None:
    assert data["dry_run"] is True
    assert data["run_logs_mutated"] is False
    assert data["candidate_ledger_mutated"] is False
    assert data["durable_skills_mutated"] is False
    assert data["registry_mutated"] is False
    assert data["governor_steering_enabled"] is False


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
