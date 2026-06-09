from __future__ import annotations

import json
from pathlib import Path
from shutil import copytree

from typer.testing import CliRunner

from app.admission_plan import build_admission_plan
from app.agent_loop import run_task
from app.cli import app
from app.durable_admission import build_durable_admission_preview
from app.input_resolution import InputResolutionError, resolve_input_request
from app.input_resolution_ledger import (
    append_input_request_resolution,
    load_input_request_resolution_ledger,
)
from app.models import InputRequest, InputRequestResolutionDryRun
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
    assert preview.target_skill_path == str(
        copied_seed_skills / "argument-clustering" / "SKILL.md"
    )
    assert preview.write_plan.operation == "blocked"
    assert preview.write_plan.collision_policy == "block_existing"
    assert preview.write_plan.permission_policy == "block_widening_without_approval"
    assert preview.write_plan.source_skill_path == str(source_path)
    assert preview.write_plan.source_sha256 == preview.source_sha256
    assert preview.write_plan.plan_digest_algorithm == "sha256"
    assert preview.write_plan.plan_digest is not None
    assert preview.write_plan.plan_approval_verified is False
    assert preview.write_plan.target_skill_path == preview.target_skill_path
    assert preview.write_plan.snapshot_dir == str(
        runs_dir / "admission_snapshots" / candidate_id / preview.source_sha256
    )
    assert preview.write_plan.snapshot_skill_path == str(
        runs_dir / "admission_snapshots" / candidate_id / preview.source_sha256 / "SKILL.md"
    )
    assert preview.write_plan.snapshot_sha256 == preview.source_sha256
    assert preview.write_plan.source_snapshot_created is False
    assert preview.blockers == [
        "durable_review_resolution_missing",
        "plan_digest_approval_missing",
    ]
    assert preview.write_plan.blockers == [
        "durable_review_resolution_missing",
        "plan_digest_approval_missing",
    ]
    assert preview.required_human_records == [
        "promotion_approved_by",
        "promotion_approved_at",
        "durable_admission_review approve_review resolution",
        "plan digest approval resolution",
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
    assert not (runs_dir / "admission_snapshots").exists()


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
    initial_preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )
    assert initial_preview.write_plan.plan_digest is not None
    _approve_durable_review(
        candidate_id,
        runs_dir,
        copied_seed_skills,
        plan_digest=initial_preview.write_plan.plan_digest,
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
    assert preview.write_plan.operation == "copy_new_skill"
    assert preview.write_plan.blockers == []
    assert preview.write_plan.plan_approval_verified is True
    assert preview.write_plan.plan_approval_digest == preview.write_plan.plan_digest
    assert preview.write_plan.permission_dependency_diff.added_permission_classes == []
    assert preview.write_plan.permission_dependency_diff.added_tools == []
    assert (
        preview.write_plan.permission_dependency_diff.dependency_diff.dependencies_declared
        is False
    )
    assert (
        preview.write_plan.permission_dependency_diff.dependency_diff.exact_realization_available
        is True
    )
    assert preview.write_plan.replacement_approved is False
    assert preview.write_plan.permission_widening_approved is False
    assert preview.write_plan.source_snapshot_created is False
    assert preview.blockers == []
    assert preview.next_steps == [
        "Review the target path and source fingerprint.",
        "Future install/copy remains disabled until a separate write-mode slice exists.",
    ]
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert not (runs_dir / "admission_snapshots").exists()


def test_durable_admission_preview_blocks_default_same_name_collision(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _promoted_candidate(copied_seed_skills, runs_dir)
    _approve_current_plan(candidate_id, runs_dir, copied_seed_skills)
    copytree(source_path.parent, copied_seed_skills / "argument-clustering")
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )

    assert preview.ready_for_mutation_preview is False
    assert preview.write_plan.operation == "blocked"
    assert preview.write_plan.collision_policy == "block_existing"
    assert "durable_name_collision" in preview.write_plan.blockers
    assert "admission_plan_outcome:blocked" in preview.write_plan.blockers
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_durable_admission_preview_blocks_replace_policy_without_review_approval(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _promoted_candidate(copied_seed_skills, runs_dir)
    copytree(source_path.parent, copied_seed_skills / "argument-clustering")

    preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        collision_policy="allow_replace_with_approval",
    )

    assert preview.ready_for_mutation_preview is False
    assert preview.write_plan.operation == "blocked"
    assert preview.write_plan.replacement_approved is False
    assert "durable_name_collision" in preview.write_plan.blockers
    assert "durable_review_resolution_missing" in preview.write_plan.blockers


def test_durable_admission_preview_allows_replace_plan_with_policy_and_review_evidence(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _promoted_candidate(copied_seed_skills, runs_dir)
    copytree(source_path.parent, copied_seed_skills / "argument-clustering")
    initial_preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        collision_policy="allow_replace_with_approval",
    )
    assert initial_preview.write_plan.plan_digest is not None
    _approve_durable_review(
        candidate_id,
        runs_dir,
        copied_seed_skills,
        plan_digest=initial_preview.write_plan.plan_digest,
    )
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        collision_policy="allow_replace_with_approval",
    )

    assert preview.ready_for_mutation_preview is True
    assert preview.write_plan.operation == "replace_existing_skill"
    assert preview.write_plan.replacement_approved is True
    assert preview.write_plan.plan_approval_verified is True
    assert preview.write_plan.blockers == []
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert not (runs_dir / "admission_snapshots").exists()


def test_durable_admission_preview_blocks_permission_widening_without_permission_approval(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _promoted_candidate(copied_seed_skills, runs_dir)
    permission_approval_id = _approve_durable_review(
        candidate_id,
        runs_dir,
        copied_seed_skills,
    )
    _enable_network_permission(source_path)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )

    assert preview.ready_for_mutation_preview is False
    assert preview.write_plan.operation == "blocked"
    assert "source_permission_widening" in preview.write_plan.blockers
    assert "permission_widening_approval_missing" in preview.write_plan.blockers
    assert "permission widening approval resolution" in preview.required_human_records
    assert preview.write_plan.permission_widening_approved is False
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before

    approved_preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        permission_approval_id=permission_approval_id,
    )

    assert approved_preview.write_plan.permission_widening_approved is True
    assert (
        "network"
        in approved_preview.write_plan.permission_dependency_diff.added_permission_classes
    )
    assert approved_preview.write_plan.permission_dependency_diff.permission_approval_required is True
    assert "permission_widening_approval_missing" not in approved_preview.write_plan.blockers
    assert "source_permission_widening" in approved_preview.write_plan.blockers
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_durable_admission_preview_blocks_dependency_declaration_without_realization(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _promoted_candidate(copied_seed_skills, runs_dir)
    _append_dependency_declaration(source_path)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )

    dependency_diff = preview.write_plan.permission_dependency_diff.dependency_diff
    assert preview.ready_for_mutation_preview is False
    assert dependency_diff.dependencies_declared is True
    assert dependency_diff.declaration_keys == ["dependencies"]
    assert dependency_diff.exact_realization_available is False
    assert dependency_diff.added == ["example-package"]
    assert dependency_diff.realized == []
    assert dependency_diff.unresolved == ["example-package"]
    assert "dependency_realization_missing" in dependency_diff.blockers
    contract = preview.write_plan.dependency_install_contract
    assert contract.dependency_plan_digest
    assert contract.install_supported is False
    assert contract.install_attempted is False
    assert contract.dependencies_installed is False
    assert contract.normalized_dependencies[0].model_dump(mode="json") == {
        "name": "example-package",
        "declaration_keys": ["dependencies"],
        "declaration_sources": ["dependencies"],
        "declared_spec": "example-package==1.0.0",
        "declared_version": "1.0.0",
        "declared_specs": ["example-package==1.0.0"],
        "declared_versions": ["1.0.0"],
        "realization_version": None,
        "realization_sha256": None,
        "realization_candidates": [],
        "status": "unresolved",
        "warnings": [],
    }
    assert "dependency_realization_missing" in contract.blockers
    assert "dependency_realization_missing" in preview.write_plan.blockers
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_durable_admission_preview_extracts_requirement_and_package_dependency_names(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _promoted_candidate(copied_seed_skills, runs_dir)
    _append_requirement_package_declarations(source_path)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )

    dependency_diff = preview.write_plan.permission_dependency_diff.dependency_diff
    assert preview.ready_for_mutation_preview is False
    assert dependency_diff.dependencies_declared is True
    assert dependency_diff.declaration_keys == [
        "dependency_lock",
        "packages",
        "requirements",
    ]
    assert dependency_diff.added == [
        "locked-package",
        "package-two",
        "requirement-one",
    ]
    assert dependency_diff.unresolved == [
        "locked-package",
        "package-two",
        "requirement-one",
    ]
    assert "dependency_realization_missing" in dependency_diff.blockers
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_durable_admission_preview_recognizes_exact_dependency_realization_but_blocks_install(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _promoted_candidate(copied_seed_skills, runs_dir)
    _append_dependency_declaration(source_path, exact=True)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )

    dependency_diff = preview.write_plan.permission_dependency_diff.dependency_diff
    assert preview.ready_for_mutation_preview is False
    assert dependency_diff.dependencies_declared is True
    assert dependency_diff.declaration_keys == ["dependencies", "dependency_realization"]
    assert dependency_diff.exact_realization_available is True
    assert dependency_diff.added == ["example-package"]
    assert dependency_diff.realized == ["example-package"]
    assert dependency_diff.unresolved == []
    assert "dependency_realization_missing" not in dependency_diff.blockers
    assert "dependency_install_unsupported" in dependency_diff.blockers
    contract = preview.write_plan.dependency_install_contract
    assert contract.normalized_dependencies[0].status == "exact_realized"
    assert contract.normalized_dependencies[0].realization_version == "1.0.0"
    assert (
        contract.normalized_dependencies[0].realization_sha256
        == "0123456789abcdef" * 4
    )
    assert "dependency_install_unsupported" in contract.blockers
    assert contract.dependency_approval_verified is False
    assert "dependency_install_unsupported" in preview.write_plan.blockers
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_dependency_plan_digest_changes_when_dependency_details_change(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _promoted_candidate(copied_seed_skills, runs_dir)
    _append_dependency_declaration(source_path)

    first = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )
    first_digest = first.write_plan.dependency_install_contract.dependency_plan_digest
    text = source_path.read_text(encoding="utf-8")
    source_path.write_text(
        text.replace("example-package==1.0.0", "example-package==2.0.0", 1),
        encoding="utf-8",
    )
    second = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )
    second_digest = second.write_plan.dependency_install_contract.dependency_plan_digest
    text = source_path.read_text(encoding="utf-8")
    source_path.write_text(
        text.replace(
            "dependencies:\n  - example-package==2.0.0\n---",
            "dependencies:\n  - example-package==2.0.0\n"
            "dependency_realization:\n"
            "  - name: example-package\n"
            "    version: 2.0.0\n"
            "    sha256: fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210\n"
            "---",
            1,
        ),
        encoding="utf-8",
    )
    third = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )

    assert first_digest
    assert second_digest
    assert third.write_plan.dependency_install_contract.dependency_plan_digest
    assert second_digest != first_digest
    assert third.write_plan.dependency_install_contract.dependency_plan_digest != second_digest



def test_dependency_plan_digest_changes_when_non_first_conflicting_spec_changes(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _promoted_candidate(copied_seed_skills, runs_dir)
    _append_dependency_declaration(source_path)
    text = source_path.read_text(encoding="utf-8")
    source_path.write_text(
        text.replace(
            "dependencies:\n  - example-package==1.0.0\n---",
            "dependencies:\n  - example-package==1.0.0\n  - example-package==2.0.0\n---",
            1,
        ),
        encoding="utf-8",
    )
    first = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )
    first_contract = first.write_plan.dependency_install_contract
    source_path.write_text(
        source_path.read_text(encoding="utf-8").replace(
            "example-package==2.0.0",
            "example-package==3.0.0",
            1,
        ),
        encoding="utf-8",
    )
    second = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )
    second_contract = second.write_plan.dependency_install_contract

    assert first_contract.normalized_dependencies[0].declared_specs == [
        "example-package==1.0.0",
        "example-package==2.0.0",
    ]
    assert "dependency_declaration_conflict" in first_contract.normalized_dependencies[0].warnings
    assert second_contract.normalized_dependencies[0].declared_specs == [
        "example-package==1.0.0",
        "example-package==3.0.0",
    ]
    assert second_contract.dependency_plan_digest != first_contract.dependency_plan_digest


def test_dependency_plan_digest_changes_when_non_selected_realization_changes(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _promoted_candidate(copied_seed_skills, runs_dir)
    _append_dependency_declaration(source_path, exact=True)
    text = source_path.read_text(encoding="utf-8")
    source_path.write_text(
        text.replace(
            "dependency_realization:\n"
            "  - name: example-package\n"
            "    version: 1.0.0\n"
            "    sha256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\n",
            "dependency_realization:\n"
            "  - name: example-package\n"
            "    version: 1.0.0\n"
            "    sha256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\n"
            "  - name: example-package\n"
            "    version: 1.0.0\n"
            "    sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n",
            1,
        ),
        encoding="utf-8",
    )
    first = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )
    first_contract = first.write_plan.dependency_install_contract
    source_path.write_text(
        source_path.read_text(encoding="utf-8").replace(
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            1,
        ),
        encoding="utf-8",
    )
    second = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )
    second_contract = second.write_plan.dependency_install_contract

    assert len(first_contract.normalized_dependencies[0].realization_candidates) == 2
    assert len(second_contract.normalized_dependencies[0].realization_candidates) == 2
    assert second_contract.dependency_plan_digest != first_contract.dependency_plan_digest

def test_dependency_approval_is_evidence_only_and_digest_bound(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _promoted_candidate(copied_seed_skills, runs_dir)
    _append_dependency_declaration(source_path, exact=True)
    initial = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )
    digest = initial.write_plan.dependency_install_contract.dependency_plan_digest
    assert digest is not None
    approval_id = _append_dependency_approval_record(
        candidate_id,
        runs_dir,
        dependency_plan_digest=digest,
    )

    preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        dependency_approval_id=approval_id,
    )

    contract = preview.write_plan.dependency_install_contract
    assert contract.dependency_approval_verified is True
    assert contract.dependency_approval_id == approval_id
    assert contract.dependency_approval_digest == digest
    assert "dependency_install_unsupported" in contract.blockers
    assert "dependency_install_unsupported" in preview.write_plan.blockers
    assert contract.install_supported is False
    assert contract.install_attempted is False
    assert contract.dependencies_installed is False


def test_dependency_approval_rejects_mismatched_and_expired_records(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, source_path = _promoted_candidate(copied_seed_skills, runs_dir)
    _append_dependency_declaration(source_path, exact=True)
    mismatch_id = _append_dependency_approval_record(
        candidate_id,
        runs_dir,
        dependency_plan_digest="0" * 64,
    )
    initial = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )
    assert initial.write_plan.dependency_install_contract.dependency_plan_digest
    expired_id = _append_dependency_approval_record(
        candidate_id,
        runs_dir,
        dependency_plan_digest=initial.write_plan.dependency_install_contract.dependency_plan_digest,
        expires_at="2000-01-01T00:00:00Z",
    )
    missing_expiry_id = _append_dependency_approval_record(
        candidate_id,
        runs_dir,
        dependency_plan_digest=initial.write_plan.dependency_install_contract.dependency_plan_digest,
        expires_at=None,
    )

    mismatch = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        dependency_approval_id=mismatch_id,
    )
    expired = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        dependency_approval_id=expired_id,
    )
    missing_expiry = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        dependency_approval_id=missing_expiry_id,
    )

    assert mismatch.write_plan.dependency_install_contract.dependency_approval_verified is False
    assert "dependency_plan_approval_mismatch" in mismatch.write_plan.blockers
    assert expired.write_plan.dependency_install_contract.dependency_approval_verified is False
    assert "dependency_plan_approval_expired" in expired.write_plan.blockers
    assert missing_expiry.write_plan.dependency_install_contract.dependency_approval_verified is False
    assert "dependency_plan_approval_expiry_missing" in missing_expiry.write_plan.blockers


def test_durable_admission_preview_rejects_mismatched_plan_digest_approval(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, _ = _promoted_candidate(copied_seed_skills, runs_dir)
    approval_id = _approve_durable_review(
        candidate_id,
        runs_dir,
        copied_seed_skills,
        plan_digest="0" * 64,
    )

    preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        plan_approval_id=approval_id,
    )

    assert preview.ready_for_mutation_preview is False
    assert preview.write_plan.plan_approval_verified is False
    assert preview.write_plan.plan_approval_digest == "0" * 64
    assert "plan_digest_approval_mismatch" in preview.write_plan.blockers


def test_durable_admission_preview_rejects_expired_plan_digest_approval(
    copied_seed_skills,
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    candidate_id, _ = _promoted_candidate(copied_seed_skills, runs_dir)
    initial_preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )
    assert initial_preview.write_plan.plan_digest is not None
    approval_id = _approve_durable_review(
        candidate_id,
        runs_dir,
        copied_seed_skills,
        plan_digest=initial_preview.write_plan.plan_digest,
        expires_at="2000-01-01T00:00:00Z",
    )

    preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
        plan_approval_id=approval_id,
    )

    assert preview.ready_for_mutation_preview is False
    assert preview.write_plan.plan_approval_verified is False
    assert "plan_digest_approval_expired" in preview.write_plan.blockers


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
    invalid_policy_result = runner.invoke(
        app,
        [
            "admit-candidate",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--collision-policy",
            "replace_everything",
        ],
    )

    assert text_result.exit_code == 0
    assert "DURABLE_ADMISSION_PREVIEW" in text_result.stdout
    assert "WRITE_PLAN" in text_result.stdout
    assert "Operation: blocked" in text_result.stdout
    assert "Plan digest:" in text_result.stdout
    assert "Plan approval verified: false" in text_result.stdout
    assert "Dependency install contract:" in text_result.stdout
    assert "Dependency plan digest:" in text_result.stdout
    assert "Install supported: false" in text_result.stdout
    assert "Dependencies installed: false" in text_result.stdout
    assert "Mutation supported: false" in text_result.stdout
    assert "Resolution ledger mutated: false" in text_result.stdout
    assert "durable_review_resolution_missing" in text_result.stdout
    assert json_result.exit_code == 0
    data = json.loads(json_result.stdout)
    assert data["outcome"] == "approval_required"
    assert data["ready_for_mutation_preview"] is False
    assert data["write_plan"]["operation"] == "blocked"
    assert data["write_plan"]["plan_digest_algorithm"] == "sha256"
    assert data["write_plan"]["plan_digest"]
    assert data["write_plan"]["plan_approval_verified"] is False
    assert data["write_plan"]["collision_policy"] == "block_existing"
    assert data["write_plan"]["source_snapshot_created"] is False
    assert data["admission_plan"]["input_request"]["kind"] == "durable_admission_review"
    assert write_result.exit_code == 1
    assert "durable admission mutation is not implemented" in write_result.stdout
    assert invalid_policy_result.exit_code == 1
    assert "invalid collision policy" in invalid_policy_result.stdout


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


def _approve_durable_review(
    candidate_id: str,
    runs_dir: Path,
    skills_dir: Path,
    *,
    plan_digest: str | None = None,
    expires_at: str = "2099-01-01T00:00:00Z",
) -> str:
    admission = build_admission_plan(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=skills_dir,
    )
    if admission.input_request is None or admission.input_request.kind != "durable_admission_review":
        return _append_plan_approval_record(candidate_id, runs_dir, plan_digest, expires_at)
    try:
        resolve_input_request(
            admission.input_request.id,
            runs_dir=runs_dir,
            decision="approve_review",
            reviewer="Ada",
            notes=_approval_notes(plan_digest, expires_at),
            dry_run=False,
        )
    except InputResolutionError:
        return _append_plan_approval_record(candidate_id, runs_dir, plan_digest, expires_at)
    ledger = load_input_request_resolution_ledger(runs_dir)
    return ledger.resolutions[-1].id


def _approve_current_plan(candidate_id: str, runs_dir: Path, skills_dir: Path) -> str:
    preview = build_durable_admission_preview(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=skills_dir,
    )
    assert preview.write_plan.plan_digest is not None
    return _approve_durable_review(
        candidate_id,
        runs_dir,
        skills_dir,
        plan_digest=preview.write_plan.plan_digest,
    )


def _approval_notes(plan_digest: str | None, expires_at: str) -> str:
    notes = "Reviewed durable admission evidence for preview."
    if plan_digest:
        notes = f"{notes} plan_digest={plan_digest} expires_at={expires_at}"
    return notes


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
        reason="Test fixture approval for an exact plan digest.",
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


def _append_dependency_approval_record(
    candidate_id: str,
    runs_dir: Path,
    *,
    dependency_plan_digest: str | None,
    expires_at: str | None = "2099-01-01T00:00:00Z",
) -> str:
    request = InputRequest(
        id=f"inputreq_dependency_plan_{candidate_id}_{len(_snapshot_tree(runs_dir))}",
        kind="durable_admission_review",
        title=f"Approve dependency evidence for {candidate_id}",
        reason="Test fixture approval for exact dependency plan digest.",
        blocked_scope="dependency evidence review only",
        requested_decision="Approve the exact dependency plan digest or defer.",
        options=["approve_review", "defer"],
        recommended_option="approve_review",
        related_candidate_id=candidate_id,
    )
    notes = "Reviewed no-write dependency evidence."
    if dependency_plan_digest:
        notes = f"{notes} dependency_plan_digest={dependency_plan_digest}"
        if expires_at is not None:
            notes = f"{notes} expires_at={expires_at}"
    report = InputRequestResolutionDryRun(
        dry_run=True,
        input_request_id=request.id,
        decision="approve_review",
        resolution_class="approve",
        proposed_status="resolved",
        reviewer="Ada",
        notes=notes,
        request=request,
        remaining_blocked_scope="dependency install remains unsupported",
        next_steps=["Rerun admit-candidate --dry-run."],
    )
    record = append_input_request_resolution(report, runs_dir)
    return record.id


def _enable_network_permission(source_path: Path) -> None:
    text = source_path.read_text(encoding="utf-8")
    updated = text.replace("network: false", "network: true", 1)
    assert updated != text
    source_path.write_text(updated, encoding="utf-8")


def _append_dependency_declaration(source_path: Path, *, exact: bool = False) -> None:
    text = source_path.read_text(encoding="utf-8")
    marker = "\n---\n\n#"
    assert marker in text
    realization = ""
    if exact:
        realization = (
            "dependency_realization:\n"
            "  - name: example-package\n"
            "    version: 1.0.0\n"
            "    sha256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef\n"
        )
    updated = text.replace(
        marker,
        "\ndependencies:\n  - example-package==1.0.0\n"
        f"{realization}"
        "---\n\n#",
        1,
    )
    source_path.write_text(updated, encoding="utf-8")


def _append_requirement_package_declarations(source_path: Path) -> None:
    text = source_path.read_text(encoding="utf-8")
    marker = "\n---\n\n#"
    assert marker in text
    updated = text.replace(
        marker,
        "\nrequirements:\n"
        "  - requirement-one>=2.0.0\n"
        "packages:\n"
        "  package-two: 3.0.0\n"
        "dependency_lock:\n"
        "  dependencies:\n"
        "    locked-package:\n"
        "      version: 4.0.0\n"
        "      sha256: abcdef\n"
        "---\n\n#",
        1,
    )
    source_path.write_text(updated, encoding="utf-8")


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
