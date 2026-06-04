from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app
from app.input_resolution_ledger import load_input_request_resolution_ledger
from app.shadow_activation import (
    build_shadow_activation_acceptance_report,
    build_shadow_activation_plan,
    build_shadow_managed_write_report,
    build_shadow_rollback_plan,
    build_shadow_write_gate_report,
)
from app.skill_candidate_ledger import load_candidate_ledger


def test_shadow_activation_plan_reports_managed_generation_without_writes(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    candidate_id = _prepare_reviewed_candidate(runner, copied_seed_skills, runs_dir)
    existing_generation = managed_prefix / "profiles" / "default" / "generations" / "3"
    existing_generation.mkdir(parents=True)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)
    managed_before = _snapshot_tree(managed_prefix)

    report = build_shadow_activation_plan(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
    )
    json_result = runner.invoke(
        app,
        [
            "shadow-activation-plan",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--json",
        ],
    )
    text_result = runner.invoke(
        app,
        [
            "shadow-activation-plan",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
        ],
    )

    assert report.outcome == "ready_for_shadow_activation_preview"
    assert report.ready_for_shadow_activation_preview is True
    assert report.previous_generation == 3
    assert report.planned_generation == 4
    assert report.rollback_target == str(existing_generation)
    assert report.store_skill_path is not None
    assert "/store/sha256-" in report.store_skill_path
    assert report.generation_skill_path == str(
        managed_prefix
        / "profiles"
        / "default"
        / "generations"
        / "4"
        / "skills"
        / "argument-clustering"
        / "SKILL.md"
    )
    assert report.shadow_plan_digest
    _assert_no_mutation_flags(report.model_dump(mode="json"))

    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["ready_for_shadow_activation_preview"] is True
    assert data["previous_generation"] == 3
    assert data["planned_generation"] == 4
    assert data["rollback_target"] == str(existing_generation)
    _assert_no_mutation_flags(data)

    assert text_result.exit_code == 0
    assert "SHADOW_ACTIVATION_PLAN" in text_result.stdout
    assert "Ready for shadow activation preview: true" in text_result.stdout
    assert "Previous generation: 3" in text_result.stdout
    assert "Planned generation: 4" in text_result.stdout
    assert "Managed prefix mutated: false" in text_result.stdout

    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert _snapshot_tree(managed_prefix) == managed_before
    assert not (managed_prefix / "store").exists()


def test_shadow_activation_plan_stays_blocked_without_required_review(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
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
            "shadow-activation-plan",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["outcome"] == "blocked"
    assert data["ready_for_shadow_activation_preview"] is False
    assert "promotion_approval_missing" in data["blockers"]
    assert "durable_review_resolution_missing" in data["blockers"]
    assert "plan_digest_approval_missing" in data["blockers"]
    _assert_no_mutation_flags(data)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert not managed_prefix.exists()


def test_shadow_activation_plan_rejects_profile_name_path_escape(
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

    result = runner.invoke(
        app,
        [
            "shadow-activation-plan",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--profile-name",
            "../escape",
            "--json",
        ],
    )

    assert result.exit_code == 1
    assert "profile name must start" in result.stdout


def test_shadow_rollback_plan_verifies_existing_generation_without_writes(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    candidate_id = _prepare_reviewed_candidate(runner, copied_seed_skills, runs_dir)
    profile_dir = managed_prefix / "profiles" / "default"
    generation_2 = profile_dir / "generations" / "2"
    generation_3 = profile_dir / "generations" / "3"
    generation_2.mkdir(parents=True)
    generation_3.mkdir(parents=True)
    (generation_2 / ".marker").write_text("previous\n", encoding="utf-8")
    (generation_3 / ".marker").write_text("current\n", encoding="utf-8")
    current_pointer = profile_dir / "current"
    current_pointer.write_text(str(generation_3), encoding="utf-8")
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)
    managed_before = _snapshot_tree(managed_prefix)

    report = build_shadow_rollback_plan(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
    )
    json_result = runner.invoke(
        app,
        [
            "shadow-rollback-plan",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--json",
        ],
    )
    text_result = runner.invoke(
        app,
        [
            "shadow-rollback-plan",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
        ],
    )

    assert report.outcome == "rollback_verifiable"
    assert report.rollback_verifiable is True
    assert report.activation_pointer_exists is True
    assert report.activation_pointer_target == str(generation_3)
    assert report.current_generation == 3
    assert report.planned_generation == 4
    assert report.rollback_generation == 3
    assert report.rollback_target == str(generation_3)
    assert report.rollback_target_exists is True
    assert report.shadow_plan_digest
    assert report.rollback_plan_digest
    _assert_no_mutation_flags(report.model_dump(mode="json"))

    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["outcome"] == "rollback_verifiable"
    assert data["rollback_verifiable"] is True
    assert data["activation_pointer_target"] == str(generation_3)
    assert data["current_generation"] == 3
    assert data["planned_generation"] == 4
    assert data["rollback_generation"] == 3
    assert data["rollback_target"] == str(generation_3)
    assert data["rollback_target_exists"] is True
    _assert_no_mutation_flags(data)

    assert text_result.exit_code == 0
    assert "SHADOW_ROLLBACK_PLAN" in text_result.stdout
    assert "Rollback verifiable: true" in text_result.stdout
    assert "Current generation: 3" in text_result.stdout
    assert "Rollback target exists: true" in text_result.stdout
    assert "Managed prefix mutated: false" in text_result.stdout

    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert _snapshot_tree(managed_prefix) == managed_before
    assert not (managed_prefix / "store").exists()


def test_shadow_rollback_plan_blocks_without_previous_generation_or_writes(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    candidate_id = _prepare_reviewed_candidate(runner, copied_seed_skills, runs_dir)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = runner.invoke(
        app,
        [
            "shadow-rollback-plan",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["outcome"] == "blocked"
    assert data["rollback_verifiable"] is False
    assert "rollback_generation_missing" in data["blockers"]
    assert data["rollback_target_exists"] is False
    _assert_no_mutation_flags(data)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert not managed_prefix.exists()


def test_shadow_rollback_plan_blocks_when_activation_pointer_missing(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    candidate_id = _prepare_reviewed_candidate(runner, copied_seed_skills, runs_dir)
    generation_1 = managed_prefix / "profiles" / "default" / "generations" / "1"
    generation_1.mkdir(parents=True)
    (generation_1 / ".marker").write_text("current\n", encoding="utf-8")
    managed_before = _snapshot_tree(managed_prefix)

    result = runner.invoke(
        app,
        [
            "shadow-rollback-plan",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["outcome"] == "blocked"
    assert data["rollback_verifiable"] is False
    assert data["rollback_generation"] == 1
    assert data["rollback_target_exists"] is True
    assert "activation_pointer_missing" in data["blockers"]
    _assert_no_mutation_flags(data)
    assert _snapshot_tree(managed_prefix) == managed_before
    assert not (managed_prefix / "store").exists()


def test_shadow_activation_acceptance_prepares_sandbox_and_rolls_back_only_under_runs(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "case"
    candidate_id = _prepare_reviewed_candidate(runner, copied_seed_skills, runs_dir)
    existing_generation = managed_prefix / "profiles" / "default" / "generations" / "3"
    existing_generation.mkdir(parents=True)
    (existing_generation / ".marker").write_text("real prefix stays untouched\n", encoding="utf-8")
    durable_before = _snapshot_tree(copied_seed_skills)
    managed_before = _snapshot_tree(managed_prefix)
    runs_without_acceptance_before = _snapshot_tree_excluding(runs_dir, acceptance_prefix)

    report = build_shadow_activation_acceptance_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        prepare_acceptance_evidence=True,
    )
    json_result = runner.invoke(
        app,
        [
            "shadow-activation-acceptance",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--prepare-acceptance-evidence",
            "--json",
        ],
    )
    text_result = runner.invoke(
        app,
        [
            "shadow-activation-acceptance",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--prepare-acceptance-evidence",
        ],
    )

    assert report.outcome == "accepted"
    assert report.acceptance_prepared is True
    assert report.activation_verified is True
    assert report.rollback_verified is True
    assert report.mutation_supported is True
    assert report.acceptance_prefix_mutated is True
    assert report.managed_prefix_mutated is False
    assert report.durable_skills_mutated is False
    assert report.previous_generation == 3
    assert report.planned_generation == 4
    assert report.acceptance_plan_digest
    assert report.acceptance_store_skill_path
    assert report.acceptance_generation_skill_path
    assert Path(report.acceptance_store_skill_path).exists()
    assert Path(report.acceptance_generation_skill_path).exists()
    assert report.activation_pointer_after_activation is not None
    assert report.activation_pointer_after_activation.endswith("/generations/4")
    assert report.activation_pointer_after_rollback == report.acceptance_rollback_target

    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["outcome"] == "accepted"
    assert data["acceptance_prepared"] is True
    assert data["activation_verified"] is True
    assert data["rollback_verified"] is True
    assert data["mutation_supported"] is True
    assert data["acceptance_prefix_mutated"] is True
    assert data["managed_prefix_mutated"] is False
    assert data["durable_skills_mutated"] is False

    assert text_result.exit_code == 0
    assert "SHADOW_ACTIVATION_ACCEPTANCE" in text_result.stdout
    assert "Acceptance prepared: true" in text_result.stdout
    assert "Activation verified: true" in text_result.stdout
    assert "Rollback verified: true" in text_result.stdout
    assert "Managed prefix mutated: false" in text_result.stdout

    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(managed_prefix) == managed_before
    assert _snapshot_tree_excluding(runs_dir, acceptance_prefix) == runs_without_acceptance_before
    assert not (managed_prefix / "store").exists()


def test_shadow_activation_acceptance_planned_mode_writes_nothing(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "planned"
    candidate_id = _prepare_reviewed_candidate(runner, copied_seed_skills, runs_dir)
    existing_generation = managed_prefix / "profiles" / "default" / "generations" / "3"
    existing_generation.mkdir(parents=True)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)
    managed_before = _snapshot_tree(managed_prefix)

    result = runner.invoke(
        app,
        [
            "shadow-activation-acceptance",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["outcome"] == "planned"
    assert data["acceptance_prepared"] is False
    assert data["activation_verified"] is False
    assert data["rollback_verified"] is False
    assert data["mutation_supported"] is False
    assert data["acceptance_prefix_mutated"] is False
    assert data["acceptance_plan_digest"]
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert _snapshot_tree(managed_prefix) == managed_before
    assert not acceptance_prefix.exists()


def test_shadow_activation_acceptance_blocks_outside_runs_dir_without_writes(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    outside_prefix = tmp_path / "outside-acceptance"
    candidate_id = _prepare_reviewed_candidate(runner, copied_seed_skills, runs_dir)
    existing_generation = managed_prefix / "profiles" / "default" / "generations" / "3"
    existing_generation.mkdir(parents=True)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)
    managed_before = _snapshot_tree(managed_prefix)

    result = runner.invoke(
        app,
        [
            "shadow-activation-acceptance",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(outside_prefix),
            "--prepare-acceptance-evidence",
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["outcome"] == "blocked"
    assert data["acceptance_prepared"] is False
    assert "acceptance_prefix_outside_runs_dir" in data["blockers"]
    assert data["acceptance_prefix_mutated"] is False
    assert data["managed_prefix_mutated"] is False
    assert data["durable_skills_mutated"] is False
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert _snapshot_tree(managed_prefix) == managed_before
    assert not outside_prefix.exists()


def test_shadow_activation_acceptance_recovers_interrupted_pointer_state(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "interrupted"
    candidate_id = _prepare_reviewed_candidate(runner, copied_seed_skills, runs_dir)
    existing_generation = managed_prefix / "profiles" / "default" / "generations" / "3"
    existing_generation.mkdir(parents=True)
    planned = build_shadow_activation_acceptance_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
    )
    assert planned.outcome == "planned"
    source_bytes = Path(planned.source_skill_path).read_bytes()
    store_path = Path(planned.acceptance_store_skill_path)
    generation_skill_path = Path(planned.acceptance_generation_skill_path)
    generation_dir = generation_skill_path.parent.parent.parent
    pointer_path = Path(planned.acceptance_activation_pointer)
    rollback_target = Path(planned.acceptance_rollback_target)
    store_path.parent.mkdir(parents=True)
    store_path.write_bytes(source_bytes)
    generation_skill_path.parent.mkdir(parents=True)
    generation_skill_path.write_bytes(source_bytes)
    pointer_path.parent.mkdir(parents=True, exist_ok=True)
    pointer_path.write_text(str(generation_dir), encoding="utf-8")
    durable_before = _snapshot_tree(copied_seed_skills)
    managed_before = _snapshot_tree(managed_prefix)

    result = runner.invoke(
        app,
        [
            "shadow-activation-acceptance",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--prepare-acceptance-evidence",
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["outcome"] == "accepted"
    assert data["activation_pointer_before"] == str(generation_dir)
    assert data["interrupted_activation_recovered"] is True
    assert data["activation_verified"] is True
    assert data["rollback_verified"] is True
    assert data["activation_pointer_after_rollback"] == str(rollback_target)
    assert pointer_path.read_text(encoding="utf-8") == str(rollback_target)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(managed_prefix) == managed_before
    assert not (managed_prefix / "store").exists()


def test_shadow_activation_acceptance_blocks_conflicting_existing_evidence(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "conflict"
    candidate_id = _prepare_reviewed_candidate(runner, copied_seed_skills, runs_dir)
    existing_generation = managed_prefix / "profiles" / "default" / "generations" / "3"
    existing_generation.mkdir(parents=True)
    planned = build_shadow_activation_acceptance_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
    )
    store_path = Path(planned.acceptance_store_skill_path)
    store_path.parent.mkdir(parents=True)
    store_path.write_text("conflicting bytes\n", encoding="utf-8")
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_without_acceptance_before = _snapshot_tree_excluding(runs_dir, acceptance_prefix)
    managed_before = _snapshot_tree(managed_prefix)
    acceptance_before = _snapshot_tree(acceptance_prefix)

    result = runner.invoke(
        app,
        [
            "shadow-activation-acceptance",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--prepare-acceptance-evidence",
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["outcome"] == "blocked"
    assert data["acceptance_prepared"] is False
    assert data["acceptance_conflict_detected"] is True
    assert any(
        blocker.startswith("acceptance_evidence_conflict:")
        for blocker in data["blockers"]
    )
    assert data["activation_pointer_after_activation"] is None
    assert data["activation_pointer_after_rollback"] is None
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree_excluding(runs_dir, acceptance_prefix) == runs_without_acceptance_before
    assert _snapshot_tree(managed_prefix) == managed_before
    assert _snapshot_tree(acceptance_prefix) == acceptance_before


def test_shadow_write_gate_readies_after_prepared_acceptance_without_writes(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "write-gate"
    candidate_id = _prepare_reviewed_candidate(runner, copied_seed_skills, runs_dir)
    existing_generation = managed_prefix / "profiles" / "default" / "generations" / "3"
    existing_generation.mkdir(parents=True)
    (existing_generation / ".marker").write_text("real prefix stays untouched\n", encoding="utf-8")
    current_pointer = managed_prefix / "profiles" / "default" / "current"
    current_pointer.write_text(str(existing_generation), encoding="utf-8")
    acceptance = build_shadow_activation_acceptance_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        prepare_acceptance_evidence=True,
    )
    assert acceptance.outcome == "accepted"
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)
    managed_before = _snapshot_tree(managed_prefix)

    report = build_shadow_write_gate_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        acceptance_plan_digest=acceptance.acceptance_plan_digest,
    )
    json_result = runner.invoke(
        app,
        [
            "shadow-write-gate",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--acceptance-plan-digest",
            str(acceptance.acceptance_plan_digest),
            "--json",
        ],
    )
    text_result = runner.invoke(
        app,
        [
            "shadow-write-gate",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--acceptance-plan-digest",
            str(acceptance.acceptance_plan_digest),
        ],
    )

    assert report.outcome == "ready_for_human_managed_prefix_write"
    assert report.ready_for_human_managed_prefix_write is True
    assert report.source_hash_verified is True
    assert report.acceptance_store_verified is True
    assert report.acceptance_generation_verified is True
    assert report.acceptance_pointer_restored is True
    assert report.acceptance_rollback_marker_verified is True
    assert report.acceptance_plan_digest_verified is True
    assert report.acceptance_prefix_mutated is False
    _assert_no_mutation_flags(report.model_dump(mode="json"))

    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["outcome"] == "ready_for_human_managed_prefix_write"
    assert data["ready_for_human_managed_prefix_write"] is True
    assert data["acceptance_plan_digest"] == acceptance.acceptance_plan_digest
    assert data["expected_acceptance_plan_digest"] == acceptance.acceptance_plan_digest
    assert data["acceptance_store_verified"] is True
    assert data["acceptance_pointer_restored"] is True
    assert data["acceptance_prefix_mutated"] is False
    _assert_no_mutation_flags(data)

    assert text_result.exit_code == 0
    assert "SHADOW_WRITE_GATE" in text_result.stdout
    assert "Ready for human managed-prefix write: true" in text_result.stdout
    assert "Mutation supported: false" in text_result.stdout
    assert "Managed prefix mutated: false" in text_result.stdout

    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert _snapshot_tree(managed_prefix) == managed_before


def test_shadow_write_gate_blocks_without_prepared_acceptance_evidence(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "missing"
    candidate_id = _prepare_reviewed_candidate(runner, copied_seed_skills, runs_dir)
    existing_generation = managed_prefix / "profiles" / "default" / "generations" / "3"
    existing_generation.mkdir(parents=True)
    current_pointer = managed_prefix / "profiles" / "default" / "current"
    current_pointer.write_text(str(existing_generation), encoding="utf-8")
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)
    managed_before = _snapshot_tree(managed_prefix)

    result = runner.invoke(
        app,
        [
            "shadow-write-gate",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["outcome"] == "blocked"
    assert data["ready_for_human_managed_prefix_write"] is False
    assert "acceptance_store_missing_or_hash_mismatch" in data["blockers"]
    assert "acceptance_generation_missing_or_hash_mismatch" in data["blockers"]
    assert "acceptance_pointer_not_restored_to_rollback" in data["blockers"]
    assert "acceptance_rollback_marker_missing" in data["blockers"]
    assert "acceptance_plan_digest_expected_missing" in data["blockers"]
    assert data["acceptance_prefix_mutated"] is False
    _assert_no_mutation_flags(data)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert _snapshot_tree(managed_prefix) == managed_before
    assert not acceptance_prefix.exists()


def test_shadow_write_gate_blocks_acceptance_digest_mismatch_without_writes(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "digest-mismatch"
    candidate_id = _prepare_reviewed_candidate(runner, copied_seed_skills, runs_dir)
    existing_generation = managed_prefix / "profiles" / "default" / "generations" / "3"
    existing_generation.mkdir(parents=True)
    current_pointer = managed_prefix / "profiles" / "default" / "current"
    current_pointer.write_text(str(existing_generation), encoding="utf-8")
    acceptance = build_shadow_activation_acceptance_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        prepare_acceptance_evidence=True,
    )
    assert acceptance.outcome == "accepted"
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)
    managed_before = _snapshot_tree(managed_prefix)

    result = runner.invoke(
        app,
        [
            "shadow-write-gate",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--acceptance-plan-digest",
            "0" * 64,
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["outcome"] == "blocked"
    assert data["ready_for_human_managed_prefix_write"] is False
    assert data["acceptance_plan_digest"] == acceptance.acceptance_plan_digest
    assert data["expected_acceptance_plan_digest"] == "0" * 64
    assert data["acceptance_plan_digest_verified"] is False
    assert "acceptance_plan_digest_mismatch" in data["blockers"]
    assert data["acceptance_store_verified"] is True
    assert data["acceptance_pointer_restored"] is True
    assert data["acceptance_prefix_mutated"] is False
    _assert_no_mutation_flags(data)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert _snapshot_tree(managed_prefix) == managed_before


def test_shadow_managed_write_dry_run_reports_digest_and_never_writes(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "managed-write"
    candidate_id = _prepare_reviewed_candidate(runner, copied_seed_skills, runs_dir)
    existing_generation = managed_prefix / "profiles" / "default" / "generations" / "3"
    existing_generation.mkdir(parents=True)
    (existing_generation / ".marker").write_text("real prefix stays untouched\n", encoding="utf-8")
    current_pointer = managed_prefix / "profiles" / "default" / "current"
    current_pointer.write_text(str(existing_generation), encoding="utf-8")
    acceptance = build_shadow_activation_acceptance_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        prepare_acceptance_evidence=True,
    )
    assert acceptance.outcome == "accepted"
    checkpoint_result = runner.invoke(
        app,
        [
            "evidence-checkpoint",
            "--runs-dir",
            str(runs_dir),
            "--no-dry-run",
            "--json",
        ],
    )
    assert checkpoint_result.exit_code == 0
    latest_checkpoint_hash = json.loads(checkpoint_result.stdout)["latest_checkpoint_hash"]
    gate = build_shadow_write_gate_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        acceptance_plan_digest=acceptance.acceptance_plan_digest,
    )
    assert gate.ready_for_human_managed_prefix_write is True
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)
    managed_before = _snapshot_tree(managed_prefix)

    report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_source_sha256=gate.source_sha256,
        expected_durable_plan_digest=gate.durable_plan_digest,
        expected_shadow_plan_digest=gate.shadow_plan_digest,
        expected_rollback_plan_digest=gate.rollback_plan_digest,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
        expected_checkpoint_hash=latest_checkpoint_hash,
    )
    json_result = runner.invoke(
        app,
        [
            "shadow-managed-write",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--expected-source-sha256",
            str(gate.source_sha256),
            "--expected-durable-plan-digest",
            str(gate.durable_plan_digest),
            "--expected-shadow-plan-digest",
            str(gate.shadow_plan_digest),
            "--expected-rollback-plan-digest",
            str(gate.rollback_plan_digest),
            "--expected-acceptance-plan-digest",
            str(acceptance.acceptance_plan_digest),
            "--expected-checkpoint-hash",
            str(latest_checkpoint_hash),
            "--json",
        ],
    )
    text_result = runner.invoke(
        app,
        [
            "shadow-managed-write",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--expected-acceptance-plan-digest",
            str(acceptance.acceptance_plan_digest),
        ],
    )

    assert report.outcome == "approval_required"
    assert report.managed_write_plan_digest
    assert report.receipt_acceptable is True
    assert report.receipt_reversibility_accepted is True
    assert report.checkpoint_verified is True
    assert report.checkpoint_hash_verified is True
    assert report.shadow_write_gate_ready is True
    assert report.rollback_ready is True
    assert report.source_hash_verified is True
    assert report.expected_source_sha256_verified is True
    assert report.durable_plan_digest_verified is True
    assert report.shadow_plan_digest_verified is True
    assert report.rollback_plan_digest_verified is True
    assert report.acceptance_plan_digest_verified is True
    assert report.write_approval_present is False
    assert report.write_approval_verified is False
    assert report.blockers == []
    unverified_approval_report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
        write_approval_id="future-write-approval",
    )
    assert unverified_approval_report.outcome == "blocked"
    assert unverified_approval_report.ready_for_managed_prefix_write is False
    assert unverified_approval_report.write_approval_present is True
    assert unverified_approval_report.write_approval_verified is False
    assert "write_approval_invalid" in unverified_approval_report.blockers
    _assert_no_mutation_flags(report.model_dump(mode="json"))
    assert report.model_dump(mode="json")["checkpoint_ledger_mutated"] is False

    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["outcome"] == "approval_required"
    assert data["managed_write_plan_digest"] == report.managed_write_plan_digest
    assert data["latest_checkpoint_hash"] == latest_checkpoint_hash
    assert data["receipt_acceptable"] is True
    assert data["expected_source_sha256_verified"] is True
    assert data["checkpoint_verified"] is True
    assert data["shadow_write_gate_ready"] is True
    assert data["rollback_ready"] is True
    assert data["durable_skills_mutated"] is False
    assert data["registry_mutated"] is False
    assert data["candidate_ledger_mutated"] is False
    assert data["resolution_ledger_mutated"] is False
    assert data["run_logs_mutated"] is False
    assert data["governor_steering_enabled"] is False
    _assert_no_mutation_flags(data)

    assert text_result.exit_code == 0
    assert "SHADOW_MANAGED_WRITE" in text_result.stdout
    assert "Outcome: approval_required" in text_result.stdout
    assert "Managed write plan digest:" in text_result.stdout
    assert "Checkpoint verified: true" in text_result.stdout
    assert "Write approval present: false" in text_result.stdout
    assert "Managed prefix mutated: false" in text_result.stdout
    assert "Durable skills mutated: false" in text_result.stdout

    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert _snapshot_tree(managed_prefix) == managed_before


def test_shadow_managed_write_reports_expected_mismatch_and_rejects_no_dry_run(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "managed-write-mismatch"
    candidate_id = _prepare_reviewed_candidate(runner, copied_seed_skills, runs_dir)
    existing_generation = managed_prefix / "profiles" / "default" / "generations" / "1"
    existing_generation.mkdir(parents=True)
    current_pointer = managed_prefix / "profiles" / "default" / "current"
    current_pointer.write_text(str(existing_generation), encoding="utf-8")
    acceptance = build_shadow_activation_acceptance_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        prepare_acceptance_evidence=True,
    )
    checkpoint_result = runner.invoke(
        app,
        [
            "evidence-checkpoint",
            "--runs-dir",
            str(runs_dir),
            "--no-dry-run",
            "--json",
        ],
    )
    assert checkpoint_result.exit_code == 0
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)
    managed_before = _snapshot_tree(managed_prefix)

    mismatch_result = runner.invoke(
        app,
        [
            "shadow-managed-write",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--expected-acceptance-plan-digest",
            str(acceptance.acceptance_plan_digest),
            "--expected-managed-write-plan-digest",
            "0" * 64,
            "--json",
        ],
    )
    no_dry_run_result = runner.invoke(
        app,
        [
            "shadow-managed-write",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--expected-acceptance-plan-digest",
            str(acceptance.acceptance_plan_digest),
            "--no-dry-run",
            "--json",
        ],
    )

    assert mismatch_result.exit_code == 0
    data = json.loads(mismatch_result.stdout)
    assert data["outcome"] == "blocked"
    assert data["expected_managed_write_plan_digest"] == "0" * 64
    assert data["managed_write_plan_digest"] != "0" * 64
    assert data["managed_write_plan_digest_verified"] is False
    assert "expected_managed_write_plan_digest_mismatch" in data["blockers"]
    _assert_no_mutation_flags(data)

    assert no_dry_run_result.exit_code == 0
    no_dry_run_data = json.loads(no_dry_run_result.stdout)
    assert no_dry_run_data["outcome"] == "blocked"
    assert "expected_source_sha256_missing" in no_dry_run_data["blockers"]
    assert "expected_durable_plan_digest_missing" in no_dry_run_data["blockers"]
    assert "expected_shadow_plan_digest_missing" in no_dry_run_data["blockers"]
    assert "expected_rollback_plan_digest_missing" in no_dry_run_data["blockers"]
    assert "expected_managed_write_plan_digest_missing" in no_dry_run_data["blockers"]
    assert "expected_checkpoint_hash_missing" in no_dry_run_data["blockers"]
    assert "write_approval_id_missing" in no_dry_run_data["blockers"]
    assert no_dry_run_data["exact_expected_values_verified"] is False
    assert no_dry_run_data["write_approval_verified"] is False
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert _snapshot_tree(managed_prefix) == managed_before


def test_shadow_managed_write_verifies_write_approval_and_exact_gates(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "managed-write-approved"
    candidate_id, acceptance, gate = _prepare_shadow_managed_write_ready_state(
        runner,
        copied_seed_skills,
        runs_dir,
        managed_prefix,
        acceptance_prefix,
    )
    digest_report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
    )
    assert digest_report.managed_write_plan_digest
    write_approval_id = _record_write_approval(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        managed_write_plan_digest=str(digest_report.managed_write_plan_digest),
        expires_at="2099-01-01T00:00:00Z",
    )
    checkpoint_hash = _append_evidence_checkpoint(runner, runs_dir)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)
    managed_before = _snapshot_tree(managed_prefix)

    report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_source_sha256=gate.source_sha256,
        expected_durable_plan_digest=gate.durable_plan_digest,
        expected_shadow_plan_digest=gate.shadow_plan_digest,
        expected_rollback_plan_digest=gate.rollback_plan_digest,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
        expected_managed_write_plan_digest=digest_report.managed_write_plan_digest,
        expected_checkpoint_hash=checkpoint_hash,
        write_approval_id=write_approval_id,
    )
    cli_result = runner.invoke(
        app,
        [
            "shadow-managed-write",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--expected-source-sha256",
            str(gate.source_sha256),
            "--expected-durable-plan-digest",
            str(gate.durable_plan_digest),
            "--expected-shadow-plan-digest",
            str(gate.shadow_plan_digest),
            "--expected-rollback-plan-digest",
            str(gate.rollback_plan_digest),
            "--expected-acceptance-plan-digest",
            str(acceptance.acceptance_plan_digest),
            "--expected-managed-write-plan-digest",
            str(digest_report.managed_write_plan_digest),
            "--expected-checkpoint-hash",
            str(checkpoint_hash),
            "--write-approval-id",
            write_approval_id,
            "--json",
        ],
    )
    no_dry_run_result = runner.invoke(
        app,
        [
            "shadow-managed-write",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--expected-source-sha256",
            str(gate.source_sha256),
            "--expected-durable-plan-digest",
            str(gate.durable_plan_digest),
            "--expected-shadow-plan-digest",
            str(gate.shadow_plan_digest),
            "--expected-rollback-plan-digest",
            str(gate.rollback_plan_digest),
            "--expected-acceptance-plan-digest",
            str(acceptance.acceptance_plan_digest),
            "--expected-managed-write-plan-digest",
            str(digest_report.managed_write_plan_digest),
            "--expected-checkpoint-hash",
            str(checkpoint_hash),
            "--write-approval-id",
            write_approval_id,
            "--no-dry-run",
            "--json",
        ],
    )

    assert report.outcome == "ready_for_managed_prefix_write"
    assert report.ready_for_managed_prefix_write is True
    assert report.write_approval_verified is True
    assert report.write_approval_digest == digest_report.managed_write_plan_digest
    assert report.write_approval_expires_at == "2099-01-01T00:00:00Z"
    assert report.exact_expected_values_verified is True
    assert report.checkpoint_verified is True
    assert report.checkpoint_hash_verified is True
    assert report.shadow_write_gate_ready is True
    assert report.receipt_acceptable is True
    assert report.blockers == []
    _assert_no_mutation_flags(report.model_dump(mode="json"))

    assert cli_result.exit_code == 0
    data = json.loads(cli_result.stdout)
    assert data["outcome"] == "ready_for_managed_prefix_write"
    assert data["ready_for_managed_prefix_write"] is True
    assert data["write_approval_verified"] is True
    assert data["exact_expected_values_verified"] is True
    assert data["write_approval_digest"] == digest_report.managed_write_plan_digest

    assert no_dry_run_result.exit_code == 0
    no_dry_run_data = json.loads(no_dry_run_result.stdout)
    assert no_dry_run_data["outcome"] == "managed_prefix_write_applied"
    assert no_dry_run_data["dry_run"] is False
    assert no_dry_run_data["mutation_supported"] is True
    assert no_dry_run_data["ready_for_managed_prefix_write"] is True
    assert no_dry_run_data["write_approval_verified"] is True
    assert no_dry_run_data["exact_expected_values_verified"] is True
    assert no_dry_run_data["store_verified"] is True
    assert no_dry_run_data["generation_verified"] is True
    assert no_dry_run_data["activation_pointer_updated"] is True
    assert no_dry_run_data["activation_pointer_verified"] is True
    assert no_dry_run_data["rollback_target_verified"] is True
    assert no_dry_run_data["managed_prefix_mutated"] is True
    assert no_dry_run_data["profile_mutated"] is True
    assert no_dry_run_data["durable_skills_mutated"] is False
    assert no_dry_run_data["registry_mutated"] is False
    assert no_dry_run_data["candidate_ledger_mutated"] is False
    assert no_dry_run_data["resolution_ledger_mutated"] is False
    assert no_dry_run_data["run_logs_mutated"] is False
    assert no_dry_run_data["governor_steering_enabled"] is False
    assert no_dry_run_data["blockers"] == []
    assert Path(no_dry_run_data["store_skill_path"]).read_bytes() == Path(no_dry_run_data["source_skill_path"]).read_bytes()
    assert Path(no_dry_run_data["generation_skill_path"]).read_bytes() == Path(no_dry_run_data["source_skill_path"]).read_bytes()
    assert Path(no_dry_run_data["activation_pointer"]).read_text(encoding="utf-8").strip() == str(
        Path(no_dry_run_data["generation_skill_path"]).parent.parent.parent
    )
    assert Path(no_dry_run_data["write_receipt_path"]).exists()

    rerun_result = runner.invoke(
        app,
        [
            "shadow-managed-write",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--managed-prefix",
            str(managed_prefix),
            "--acceptance-prefix",
            str(acceptance_prefix),
            "--expected-source-sha256",
            str(gate.source_sha256),
            "--expected-durable-plan-digest",
            str(gate.durable_plan_digest),
            "--expected-shadow-plan-digest",
            str(gate.shadow_plan_digest),
            "--expected-rollback-plan-digest",
            str(gate.rollback_plan_digest),
            "--expected-acceptance-plan-digest",
            str(acceptance.acceptance_plan_digest),
            "--expected-managed-write-plan-digest",
            str(digest_report.managed_write_plan_digest),
            "--expected-checkpoint-hash",
            str(checkpoint_hash),
            "--write-approval-id",
            write_approval_id,
            "--no-dry-run",
            "--json",
        ],
    )
    assert rerun_result.exit_code == 0
    rerun_data = json.loads(rerun_result.stdout)
    assert rerun_data["outcome"] == "already_applied"
    assert rerun_data["dry_run"] is False
    assert rerun_data["mutation_supported"] is True
    assert rerun_data["already_applied"] is True
    assert rerun_data["managed_prefix_mutated"] is False
    assert rerun_data["profile_mutated"] is False
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert _snapshot_tree(managed_prefix) != managed_before


def test_shadow_managed_write_recovers_interrupted_store_generation_retry(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "managed-write-interrupted"
    candidate_id, acceptance, gate = _prepare_shadow_managed_write_ready_state(
        runner,
        copied_seed_skills,
        runs_dir,
        managed_prefix,
        acceptance_prefix,
    )
    digest_report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
    )
    assert digest_report.managed_write_plan_digest
    source_bytes = Path(str(gate.source_skill_path)).read_bytes()
    store_path = Path(str(digest_report.store_skill_path))
    generation_path = Path(str(digest_report.generation_skill_path))
    store_path.parent.mkdir(parents=True, exist_ok=True)
    generation_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_bytes(source_bytes)
    generation_path.write_bytes(source_bytes)
    write_approval_id = _record_write_approval(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        managed_write_plan_digest=str(digest_report.managed_write_plan_digest),
        expires_at="2099-01-01T00:00:00Z",
    )
    checkpoint_hash = _append_evidence_checkpoint(runner, runs_dir)

    report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        dry_run=False,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_source_sha256=gate.source_sha256,
        expected_durable_plan_digest=gate.durable_plan_digest,
        expected_shadow_plan_digest=gate.shadow_plan_digest,
        expected_rollback_plan_digest=gate.rollback_plan_digest,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
        expected_managed_write_plan_digest=digest_report.managed_write_plan_digest,
        expected_checkpoint_hash=checkpoint_hash,
        write_approval_id=write_approval_id,
    )

    assert report.outcome == "managed_prefix_write_applied"
    assert report.interrupted_activation_recovered is True
    assert report.store_verified is True
    assert report.generation_verified is True
    assert report.activation_pointer_verified is True
    assert report.rollback_target_verified is True
    assert Path(str(report.write_receipt_path)).exists()
    assert report.blockers == []


def test_shadow_managed_write_blocks_conflicting_managed_prefix_bytes_without_pointer_switch(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "managed-write-conflict"
    candidate_id, acceptance, gate = _prepare_shadow_managed_write_ready_state(
        runner,
        copied_seed_skills,
        runs_dir,
        managed_prefix,
        acceptance_prefix,
    )
    digest_report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
    )
    assert digest_report.managed_write_plan_digest
    store_path = Path(str(digest_report.store_skill_path))
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text("conflicting bytes\n", encoding="utf-8")
    pointer_before = Path(str(digest_report.activation_pointer)).read_text(encoding="utf-8")
    write_approval_id = _record_write_approval(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        managed_write_plan_digest=str(digest_report.managed_write_plan_digest),
        expires_at="2099-01-01T00:00:00Z",
    )
    checkpoint_hash = _append_evidence_checkpoint(runner, runs_dir)

    report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        dry_run=False,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_source_sha256=gate.source_sha256,
        expected_durable_plan_digest=gate.durable_plan_digest,
        expected_shadow_plan_digest=gate.shadow_plan_digest,
        expected_rollback_plan_digest=gate.rollback_plan_digest,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
        expected_managed_write_plan_digest=digest_report.managed_write_plan_digest,
        expected_checkpoint_hash=checkpoint_hash,
        write_approval_id=write_approval_id,
    )

    assert report.outcome == "blocked"
    assert "managed_write_store_conflict" in report.blockers
    assert report.managed_prefix_mutated is False
    assert report.profile_mutated is False
    assert Path(str(digest_report.activation_pointer)).read_text(encoding="utf-8") == pointer_before
    assert not Path(str(report.write_receipt_path)).exists()


def test_shadow_managed_write_restores_pointer_when_receipt_write_fails(
    copied_seed_skills,
    tmp_path,
    monkeypatch,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "managed-write-io-failure"
    candidate_id, acceptance, gate, digest_report, write_approval_id, checkpoint_hash = (
        _prepare_approved_managed_write_inputs(
            runner,
            copied_seed_skills,
            runs_dir,
            managed_prefix,
            acceptance_prefix,
        )
    )
    rollback_pointer_target = Path(str(digest_report.activation_pointer)).read_text(
        encoding="utf-8"
    ).strip()
    original_atomic_write_text = __import__(
        "app.shadow_activation",
        fromlist=["_atomic_write_text"],
    )._atomic_write_text

    def fail_receipt_write(path: Path, text: str) -> None:
        if path == Path(str(digest_report.write_receipt_path)):
            raise OSError("receipt write failed")
        original_atomic_write_text(path, text)

    monkeypatch.setattr(
        "app.shadow_activation._atomic_write_text",
        fail_receipt_write,
    )

    report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        dry_run=False,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_source_sha256=gate.source_sha256,
        expected_durable_plan_digest=gate.durable_plan_digest,
        expected_shadow_plan_digest=gate.shadow_plan_digest,
        expected_rollback_plan_digest=gate.rollback_plan_digest,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
        expected_managed_write_plan_digest=digest_report.managed_write_plan_digest,
        expected_checkpoint_hash=checkpoint_hash,
        write_approval_id=write_approval_id,
    )

    assert report.outcome == "blocked"
    assert "managed_write_receipt_write_failed" in report.blockers
    assert Path(str(digest_report.activation_pointer)).read_text(encoding="utf-8").strip() == rollback_pointer_target
    assert not Path(str(digest_report.write_receipt_path)).exists()
    assert report.managed_prefix_mutated is True
    assert report.profile_mutated is True


def test_shadow_managed_write_blocks_symlink_ancestor_escape(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "managed-write-symlink"
    candidate_id, acceptance, gate, digest_report, write_approval_id, checkpoint_hash = (
        _prepare_approved_managed_write_inputs(
            runner,
            copied_seed_skills,
            runs_dir,
            managed_prefix,
            acceptance_prefix,
        )
    )
    store_root = managed_prefix / "store"
    escape_root = tmp_path / "escape-store"
    escape_root.mkdir()
    store_root.symlink_to(escape_root, target_is_directory=True)

    report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        dry_run=False,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_source_sha256=gate.source_sha256,
        expected_durable_plan_digest=gate.durable_plan_digest,
        expected_shadow_plan_digest=gate.shadow_plan_digest,
        expected_rollback_plan_digest=gate.rollback_plan_digest,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
        expected_managed_write_plan_digest=digest_report.managed_write_plan_digest,
        expected_checkpoint_hash=checkpoint_hash,
        write_approval_id=write_approval_id,
    )

    assert report.outcome == "blocked"
    assert any(blocker.startswith("managed_write_path_symlink:") for blocker in report.blockers)
    assert report.managed_prefix_mutated is False
    assert not Path(str(digest_report.write_receipt_path)).exists()


def test_shadow_managed_write_blocks_managed_prefix_symlink_escape(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    actual_prefix = tmp_path / "actual-shadow-prefix"
    actual_prefix.mkdir()
    managed_prefix.symlink_to(actual_prefix, target_is_directory=True)
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "managed-write-prefix-symlink"
    candidate_id, acceptance, gate, digest_report, write_approval_id, checkpoint_hash = (
        _prepare_approved_managed_write_inputs(
            runner,
            copied_seed_skills,
            runs_dir,
            managed_prefix,
            acceptance_prefix,
        )
    )

    report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        dry_run=False,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_source_sha256=gate.source_sha256,
        expected_durable_plan_digest=gate.durable_plan_digest,
        expected_shadow_plan_digest=gate.shadow_plan_digest,
        expected_rollback_plan_digest=gate.rollback_plan_digest,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
        expected_managed_write_plan_digest=digest_report.managed_write_plan_digest,
        expected_checkpoint_hash=checkpoint_hash,
        write_approval_id=write_approval_id,
    )

    assert report.outcome == "blocked"
    assert f"managed_write_path_symlink:{managed_prefix}" in report.blockers
    assert report.managed_prefix_mutated is False
    assert not Path(str(digest_report.write_receipt_path)).exists()


def test_shadow_managed_write_blocks_pointer_switched_without_receipt_rerun(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "managed-write-missing-receipt"
    candidate_id, acceptance, gate, digest_report, write_approval_id, checkpoint_hash = (
        _prepare_approved_managed_write_inputs(
            runner,
            copied_seed_skills,
            runs_dir,
            managed_prefix,
            acceptance_prefix,
        )
    )
    source_bytes = Path(str(gate.source_skill_path)).read_bytes()
    store_path = Path(str(digest_report.store_skill_path))
    generation_path = Path(str(digest_report.generation_skill_path))
    generation_dir = generation_path.parent.parent.parent
    store_path.parent.mkdir(parents=True, exist_ok=True)
    generation_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_bytes(source_bytes)
    generation_path.write_bytes(source_bytes)
    Path(str(digest_report.activation_pointer)).write_text(str(generation_dir), encoding="utf-8")

    report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        dry_run=False,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_source_sha256=gate.source_sha256,
        expected_durable_plan_digest=gate.durable_plan_digest,
        expected_shadow_plan_digest=gate.shadow_plan_digest,
        expected_rollback_plan_digest=gate.rollback_plan_digest,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
        expected_managed_write_plan_digest=digest_report.managed_write_plan_digest,
        expected_checkpoint_hash=checkpoint_hash,
        write_approval_id=write_approval_id,
    )

    assert report.outcome == "blocked"
    assert "managed_write_receipt_missing_after_pointer_switch" in report.blockers
    assert not Path(str(digest_report.write_receipt_path)).exists()
    assert not (managed_prefix / "profiles" / "default" / "generations" / "5").exists()


def test_shadow_managed_write_blocks_write_approval_mismatch_expiry_and_checkpoint_mismatch(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    managed_prefix = tmp_path / "shadow-prefix"
    acceptance_prefix = runs_dir / "shadow_activation_acceptance" / "managed-write-bad-approval"
    candidate_id, acceptance, gate = _prepare_shadow_managed_write_ready_state(
        runner,
        copied_seed_skills,
        runs_dir,
        managed_prefix,
        acceptance_prefix,
    )
    digest_report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
    )
    assert digest_report.managed_write_plan_digest

    mismatch_approval_id = _record_write_approval(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        managed_write_plan_digest="0" * 64,
        expires_at="2099-01-01T00:00:00Z",
    )
    mismatch_checkpoint_hash = _append_evidence_checkpoint(runner, runs_dir)
    mismatch_report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_source_sha256=gate.source_sha256,
        expected_durable_plan_digest=gate.durable_plan_digest,
        expected_shadow_plan_digest=gate.shadow_plan_digest,
        expected_rollback_plan_digest=gate.rollback_plan_digest,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
        expected_managed_write_plan_digest=digest_report.managed_write_plan_digest,
        expected_checkpoint_hash=mismatch_checkpoint_hash,
        write_approval_id=mismatch_approval_id,
    )

    expired_approval_id = _record_write_approval(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        managed_write_plan_digest=str(digest_report.managed_write_plan_digest),
        expires_at="2000-01-01T00:00:00Z",
    )
    expired_checkpoint_hash = _append_evidence_checkpoint(runner, runs_dir)
    expired_report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_source_sha256=gate.source_sha256,
        expected_durable_plan_digest=gate.durable_plan_digest,
        expected_shadow_plan_digest=gate.shadow_plan_digest,
        expected_rollback_plan_digest=gate.rollback_plan_digest,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
        expected_managed_write_plan_digest=digest_report.managed_write_plan_digest,
        expected_checkpoint_hash=expired_checkpoint_hash,
        write_approval_id=expired_approval_id,
    )

    valid_approval_id = _record_write_approval(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        managed_write_plan_digest=str(digest_report.managed_write_plan_digest),
        expires_at="2099-01-01T00:00:00Z",
    )
    _append_evidence_checkpoint(runner, runs_dir)
    checkpoint_mismatch_report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_source_sha256=gate.source_sha256,
        expected_durable_plan_digest=gate.durable_plan_digest,
        expected_shadow_plan_digest=gate.shadow_plan_digest,
        expected_rollback_plan_digest=gate.rollback_plan_digest,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
        expected_managed_write_plan_digest=digest_report.managed_write_plan_digest,
        expected_checkpoint_hash="0" * 64,
        write_approval_id=valid_approval_id,
    )

    assert mismatch_report.outcome == "blocked"
    assert mismatch_report.write_approval_verified is False
    assert mismatch_report.write_approval_digest == "0" * 64
    assert "write_approval_digest_mismatch" in mismatch_report.blockers
    assert mismatch_report.exact_expected_values_verified is True

    assert expired_report.outcome == "blocked"
    assert expired_report.write_approval_verified is False
    assert expired_report.write_approval_expires_at == "2000-01-01T00:00:00Z"
    assert "write_approval_expired" in expired_report.blockers
    assert expired_report.exact_expected_values_verified is True

    assert checkpoint_mismatch_report.outcome == "blocked"
    assert checkpoint_mismatch_report.write_approval_verified is True
    assert checkpoint_mismatch_report.exact_expected_values_verified is False
    assert checkpoint_mismatch_report.checkpoint_hash_verified is False
    assert "expected_checkpoint_hash_mismatch" in checkpoint_mismatch_report.blockers


def _prepare_reviewed_candidate(
    runner: CliRunner,
    skills_dir: Path,
    runs_dir: Path,
) -> str:
    run_result = runner.invoke(
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
    assert run_result.exit_code == 0
    candidate_id = load_candidate_ledger(runs_dir).entries[0].candidate_id
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
    admission = json.loads(admission_result.stdout)
    input_request = admission["input_request"]
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
    return candidate_id


def _prepare_shadow_managed_write_ready_state(
    runner: CliRunner,
    skills_dir: Path,
    runs_dir: Path,
    managed_prefix: Path,
    acceptance_prefix: Path,
):
    candidate_id = _prepare_reviewed_candidate(runner, skills_dir, runs_dir)
    existing_generation = managed_prefix / "profiles" / "default" / "generations" / "3"
    existing_generation.mkdir(parents=True)
    (existing_generation / ".marker").write_text("real prefix stays untouched\n", encoding="utf-8")
    current_pointer = managed_prefix / "profiles" / "default" / "current"
    current_pointer.write_text(str(existing_generation), encoding="utf-8")
    acceptance = build_shadow_activation_acceptance_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=skills_dir,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        prepare_acceptance_evidence=True,
    )
    assert acceptance.outcome == "accepted"
    gate = build_shadow_write_gate_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=skills_dir,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        acceptance_plan_digest=acceptance.acceptance_plan_digest,
    )
    assert gate.ready_for_human_managed_prefix_write is True
    return candidate_id, acceptance, gate


def _prepare_approved_managed_write_inputs(
    runner: CliRunner,
    skills_dir: Path,
    runs_dir: Path,
    managed_prefix: Path,
    acceptance_prefix: Path,
):
    candidate_id, acceptance, gate = _prepare_shadow_managed_write_ready_state(
        runner,
        skills_dir,
        runs_dir,
        managed_prefix,
        acceptance_prefix,
    )
    digest_report = build_shadow_managed_write_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=skills_dir,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        expected_acceptance_plan_digest=acceptance.acceptance_plan_digest,
    )
    assert digest_report.managed_write_plan_digest
    write_approval_id = _record_write_approval(
        runner,
        candidate_id,
        runs_dir,
        skills_dir,
        managed_write_plan_digest=str(digest_report.managed_write_plan_digest),
        expires_at="2099-01-01T00:00:00Z",
    )
    checkpoint_hash = _append_evidence_checkpoint(runner, runs_dir)
    return candidate_id, acceptance, gate, digest_report, write_approval_id, checkpoint_hash


def _record_write_approval(
    runner: CliRunner,
    candidate_id: str,
    runs_dir: Path,
    skills_dir: Path,
    *,
    managed_write_plan_digest: str,
    expires_at: str,
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
            f"Approved managed write. managed_write_plan_digest={managed_write_plan_digest} expires_at={expires_at}",
            "--no-dry-run",
            "--json",
        ],
    )
    assert resolve_result.exit_code == 0
    ledger = load_input_request_resolution_ledger(runs_dir)
    return ledger.resolutions[-1].id


def _append_evidence_checkpoint(runner: CliRunner, runs_dir: Path) -> str:
    checkpoint_result = runner.invoke(
        app,
        [
            "evidence-checkpoint",
            "--runs-dir",
            str(runs_dir),
            "--no-dry-run",
            "--json",
        ],
    )
    assert checkpoint_result.exit_code == 0
    checkpoint_hash = json.loads(checkpoint_result.stdout)["latest_checkpoint_hash"]
    assert checkpoint_hash
    return checkpoint_hash


def _assert_no_mutation_flags(data: dict) -> None:
    assert data["managed_prefix_mutated"] is False
    assert data["profile_mutated"] is False
    assert data["run_logs_mutated"] is False
    assert data["candidate_ledger_mutated"] is False
    assert data["resolution_ledger_mutated"] is False
    assert data["durable_skills_mutated"] is False
    assert data["registry_mutated"] is False
    assert data["governor_steering_enabled"] is False


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    if not path.exists():
        return {}
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def _snapshot_tree_excluding(path: Path, excluded: Path) -> dict[str, bytes]:
    if not path.exists():
        return {}
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
        and not item.resolve(strict=False).is_relative_to(excluded.resolve(strict=False))
    }
