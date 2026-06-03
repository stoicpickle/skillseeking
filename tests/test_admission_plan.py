from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from shutil import copytree

import pytest
from typer.testing import CliRunner

from app.admission_plan import AdmissionPlanError, build_admission_plan
from app.agent_loop import run_task
from app.cli import app
from app.cli_output import emit_admission_plan_output
from app.models import SkillCandidateLedger, SkillCandidateLedgerEntry
from app.skill_candidate_ledger import (
    approve_candidate_promotion,
    candidate_id_for,
    load_candidate_ledger,
    write_candidate_ledger,
)


def test_promoted_candidate_with_valid_source_is_ready_for_durable_review(
    copied_seed_skills, tmp_path
):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _temporary_candidate(copied_seed_skills, runs_dir)
    approve_candidate_promotion(
        runs_dir,
        candidate_id,
        reviewer="Ada",
        notes="Reviewed temporary evidence.",
    )

    before_ledger = (runs_dir / "skill_candidate_ledger.json").read_text(encoding="utf-8")
    before_source = source_path.read_text(encoding="utf-8")
    durable_before = sorted(path.name for path in copied_seed_skills.iterdir())

    report = build_admission_plan(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )

    assert report.outcome == "ready_for_durable_review"
    assert report.ready_for_durable_review is True
    assert report.dry_run is True
    assert report.durable_skill_installed is False
    assert report.ledger_mutated is False
    assert report.registry_mutated is False
    assert report.governor_steering_enabled is False
    assert report.selected_source_artifact == str(source_path)
    assert report.blockers == []
    assert (runs_dir / "skill_candidate_ledger.json").read_text(encoding="utf-8") == before_ledger
    assert source_path.read_text(encoding="utf-8") == before_source
    assert sorted(path.name for path in copied_seed_skills.iterdir()) == durable_before


def test_temporary_candidate_preview_needs_promotion_approval(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"
    candidate_id, _ = _temporary_candidate(copied_seed_skills, runs_dir)

    report = build_admission_plan(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )

    assert report.outcome == "needs_promotion_approval"
    assert report.ready_for_durable_review is False
    assert report.blockers == ["promotion_approval_missing"]


def test_runs_dir_relative_source_skill_path_is_resolved(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _temporary_candidate(copied_seed_skills, runs_dir)
    approve_candidate_promotion(runs_dir, candidate_id, "Ada", "Reviewed")
    run_log = next(runs_dir.rglob("run_*.json"))
    data = json.loads(run_log.read_text(encoding="utf-8"))
    data["skill_requests"][0]["temporary_skill"]["skill_path"] = str(
        source_path.relative_to(runs_dir)
    )
    run_log.write_text(json.dumps(data), encoding="utf-8")

    report = build_admission_plan(candidate_id, runs_dir=runs_dir, skills_dir=copied_seed_skills)

    assert report.outcome == "ready_for_durable_review"
    assert report.selected_source_artifact == str(source_path)
    assert report.blockers == []


def test_missing_candidate_raises_admission_plan_error(tmp_path):
    runs_dir = tmp_path / "runs"
    write_candidate_ledger(SkillCandidateLedger(), runs_dir)

    with pytest.raises(AdmissionPlanError, match="candidate not found"):
        build_admission_plan("candidate_missing", runs_dir=runs_dir, skills_dir=tmp_path / "skills")


def test_missing_run_log_creates_evidence_blocker(tmp_path):
    runs_dir = tmp_path / "runs"
    write_candidate_ledger(SkillCandidateLedger(entries=[_approved_entry()]), runs_dir)

    report = build_admission_plan(
        "candidate_manual",
        runs_dir=runs_dir,
        skills_dir=tmp_path / "skills",
    )

    assert report.outcome == "evidence_incomplete"
    assert "evidence_run_log_missing" in report.blockers
    assert "source_skill_path_missing" in report.blockers


def test_missing_source_path_creates_source_blocker(tmp_path):
    runs_dir = tmp_path / "runs"
    candidate_id = candidate_id_for("argument-clustering", "argument clustering")
    entry = _approved_entry(candidate_id=candidate_id)
    write_candidate_ledger(SkillCandidateLedger(entries=[entry]), runs_dir)
    (runs_dir / "run_manual.json").write_text(
        json.dumps(
            {
                "run_id": "run_manual",
                "result_category": "success",
                "skill_requests": [
                    {
                        "id": "skillreq_manual",
                        "desired_skill_name": "argument-clustering",
                        "missing_capability": "argument clustering",
                        "temporary_skill": {
                            "skill_name": "argument-clustering",
                            "validation_passed": True,
                            "validation_reasons": [],
                            "loaded": True,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = build_admission_plan(candidate_id, runs_dir=runs_dir, skills_dir=tmp_path / "skills")

    assert report.outcome == "evidence_incomplete"
    assert "source_skill_path_missing" in report.blockers


def test_missing_source_skill_file_creates_source_blocker(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _temporary_candidate(copied_seed_skills, runs_dir)
    approve_candidate_promotion(runs_dir, candidate_id, "Ada", "Reviewed")
    source_path.unlink()

    report = build_admission_plan(candidate_id, runs_dir=runs_dir, skills_dir=copied_seed_skills)

    assert report.outcome == "evidence_incomplete"
    assert "source_skill_missing" in report.blockers


def test_source_path_outside_runs_blocks_without_source_io(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"
    candidate_id, _ = _temporary_candidate(copied_seed_skills, runs_dir)
    approve_candidate_promotion(runs_dir, candidate_id, "Ada", "Reviewed")
    outside_source = tmp_path / "outside" / "argument-clustering" / "SKILL.md"
    outside_source.parent.mkdir(parents=True)
    outside_source.write_text("not a real skill", encoding="utf-8")
    run_log = next(runs_dir.rglob("run_*.json"))
    data = json.loads(run_log.read_text(encoding="utf-8"))
    data["skill_requests"][0]["temporary_skill"]["skill_path"] = str(outside_source)
    run_log.write_text(json.dumps(data), encoding="utf-8")

    report = build_admission_plan(candidate_id, runs_dir=runs_dir, skills_dir=copied_seed_skills)

    assert report.outcome == "blocked"
    assert "source_path_outside_runs" in report.blockers
    assert "source_skill_parse_failed" not in report.blockers
    assert report.source_artifacts[0].exists is False
    assert report.source_artifacts[0].parsed is False


def test_source_validation_failure_is_reported(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _temporary_candidate(copied_seed_skills, runs_dir)
    approve_candidate_promotion(runs_dir, candidate_id, "Ada", "Reviewed")
    text = source_path.read_text(encoding="utf-8")
    source_path.write_text(text.replace("risk_level: low", "risk_level: medium"), encoding="utf-8")

    report = build_admission_plan(candidate_id, runs_dir=runs_dir, skills_dir=copied_seed_skills)

    assert report.outcome == "evidence_incomplete"
    assert "source_validation_failed" in report.blockers


def test_durable_same_name_collision_blocks(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _temporary_candidate(copied_seed_skills, runs_dir)
    approve_candidate_promotion(runs_dir, candidate_id, "Ada", "Reviewed")
    copytree(source_path.parent, copied_seed_skills / "argument-clustering")

    report = build_admission_plan(candidate_id, runs_dir=runs_dir, skills_dir=copied_seed_skills)

    assert report.outcome == "blocked"
    assert "durable_name_collision" in report.blockers
    assert report.durable_registry.name_collision["skill_name"] == "argument-clustering"


def test_durable_contract_overlap_warns(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _temporary_candidate(copied_seed_skills, runs_dir)
    approve_candidate_promotion(runs_dir, candidate_id, "Ada", "Reviewed")
    overlap_dir = copied_seed_skills / "argument-clustering-copy"
    copytree(source_path.parent, overlap_dir)
    overlap_file = overlap_dir / "SKILL.md"
    overlap_file.write_text(
        overlap_file.read_text(encoding="utf-8").replace(
            "name: argument-clustering",
            "name: argument-clustering-copy",
        ),
        encoding="utf-8",
    )

    report = build_admission_plan(candidate_id, runs_dir=runs_dir, skills_dir=copied_seed_skills)

    assert report.outcome == "ready_for_durable_review"
    assert "durable_contract_overlap" in report.warnings
    assert report.durable_registry.contract_overlaps[0]["skill_name"] == "argument-clustering-copy"


def test_permission_or_scripted_source_implication_blocks(copied_seed_skills, tmp_path):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _temporary_candidate(copied_seed_skills, runs_dir)
    approve_candidate_promotion(runs_dir, candidate_id, "Ada", "Reviewed")
    text = source_path.read_text(encoding="utf-8")
    source_path.write_text(text.replace("network: false", "network: true"), encoding="utf-8")

    report = build_admission_plan(candidate_id, runs_dir=runs_dir, skills_dir=copied_seed_skills)

    assert "source_permission_widening" in report.blockers
    assert "network" in report.durable_registry.permission_widening


def test_admission_plan_command_outputs_human_and_json(copied_seed_skills, tmp_path):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, _ = _temporary_candidate(copied_seed_skills, runs_dir)
    approve_candidate_promotion(runs_dir, candidate_id, "Ada", "Reviewed")

    text_result = runner.invoke(
        app,
        [
            "admission-plan",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
        ],
    )
    json_result = runner.invoke(
        app,
        [
            "admission-plan",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--json",
        ],
    )

    assert text_result.exit_code == 0
    assert "ADMISSION_PLAN" in text_result.stdout
    assert "SOURCE" in text_result.stdout
    assert "EVIDENCE" in text_result.stdout
    assert "DURABLE_REGISTRY" in text_result.stdout
    assert "PROMOTION_REQUIREMENTS" in text_result.stdout
    assert "BLOCKERS" in text_result.stdout
    assert "WARNINGS" in text_result.stdout
    assert "NEXT_STEPS" in text_result.stdout
    assert "Dry run: true" in text_result.stdout
    assert "Durable skill installed: false" in text_result.stdout
    assert "Ledger mutated: false" in text_result.stdout
    assert "Registry mutated: false" in text_result.stdout
    assert "Auto-promotion: disabled" in text_result.stdout
    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["dry_run"] is True
    assert data["auto_promotion_enabled"] is False
    assert data["durable_skill_installed"] is False
    assert data["ledger_mutated"] is False
    assert data["registry_mutated"] is False
    assert data["governor_steering_enabled"] is False


def test_admission_plan_human_output_warns_when_selected_source_is_stale(
    copied_seed_skills,
    tmp_path,
    capsys,
):
    runs_dir = tmp_path / "runs"
    candidate_id, _ = _temporary_candidate(copied_seed_skills, runs_dir)
    approve_candidate_promotion(runs_dir, candidate_id, "Ada", "Reviewed")
    report = build_admission_plan(candidate_id, runs_dir=runs_dir, skills_dir=copied_seed_skills)

    emit_admission_plan_output(
        report.model_copy(update={"selected_source_artifact": "missing/SKILL.md"})
    )

    output = capsys.readouterr().out
    assert "Selected temporary SKILL.md: -" in output
    assert "Source warning: selected source artifact missing from report: missing/SKILL.md" in output


def test_admission_plan_command_rejects_missing_candidate(tmp_path):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    write_candidate_ledger(SkillCandidateLedger(), runs_dir)

    result = runner.invoke(
        app,
        ["admission-plan", "candidate_missing", "--runs-dir", str(runs_dir)],
    )

    assert result.exit_code == 1
    assert "candidate not found" in result.stdout


def test_admission_plan_command_names_collision(copied_seed_skills, tmp_path):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _temporary_candidate(copied_seed_skills, runs_dir)
    approve_candidate_promotion(runs_dir, candidate_id, "Ada", "Reviewed")
    copytree(source_path.parent, copied_seed_skills / "argument-clustering")

    result = runner.invoke(
        app,
        [
            "admission-plan",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
        ],
    )

    assert result.exit_code == 0
    assert "durable_name_collision" in result.stdout
    assert "argument-clustering" in result.stdout


def _temporary_candidate(copied_seed_skills, runs_dir):
    result = run_task(
        "Cluster arguments from these sources.",
        copied_seed_skills,
        runs_dir,
        create_temporary_skills=True,
    )
    assert result.exit_code == 0
    entry = load_candidate_ledger(runs_dir).entries[0]
    source_path = Path(result.run_log.skill_requests[0]["temporary_skill"]["skill_path"])
    return entry.candidate_id, source_path


def _approved_entry(candidate_id: str = "candidate_manual") -> SkillCandidateLedgerEntry:
    return SkillCandidateLedgerEntry(
        candidate_id=candidate_id,
        skill_name="argument-clustering",
        capability="argument clustering",
        status="candidate",
        request_count=1,
        successful_temporary_uses=1,
        validation_pass_count=1,
        human_approval_required=False,
        promotion_approved_by="Ada",
        promotion_approved_at=datetime(2026, 6, 2, 12, 0, 0),
        promotion_requirements=["Human approval is recorded before durable promotion"],
        evidence_run_ids=["run_manual"],
    )
