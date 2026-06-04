from __future__ import annotations

import hashlib
import json
from pathlib import Path
from shutil import copytree

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.input_resolution_ledger import (
    append_input_request_resolution,
    load_input_request_resolution_ledger,
)
from app.models import InputRequest, InputRequestResolutionDryRun
from app.skill_candidate_ledger import load_candidate_ledger, write_candidate_ledger


def test_acceptance_write_plan_verifies_destination_snapshot_hash_and_no_writes(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path, _ = _prepare_reviewed_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = _admit_candidate_json(runner, candidate_id, runs_dir, copied_seed_skills)

    assert result["outcome"] == "ready_for_mutation_preview"
    assert result["ready_for_mutation_preview"] is True
    assert result["source_sha256"] == _sha256(source_path)
    assert result["target_skill_path"] == str(
        copied_seed_skills / "argument-clustering" / "SKILL.md"
    )
    assert result["write_plan"]["operation"] == "copy_new_skill"
    assert result["write_plan"]["plan_digest_algorithm"] == "sha256"
    assert result["write_plan"]["plan_digest"]
    assert result["write_plan"]["plan_approval_verified"] is True
    assert result["write_plan"]["plan_approval_digest"] == result["write_plan"]["plan_digest"]
    assert result["write_plan"]["plan_approval_expires_at"] == "2099-01-01T00:00:00Z"
    assert result["write_plan"]["permission_dependency_diff"]["added_permission_classes"] == []
    assert result["write_plan"]["permission_dependency_diff"]["dependency_diff"][
        "dependencies_declared"
    ] is False
    assert result["write_plan"]["source_skill_path"] == str(source_path)
    assert result["write_plan"]["source_sha256"] == result["source_sha256"]
    assert result["write_plan"]["target_skill_path"] == result["target_skill_path"]
    assert result["write_plan"]["snapshot_skill_path"] == str(
        runs_dir / "admission_snapshots" / candidate_id / result["source_sha256"] / "SKILL.md"
    )
    assert result["write_plan"]["snapshot_sha256"] == result["source_sha256"]
    assert result["write_plan"]["prepare_write_evidence"] is False
    assert result["write_plan"]["expected_source_sha256"] is None
    assert result["write_plan"]["source_hash_verified"] is True
    assert result["write_plan"]["source_snapshot_retained"] is False
    assert result["write_plan"]["destination_stage_skill_path"] == str(
        runs_dir
        / "admission_staging"
        / candidate_id
        / result["source_sha256"]
        / "skills"
        / "argument-clustering"
        / "SKILL.md"
    )
    assert result["write_plan"]["destination_stage_sha256"] is None
    assert result["write_plan"]["destination_stage_created"] is False
    assert result["write_plan"]["blockers"] == []
    _assert_no_admission_mutation(result)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert not (runs_dir / "admission_snapshots").exists()

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

    assert write_result.exit_code == 1
    assert "durable admission mutation is not implemented" in write_result.stdout
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_acceptance_prepare_write_evidence_retains_snapshot_and_stages_destination(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path, _ = _prepare_reviewed_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    source_sha256 = _sha256(source_path)
    _approve_preview_plan(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-write-evidence",
        "--expected-source-sha256",
        source_sha256,
    )
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    first = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-write-evidence",
        "--expected-source-sha256",
        source_sha256,
    )

    snapshot_path = (
        runs_dir / "admission_snapshots" / candidate_id / source_sha256 / "SKILL.md"
    )
    stage_path = (
        runs_dir
        / "admission_staging"
        / candidate_id
        / source_sha256
        / "skills"
        / "argument-clustering"
        / "SKILL.md"
    )
    assert first["outcome"] == "ready_for_mutation_preview"
    assert first["write_plan"]["prepare_write_evidence"] is True
    assert first["write_plan"]["expected_source_sha256"] == source_sha256
    assert first["write_plan"]["source_hash_verified"] is True
    assert first["write_plan"]["source_snapshot_created"] is True
    assert first["write_plan"]["source_snapshot_retained"] is True
    assert first["write_plan"]["destination_stage_created"] is True
    assert first["write_plan"]["destination_stage_skill_path"] == str(stage_path)
    assert first["write_plan"]["destination_stage_sha256"] == source_sha256
    assert snapshot_path.read_bytes() == source_path.read_bytes()
    assert stage_path.read_bytes() == source_path.read_bytes()
    assert _sha256(snapshot_path) == source_sha256
    assert _sha256(stage_path) == source_sha256
    _assert_no_durable_admission_mutation(first)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _without_admission_evidence(_snapshot_tree(runs_dir)) == runs_before

    runs_after_first = _snapshot_tree(runs_dir)
    second = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-write-evidence",
        "--expected-source-sha256",
        source_sha256,
    )

    assert second["write_plan"]["source_snapshot_created"] is False
    assert second["write_plan"]["source_snapshot_retained"] is True
    assert second["write_plan"]["destination_stage_created"] is False
    assert second["write_plan"]["destination_stage_sha256"] == source_sha256
    _assert_no_durable_admission_mutation(second)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_after_first


def test_acceptance_prepare_write_evidence_blocks_source_hash_mismatch_without_writing(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, _, _ = _prepare_reviewed_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-write-evidence",
        "--expected-source-sha256",
        "0" * 64,
    )

    assert result["write_plan"]["operation"] == "blocked"
    assert result["write_plan"]["source_hash_verified"] is False
    assert "source_hash_mismatch" in result["write_plan"]["blockers"]
    assert result["write_plan"]["source_snapshot_created"] is False
    assert result["write_plan"]["source_snapshot_retained"] is False
    assert result["write_plan"]["destination_stage_created"] is False
    assert result["write_plan"]["destination_stage_sha256"] is None
    _assert_no_durable_admission_mutation(result)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert not (runs_dir / "admission_snapshots").exists()
    assert not (runs_dir / "admission_staging").exists()


def test_acceptance_prepare_write_evidence_blocks_snapshot_mismatch_without_rewriting(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path, _ = _prepare_reviewed_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    source_sha256 = _sha256(source_path)
    snapshot_path = (
        runs_dir / "admission_snapshots" / candidate_id / source_sha256 / "SKILL.md"
    )
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_text("historical mismatch\n", encoding="utf-8")
    _approve_preview_plan(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-write-evidence",
        "--expected-source-sha256",
        source_sha256,
    )
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-write-evidence",
        "--expected-source-sha256",
        source_sha256,
    )

    assert result["write_plan"]["operation"] == "blocked"
    assert "retained_snapshot_hash_mismatch" in result["write_plan"]["blockers"]
    assert result["write_plan"]["source_snapshot_created"] is False
    assert result["write_plan"]["source_snapshot_retained"] is False
    assert result["write_plan"]["destination_stage_created"] is False
    _assert_no_durable_admission_mutation(result)
    assert snapshot_path.read_text(encoding="utf-8") == "historical mismatch\n"
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert not (runs_dir / "admission_staging").exists()


def test_acceptance_prepare_write_evidence_blocks_stage_mismatch_without_rewriting(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path, _ = _prepare_reviewed_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    source_sha256 = _sha256(source_path)
    snapshot_path = (
        runs_dir / "admission_snapshots" / candidate_id / source_sha256 / "SKILL.md"
    )
    stage_path = (
        runs_dir
        / "admission_staging"
        / candidate_id
        / source_sha256
        / "skills"
        / "argument-clustering"
        / "SKILL.md"
    )
    snapshot_path.parent.mkdir(parents=True)
    snapshot_path.write_bytes(source_path.read_bytes())
    stage_path.parent.mkdir(parents=True)
    stage_path.write_text("historical staged mismatch\n", encoding="utf-8")
    _approve_preview_plan(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-write-evidence",
        "--expected-source-sha256",
        source_sha256,
    )
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-write-evidence",
        "--expected-source-sha256",
        source_sha256,
    )

    assert result["write_plan"]["operation"] == "blocked"
    assert "destination_stage_hash_mismatch" in result["write_plan"]["blockers"]
    assert result["write_plan"]["source_snapshot_created"] is False
    assert result["write_plan"]["source_snapshot_retained"] is True
    assert result["write_plan"]["destination_stage_created"] is False
    assert result["write_plan"]["destination_stage_sha256"] is None
    _assert_no_durable_admission_mutation(result)
    assert stage_path.read_text(encoding="utf-8") == "historical staged mismatch\n"
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_acceptance_prepare_dependency_evidence_creates_and_reuses_run_scoped_manifest(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _prepare_promoted_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    _append_dependency_declaration(source_path)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    first = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-dependency-evidence",
    )

    contract = first["write_plan"]["dependency_install_contract"]
    manifest_path = Path(contract["evidence_manifest_path"])
    assert first["write_plan"]["operation"] == "blocked"
    assert contract["prepare_dependency_evidence"] is True
    assert contract["evidence_manifest_created"] is True
    assert contract["evidence_manifest_retained"] is True
    assert manifest_path == (
        runs_dir
        / "admission_dependency_evidence"
        / candidate_id
        / first["source_sha256"]
        / "dependency_plan.json"
    )
    manifest_bytes = manifest_path.read_bytes()
    assert hashlib.sha256(manifest_bytes).hexdigest() == contract["evidence_manifest_sha256"]
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    assert manifest["dependency_plan_digest"] == contract["dependency_plan_digest"]
    assert manifest["dependency_blockers"] == ["dependency_realization_missing"]
    assert manifest["install_supported"] is False
    assert manifest["install_attempted"] is False
    assert manifest["dependencies_installed"] is False
    assert contract["normalized_dependencies"][0]["status"] == "unresolved"
    assert contract["install_supported"] is False
    assert contract["install_attempted"] is False
    assert contract["dependencies_installed"] is False
    _assert_no_durable_admission_mutation(first)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _without_dependency_evidence(_snapshot_tree(runs_dir)) == runs_before
    assert not (runs_dir / "admission_snapshots").exists()
    assert not (runs_dir / "admission_staging").exists()

    runs_after_first = _snapshot_tree(runs_dir)
    second = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-dependency-evidence",
    )

    second_contract = second["write_plan"]["dependency_install_contract"]
    assert second_contract["evidence_manifest_created"] is False
    assert second_contract["evidence_manifest_retained"] is True
    assert second_contract["evidence_manifest_sha256"] == contract["evidence_manifest_sha256"]
    _assert_no_durable_admission_mutation(second)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_after_first


def test_acceptance_expected_dependency_digest_mismatch_blocks_manifest_write(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _prepare_promoted_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    _append_dependency_declaration(source_path)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-dependency-evidence",
        "--expected-dependency-plan-digest",
        "0" * 64,
    )

    contract = result["write_plan"]["dependency_install_contract"]
    assert contract["dependency_plan_digest_verified"] is False
    assert "dependency_plan_digest_mismatch" in contract["blockers"]
    assert "dependency_plan_digest_mismatch" in result["write_plan"]["blockers"]
    assert contract["evidence_manifest_created"] is False
    assert contract["evidence_manifest_retained"] is False
    assert not Path(contract["evidence_manifest_path"]).exists()
    _assert_no_durable_admission_mutation(result)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_acceptance_dependency_manifest_mismatch_blocks_without_overwrite(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _prepare_promoted_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    _append_dependency_declaration(source_path)
    initial = _admit_candidate_json(runner, candidate_id, runs_dir, copied_seed_skills)
    manifest_path = Path(
        initial["write_plan"]["dependency_install_contract"]["evidence_manifest_path"]
    )
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text("historical dependency mismatch\n", encoding="utf-8")
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-dependency-evidence",
    )

    contract = result["write_plan"]["dependency_install_contract"]
    assert "dependency_evidence_manifest_hash_mismatch" in contract["blockers"]
    assert "dependency_evidence_manifest_hash_mismatch" in result["write_plan"]["blockers"]
    assert contract["evidence_manifest_created"] is False
    assert contract["evidence_manifest_retained"] is False
    assert manifest_path.read_text(encoding="utf-8") == "historical dependency mismatch\n"
    _assert_no_durable_admission_mutation(result)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_acceptance_dependency_manifest_blocks_candidate_id_path_traversal(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    original_candidate_id, source_path = _prepare_promoted_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    _append_dependency_declaration(source_path)
    escaped_candidate_id = "../../escaped-candidate"
    ledger = load_candidate_ledger(runs_dir)
    assert ledger.entries[0].candidate_id == original_candidate_id
    ledger.entries[0].candidate_id = escaped_candidate_id
    write_candidate_ledger(ledger, runs_dir)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = _admit_candidate_json(
        runner,
        escaped_candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-dependency-evidence",
    )

    contract = result["write_plan"]["dependency_install_contract"]
    assert "dependency_evidence_manifest_path_escape" in contract["blockers"]
    assert "dependency_evidence_manifest_path_escape" in result["write_plan"]["blockers"]
    assert contract["evidence_manifest_path"] is None
    assert contract["evidence_manifest_created"] is False
    assert contract["evidence_manifest_retained"] is False
    assert not (tmp_path / "escaped-candidate").exists()
    _assert_no_durable_admission_mutation(result)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_acceptance_dependency_manifest_blocks_symlinked_evidence_parent_escape(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _prepare_promoted_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    _append_dependency_declaration(source_path)
    outside_dir = tmp_path / "outside-evidence"
    outside_dir.mkdir()
    evidence_parent = runs_dir / "admission_dependency_evidence"
    try:
        evidence_parent.symlink_to(outside_dir, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlink creation unavailable: {exc}")
    durable_before = _snapshot_tree(copied_seed_skills)

    result = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-dependency-evidence",
    )

    contract = result["write_plan"]["dependency_install_contract"]
    assert "dependency_evidence_manifest_path_escape" in contract["blockers"]
    assert contract["evidence_manifest_created"] is False
    assert contract["evidence_manifest_retained"] is False
    assert list(outside_dir.rglob("*")) == []
    _assert_no_durable_admission_mutation(result)
    assert _snapshot_tree(copied_seed_skills) == durable_before


def test_acceptance_prepare_dependency_evidence_blocks_unsafe_source_admission_blockers(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _prepare_promoted_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    _append_dependency_declaration(source_path)
    (source_path.parent / "scripts").mkdir()
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-dependency-evidence",
    )

    contract = result["write_plan"]["dependency_install_contract"]
    assert "dependency_realization_missing" in contract["blockers"]
    assert "source_scripted_unsupported" in contract["blockers"]
    assert contract["evidence_manifest_path"] is not None
    assert contract["evidence_manifest_created"] is False
    assert contract["evidence_manifest_retained"] is False
    assert not Path(contract["evidence_manifest_path"]).exists()
    _assert_no_durable_admission_mutation(result)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_acceptance_prepare_dependency_evidence_blocks_source_outside_runs(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _prepare_promoted_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    _append_dependency_declaration(source_path)
    outside_source = tmp_path / "outside-source" / "SKILL.md"
    outside_source.parent.mkdir()
    outside_source.write_bytes(source_path.read_bytes())
    _rewrite_single_run_log_source_path(runs_dir, outside_source)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--prepare-dependency-evidence",
    )

    contract = result["write_plan"]["dependency_install_contract"]
    assert result["source_sha256"] is None
    assert result["write_plan"]["source_sha256"] is None
    assert result["write_plan"]["snapshot_skill_path"] is None
    assert "source_path_outside_runs" in contract["blockers"]
    assert contract["evidence_manifest_created"] is False
    assert contract["evidence_manifest_retained"] is False
    assert contract["evidence_manifest_path"] is None
    _assert_no_durable_admission_mutation(result)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_acceptance_source_drift_changes_hash_and_snapshot_path_without_writing(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path, _ = _prepare_reviewed_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )

    first = _admit_candidate_json(runner, candidate_id, runs_dir, copied_seed_skills)
    source_path.write_text(
        source_path.read_text(encoding="utf-8") + "\nAdditional drift evidence.\n",
        encoding="utf-8",
    )
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    second = _admit_candidate_json(runner, candidate_id, runs_dir, copied_seed_skills)

    assert second["source_sha256"] == _sha256(source_path)
    assert second["source_sha256"] != first["source_sha256"]
    assert second["write_plan"]["snapshot_skill_path"] == str(
        runs_dir / "admission_snapshots" / candidate_id / second["source_sha256"] / "SKILL.md"
    )
    assert (
        second["write_plan"]["snapshot_skill_path"]
        != first["write_plan"]["snapshot_skill_path"]
    )
    assert second["write_plan"]["operation"] == "blocked"
    assert second["write_plan"]["plan_approval_verified"] is False
    assert "plan_digest_approval_mismatch" in second["write_plan"]["blockers"]
    _assert_no_admission_mutation(second)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert not (runs_dir / "admission_snapshots").exists()


def test_acceptance_collision_approval_gates_replacement_preview_without_writing(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    no_review_skills = tmp_path / "skills-no-review"
    reviewed_skills = tmp_path / "skills-reviewed"
    copytree(copied_seed_skills, no_review_skills)
    copytree(copied_seed_skills, reviewed_skills)
    runs_dir = tmp_path / "runs-no-review"
    candidate_id, source_path = _prepare_promoted_candidate(
        runner,
        no_review_skills,
        runs_dir,
    )
    copytree(source_path.parent, no_review_skills / "argument-clustering")
    durable_before_review = _snapshot_tree(no_review_skills)
    runs_before_review = _snapshot_tree(runs_dir)

    no_review = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        no_review_skills,
        "--collision-policy",
        "allow_replace_with_approval",
    )

    assert no_review["write_plan"]["operation"] == "blocked"
    assert no_review["write_plan"]["replacement_approved"] is False
    assert "durable_review_resolution_missing" in no_review["write_plan"]["blockers"]
    assert _snapshot_tree(no_review_skills) == durable_before_review
    assert _snapshot_tree(runs_dir) == runs_before_review

    reviewed_runs_dir = tmp_path / "runs-reviewed"
    reviewed_candidate_id, reviewed_source_path, _ = _prepare_reviewed_candidate(
        runner,
        reviewed_skills,
        reviewed_runs_dir,
    )
    copytree(reviewed_source_path.parent, reviewed_skills / "argument-clustering")
    _approve_preview_plan(
        runner,
        reviewed_candidate_id,
        reviewed_runs_dir,
        reviewed_skills,
        "--collision-policy",
        "allow_replace_with_approval",
    )
    durable_before_preview = _snapshot_tree(reviewed_skills)
    runs_before_preview = _snapshot_tree(reviewed_runs_dir)
    default_policy = _admit_candidate_json(
        runner,
        reviewed_candidate_id,
        reviewed_runs_dir,
        reviewed_skills,
    )
    replacement = _admit_candidate_json(
        runner,
        reviewed_candidate_id,
        reviewed_runs_dir,
        reviewed_skills,
        "--collision-policy",
        "allow_replace_with_approval",
    )

    assert default_policy["write_plan"]["operation"] == "blocked"
    assert "durable_name_collision" in default_policy["write_plan"]["blockers"]
    assert replacement["ready_for_mutation_preview"] is True
    assert replacement["write_plan"]["operation"] == "replace_existing_skill"
    assert replacement["write_plan"]["replacement_approved"] is True
    assert replacement["write_plan"]["blockers"] == []
    _assert_no_admission_mutation(replacement)
    assert _snapshot_tree(reviewed_skills) == durable_before_preview
    assert _snapshot_tree(reviewed_runs_dir) == runs_before_preview
    assert not (reviewed_runs_dir / "admission_snapshots").exists()


def test_acceptance_permission_approval_clears_only_permission_gate_without_writing(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path, permission_approval_id = _prepare_reviewed_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    updated_source = source_path.read_text(encoding="utf-8").replace(
        "network: false",
        "network: true",
        1,
    )
    source_path.write_text(
        updated_source,
        encoding="utf-8",
    )
    plan_approval_id = _approve_preview_plan(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--permission-approval-id",
        permission_approval_id,
    )
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    without_permission = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
    )
    with_permission = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--permission-approval-id",
        permission_approval_id,
        "--plan-approval-id",
        plan_approval_id,
    )

    assert without_permission["write_plan"]["operation"] == "blocked"
    assert (
        "permission_widening_approval_missing"
        in without_permission["write_plan"]["blockers"]
    )
    assert without_permission["write_plan"]["permission_widening_approved"] is False
    assert with_permission["write_plan"]["operation"] == "blocked"
    assert with_permission["write_plan"]["permission_widening_approved"] is True
    assert (
        "network"
        in with_permission["write_plan"]["permission_dependency_diff"][
            "added_permission_classes"
        ]
    )
    assert (
        "permission_widening_approval_missing"
        not in with_permission["write_plan"]["blockers"]
    )
    assert "source_permission_widening" in with_permission["write_plan"]["blockers"]
    _assert_no_admission_mutation(with_permission)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert not (runs_dir / "admission_snapshots").exists()


def _prepare_reviewed_candidate(
    runner: CliRunner,
    skills_dir: Path,
    runs_dir: Path,
) -> tuple[str, Path, str]:
    candidate_id, source_path = _prepare_promoted_candidate(runner, skills_dir, runs_dir)
    initial_preview = _admit_candidate_json(runner, candidate_id, runs_dir, skills_dir)
    resolution_id = _approve_admission_review(
        runner,
        candidate_id,
        runs_dir,
        skills_dir,
        plan_digest=initial_preview["write_plan"]["plan_digest"],
    )
    return candidate_id, source_path, resolution_id


def _prepare_promoted_candidate(
    runner: CliRunner,
    skills_dir: Path,
    runs_dir: Path,
) -> tuple[str, Path]:
    run_result = runner.invoke(
        app,
        [
            "run",
            "Cluster arguments from these sources.",
            "--temporary-skills",
            "--skills-dir",
            str(skills_dir),
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert run_result.exit_code == 0
    run_log = _single_run_log(runs_dir)
    source_path = Path(
        json.loads(run_log.read_text(encoding="utf-8"))["skill_requests"][0]["temporary_skill"][
            "skill_path"
        ]
    )
    candidates_result = runner.invoke(
        app,
        ["candidates", "--runs-dir", str(runs_dir), "--json"],
    )
    assert candidates_result.exit_code == 0
    candidate_id = json.loads(candidates_result.stdout)["entries"][0]["candidate_id"]
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
    return candidate_id, source_path


def _approve_admission_review(
    runner: CliRunner,
    candidate_id: str,
    runs_dir: Path,
    skills_dir: Path,
    *,
    plan_digest: str | None = None,
    expires_at: str = "2099-01-01T00:00:00Z",
) -> str:
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
    admission = json.loads(admission_result.stdout)
    input_request = admission.get("input_request")
    if input_request is None or input_request["kind"] != "durable_admission_review":
        return _append_plan_approval_record(candidate_id, runs_dir, plan_digest, expires_at)
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
            _approval_notes(plan_digest, expires_at),
            "--no-dry-run",
            "--json",
        ],
    )
    if resolve_result.exit_code != 0:
        return _append_plan_approval_record(candidate_id, runs_dir, plan_digest, expires_at)
    ledger = load_input_request_resolution_ledger(runs_dir)
    return ledger.resolutions[-1].id


def _approve_preview_plan(
    runner: CliRunner,
    candidate_id: str,
    runs_dir: Path,
    skills_dir: Path,
    *extra_args: str,
) -> str:
    preview = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        skills_dir,
        *extra_args,
    )
    assert preview["write_plan"]["plan_digest"]
    return _approve_admission_review(
        runner,
        candidate_id,
        runs_dir,
        skills_dir,
        plan_digest=preview["write_plan"]["plan_digest"],
    )


def _approval_notes(plan_digest: str | None, expires_at: str) -> str:
    notes = "Reviewed durable admission evidence."
    if plan_digest:
        notes = f"{notes} plan_digest={plan_digest} expires_at={expires_at}"
    return notes


def _append_dependency_declaration(source_path: Path) -> None:
    text = source_path.read_text(encoding="utf-8")
    marker = "\n---\n\n#"
    assert marker in text
    updated = text.replace(
        marker,
        "\ndependencies:\n  - example-package==1.0.0\n---\n\n#",
        1,
    )
    source_path.write_text(updated, encoding="utf-8")


def _rewrite_single_run_log_source_path(runs_dir: Path, source_path: Path) -> None:
    run_log = _single_run_log(runs_dir)
    data = json.loads(run_log.read_text(encoding="utf-8"))
    data["skill_requests"][0]["temporary_skill"]["skill_path"] = str(source_path)
    run_log.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_plan_approval_record(
    candidate_id: str,
    runs_dir: Path,
    plan_digest: str | None,
    expires_at: str,
) -> str:
    request = InputRequest(
        id=f"inputreq_plan_digest_{candidate_id}",
        kind="durable_admission_review",
        title=f"Approve exact durable admission plan for {candidate_id}",
        reason="Acceptance fixture approval for an exact plan digest.",
        blocked_scope="durable skill install/copy",
        requested_decision="Approve the exact plan digest or defer.",
        options=["approve_review", "defer"],
        recommended_option="approve_review",
        related_candidate_id=candidate_id,
    )
    report = InputRequestResolutionDryRun(
        dry_run=True,
        input_request_id=request.id,
        decision="approve_review",
        resolution_class="approve",
        proposed_status="resolved",
        reviewer="Ada",
        notes=_approval_notes(plan_digest, expires_at),
        request=request,
        remaining_blocked_scope="durable skill install/copy",
        next_steps=["Rerun admit-candidate --dry-run."],
    )
    record = append_input_request_resolution(report, runs_dir)
    return record.id


def _admit_candidate_json(
    runner: CliRunner,
    candidate_id: str,
    runs_dir: Path,
    skills_dir: Path,
    *extra_args: str,
) -> dict:
    result = runner.invoke(
        app,
        [
            "admit-candidate",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(skills_dir),
            *extra_args,
            "--json",
        ],
    )
    assert result.exit_code == 0
    return json.loads(result.stdout)


def _assert_no_admission_mutation(report: dict) -> None:
    _assert_no_durable_admission_mutation(report)
    for key in [
        "source_snapshot_created",
    ]:
        assert report["write_plan"][key] is False


def _assert_no_durable_admission_mutation(report: dict) -> None:
    for key in [
        "mutation_supported",
        "durable_skill_installed",
        "ledger_mutated",
        "registry_mutated",
        "resolution_ledger_mutated",
        "governor_steering_enabled",
    ]:
        assert report[key] is False
    for key in [
        "durable_skill_installed",
        "ledger_mutated",
        "registry_mutated",
        "resolution_ledger_mutated",
        "governor_steering_enabled",
    ]:
        assert report["write_plan"][key] is False
    contract = report["write_plan"]["dependency_install_contract"]
    assert contract["install_supported"] is False
    assert contract["install_attempted"] is False
    assert contract["dependencies_installed"] is False


def _single_run_log(runs_dir: Path) -> Path:
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    return logs[0]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def _without_admission_evidence(tree: dict[str, bytes]) -> dict[str, bytes]:
    return {
        key: value
        for key, value in tree.items()
        if not key.startswith("admission_snapshots/")
        and not key.startswith("admission_staging/")
    }


def _without_dependency_evidence(tree: dict[str, bytes]) -> dict[str, bytes]:
    return {
        key: value
        for key, value in tree.items()
        if not key.startswith("admission_dependency_evidence/")
    }


def test_atomic_write_bytes_cleans_temp_file_on_write_failure(tmp_path):
    from app import durable_admission

    target = tmp_path / "evidence" / "dependency_plan.json"

    class FailingHandle:
        name = str(tmp_path / "evidence" / ".tmp-dependency")

        def __enter__(self):
            Path(self.name).parent.mkdir(parents=True, exist_ok=True)
            Path(self.name).write_bytes(b"partial")
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def write(self, content: bytes) -> None:
            raise OSError("simulated write failure")

    original = durable_admission.NamedTemporaryFile
    durable_admission.NamedTemporaryFile = lambda **kwargs: FailingHandle()
    try:
        with pytest.raises(OSError):
            durable_admission._atomic_write_bytes(target, b"payload")
    finally:
        durable_admission.NamedTemporaryFile = original

    assert not Path(FailingHandle.name).exists()
    assert not target.exists()
