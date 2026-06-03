from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.admission_plan import build_admission_plan
from app.agent_loop import run_task
from app.cli import app
from app.durable_admission import build_durable_admission_preview
from app.input_resolution import resolve_input_request
from app.skill_candidate_ledger import approve_candidate_promotion, load_candidate_ledger


def test_durable_admission_preview_requires_approve_review_resolution(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _promoted_candidate(copied_seed_skills, runs_dir)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )

    assert preview.outcome == "approval_required"
    assert preview.ready_for_mutation_preview is False
    assert preview.source_skill_path == str(source_path)
    assert preview.source_sha256 is not None
    assert preview.target_skill_dir == str(copied_seed_skills / "argument-clustering")
    assert preview.target_skill_path == str(copied_seed_skills / "argument-clustering" / "SKILL.md")
    assert preview.blockers == ["durable_review_resolution_missing"]
    assert preview.required_human_records == [
        "promotion_approved_by",
        "promotion_approved_at",
        "durable_admission_review approve_review resolution",
    ]
    assert preview.dry_run is True
    assert preview.mutation_supported is False
    assert preview.durable_skill_installed is False
    assert preview.ledger_mutated is False
    assert preview.registry_mutated is False
    assert preview.resolution_ledger_mutated is False
    assert preview.governor_steering_enabled is False
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_durable_admission_preview_ready_after_append_only_review_resolution(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, _ = _promoted_candidate(copied_seed_skills, runs_dir)
    admission = build_admission_plan(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )
    assert admission.input_request is not None
    resolve_input_request(
        admission.input_request.id,
        runs_dir=runs_dir,
        decision="approve_review",
        reviewer="Ada",
        notes="Reviewed durable admission evidence for preview.",
        dry_run=False,
    )
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )

    assert preview.outcome == "ready_for_mutation_preview"
    assert preview.ready_for_mutation_preview is True
    assert preview.blockers == []
    assert preview.next_steps == [
        "Review the target path and source fingerprint.",
        "Future install/copy remains disabled until a separate write-mode slice exists.",
    ]
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_admit_candidate_cli_outputs_preview_and_rejects_write_mode(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, _ = _promoted_candidate(copied_seed_skills, runs_dir)

    text_result = runner.invoke(
        app,
        [
            "admit-candidate",
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
            "admit-candidate",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--json",
        ],
    )
    write_result = runner.invoke(
        app,
        [
            "admit-candidate",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--no-dry-run",
        ],
    )

    assert text_result.exit_code == 0
    assert "DURABLE_ADMISSION_PREVIEW" in text_result.stdout
    assert "Mutation supported: false" in text_result.stdout
    assert "Resolution ledger mutated: false" in text_result.stdout
    assert "durable_review_resolution_missing" in text_result.stdout
    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["outcome"] == "approval_required"
    assert data["ready_for_mutation_preview"] is False
    assert data["admission_plan"]["input_request"]["kind"] == "durable_admission_review"
    assert write_result.exit_code == 1
    assert "durable admission mutation is not implemented" in write_result.stdout


def _promoted_candidate(copied_seed_skills: Path, runs_dir: Path) -> tuple[str, Path]:
    result = run_task(
        "Cluster arguments from these sources.",
        copied_seed_skills,
        runs_dir,
        create_temporary_skills=True,
    )
    assert result.exit_code == 0
    entry = load_candidate_ledger(runs_dir).entries[0]
    approve_candidate_promotion(
        runs_dir,
        entry.candidate_id,
        reviewer="Ada",
        notes="Reviewed temporary evidence.",
    )
    source_path = Path(result.run_log.skill_requests[0]["temporary_skill"]["skill_path"])
    return entry.candidate_id, source_path


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
