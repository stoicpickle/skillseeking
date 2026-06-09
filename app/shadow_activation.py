from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

from app.admission_plan import AdmissionPlanError
from app.durable_admission import build_durable_admission_preview
from app.evidence_checkpoint import EvidenceCheckpointError, build_evidence_checkpoint_report
from app.input_resolution_ledger import (
    InputResolutionLedgerError,
    load_input_request_resolution_ledger,
)
from app.models import (
    ShadowActivationAcceptanceReport,
    ShadowActivationPlanReport,
    ShadowManagedWriteReport,
    ShadowRollbackPlanReport,
    ShadowWriteGateReport,
)
from app.skill_receipt import SkillReceiptError, build_skill_receipt_report


class ShadowActivationPlanError(RuntimeError):
    pass


PROFILE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


def build_shadow_activation_plan(
    candidate_id: str,
    *,
    runs_dir: Path,
    skills_dir: Path,
    managed_prefix: Path | None = None,
    profile_name: str = "default",
    collision_policy: str = "block_existing",
    permission_approval_id: str | None = None,
    plan_approval_id: str | None = None,
) -> ShadowActivationPlanReport:
    if not PROFILE_NAME_RE.match(profile_name):
        raise ShadowActivationPlanError(
            "profile name must start with a letter or number and contain only letters, numbers, dots, underscores, or hyphens"
        )
    prefix = managed_prefix or (runs_dir / "managed_shadow")
    try:
        preview = build_durable_admission_preview(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            dry_run=True,
            collision_policy=collision_policy,
            permission_approval_id=permission_approval_id,
            plan_approval_id=plan_approval_id,
            prepare_write_evidence=False,
        )
    except AdmissionPlanError as exc:
        raise ShadowActivationPlanError(str(exc)) from exc

    skill_name = str(preview.admission_plan.candidate.get("skill_name") or "")
    source_sha256 = preview.source_sha256
    store_dir = _store_dir(prefix, source_sha256, skill_name)
    store_skill_path = store_dir / "SKILL.md" if store_dir is not None else None
    profile_dir = prefix / "profiles" / profile_name
    activation_pointer = profile_dir / "current"
    pointer_generation = _current_generation(_activation_pointer_target(activation_pointer))
    previous_generation = (
        pointer_generation
        if pointer_generation is not None
        else _latest_generation(profile_dir)
    )
    planned_generation = (previous_generation or 0) + 1 if source_sha256 else None
    generation_dir = (
        profile_dir / "generations" / str(planned_generation)
        if planned_generation is not None
        else None
    )
    generation_skill_path = (
        generation_dir / "skills" / skill_name / "SKILL.md"
        if generation_dir is not None and skill_name
        else None
    )
    rollback_target = (
        str(profile_dir / "generations" / str(previous_generation))
        if previous_generation is not None
        else None
    )
    blockers = list(preview.write_plan.blockers)
    if not source_sha256:
        blockers.append("source_sha256_missing")
    if not skill_name:
        blockers.append("skill_name_missing")
    blockers = _unique(blockers)
    ready = not blockers
    shadow_digest = _shadow_plan_digest(
        candidate_id=candidate_id,
        source_sha256=source_sha256,
        durable_plan_digest=preview.write_plan.plan_digest,
        managed_prefix=prefix,
        store_skill_path=store_skill_path,
        profile_name=profile_name,
        activation_pointer=activation_pointer,
        planned_generation=planned_generation,
        generation_skill_path=generation_skill_path,
        previous_generation=previous_generation,
        rollback_target=rollback_target,
    )

    return ShadowActivationPlanReport(
        candidate_id=candidate_id,
        skill_name=skill_name or None,
        outcome="ready_for_shadow_activation_preview" if ready else "blocked",
        ready_for_shadow_activation_preview=ready,
        managed_prefix=str(prefix),
        managed_prefix_exists=prefix.exists(),
        store_dir=str(store_dir) if store_dir is not None else None,
        store_skill_path=str(store_skill_path) if store_skill_path is not None else None,
        profile_name=profile_name,
        profile_dir=str(profile_dir),
        activation_pointer=str(activation_pointer),
        planned_generation=planned_generation,
        generation_dir=str(generation_dir) if generation_dir is not None else None,
        generation_skill_path=(
            str(generation_skill_path) if generation_skill_path is not None else None
        ),
        previous_generation=previous_generation,
        rollback_target=rollback_target,
        source_sha256=source_sha256,
        durable_plan_digest=preview.write_plan.plan_digest,
        shadow_plan_digest=shadow_digest,
        durable_admission_preview=preview,
        blockers=blockers,
        warnings=list(preview.warnings),
        next_steps=_next_steps(ready, previous_generation),
    )


def build_shadow_rollback_plan(
    candidate_id: str,
    *,
    runs_dir: Path,
    skills_dir: Path,
    managed_prefix: Path | None = None,
    profile_name: str = "default",
    collision_policy: str = "block_existing",
    permission_approval_id: str | None = None,
    plan_approval_id: str | None = None,
) -> ShadowRollbackPlanReport:
    activation_plan = build_shadow_activation_plan(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=skills_dir,
        managed_prefix=managed_prefix,
        profile_name=profile_name,
        collision_policy=collision_policy,
        permission_approval_id=permission_approval_id,
        plan_approval_id=plan_approval_id,
    )
    activation_pointer = (
        Path(activation_plan.activation_pointer)
        if activation_plan.activation_pointer
        else None
    )
    rollback_target = (
        Path(activation_plan.rollback_target)
        if activation_plan.rollback_target
        else None
    )
    pointer_exists = bool(activation_pointer and activation_pointer.exists())
    pointer_target = _activation_pointer_target(activation_pointer)
    pointer_target_path = _activation_pointer_target_path(pointer_target, activation_pointer)
    rollback_target_exists = bool(rollback_target and rollback_target.exists())
    blockers = list(activation_plan.blockers)
    if activation_plan.previous_generation is None or activation_plan.rollback_target is None:
        blockers.append("rollback_generation_missing")
    elif not rollback_target_exists:
        blockers.append("rollback_target_missing")
    elif not pointer_exists:
        blockers.append("activation_pointer_missing")
    elif not _same_path(pointer_target_path, rollback_target):
        blockers.append("activation_pointer_target_mismatch")
    blockers = _unique(blockers)
    verifiable = not blockers
    digest = _rollback_plan_digest(
        candidate_id=candidate_id,
        managed_prefix=Path(activation_plan.managed_prefix),
        profile_name=profile_name,
        activation_pointer=activation_pointer,
        activation_pointer_target=pointer_target,
        current_generation=_current_generation(pointer_target),
        planned_generation=activation_plan.planned_generation,
        rollback_generation=activation_plan.previous_generation,
        rollback_target=rollback_target,
        shadow_plan_digest=activation_plan.shadow_plan_digest,
    )
    return ShadowRollbackPlanReport(
        candidate_id=candidate_id,
        skill_name=activation_plan.skill_name,
        outcome="rollback_verifiable" if verifiable else "blocked",
        rollback_verifiable=verifiable,
        managed_prefix=activation_plan.managed_prefix,
        profile_name=profile_name,
        profile_dir=activation_plan.profile_dir,
        activation_pointer=activation_plan.activation_pointer,
        activation_pointer_exists=pointer_exists,
        activation_pointer_target=pointer_target,
        current_generation=_current_generation(pointer_target),
        planned_generation=activation_plan.planned_generation,
        rollback_generation=activation_plan.previous_generation,
        rollback_target=activation_plan.rollback_target,
        rollback_target_exists=rollback_target_exists,
        shadow_plan_digest=activation_plan.shadow_plan_digest,
        rollback_plan_digest=digest,
        shadow_activation_plan=activation_plan,
        blockers=blockers,
        warnings=list(activation_plan.warnings),
        next_steps=_rollback_next_steps(verifiable, pointer_exists),
    )


def build_shadow_activation_acceptance_report(
    candidate_id: str,
    *,
    runs_dir: Path,
    skills_dir: Path,
    managed_prefix: Path | None = None,
    acceptance_prefix: Path | None = None,
    profile_name: str = "default",
    collision_policy: str = "block_existing",
    permission_approval_id: str | None = None,
    plan_approval_id: str | None = None,
    prepare_acceptance_evidence: bool = False,
) -> ShadowActivationAcceptanceReport:
    activation_plan = build_shadow_activation_plan(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=skills_dir,
        managed_prefix=managed_prefix,
        profile_name=profile_name,
        collision_policy=collision_policy,
        permission_approval_id=permission_approval_id,
        plan_approval_id=plan_approval_id,
    )
    planned_prefix = Path(activation_plan.managed_prefix)
    prefix = acceptance_prefix or _default_acceptance_prefix(
        runs_dir,
        candidate_id,
        activation_plan.shadow_plan_digest,
    )
    source_path = (
        Path(activation_plan.durable_admission_preview.source_skill_path)
        if activation_plan.durable_admission_preview.source_skill_path
        else None
    )
    store_skill_path = _map_planned_path(
        activation_plan.store_skill_path,
        planned_prefix=planned_prefix,
        acceptance_prefix=prefix,
    )
    generation_skill_path = _map_planned_path(
        activation_plan.generation_skill_path,
        planned_prefix=planned_prefix,
        acceptance_prefix=prefix,
    )
    activation_pointer = _map_planned_path(
        activation_plan.activation_pointer,
        planned_prefix=planned_prefix,
        acceptance_prefix=prefix,
    )
    rollback_target = _map_planned_path(
        activation_plan.rollback_target,
        planned_prefix=planned_prefix,
        acceptance_prefix=prefix,
    )
    blockers = list(activation_plan.blockers)
    warnings = list(activation_plan.warnings)
    if not _is_within(prefix, runs_dir):
        blockers.append("acceptance_prefix_outside_runs_dir")
    if activation_plan.previous_generation is None or rollback_target is None:
        blockers.append("rollback_generation_missing")
    if source_path is None:
        blockers.append("source_skill_path_missing")
    elif not source_path.exists():
        blockers.append("source_skill_path_missing")
    if store_skill_path is None:
        blockers.append("acceptance_store_path_missing")
    if generation_skill_path is None:
        blockers.append("acceptance_generation_path_missing")
    if activation_pointer is None:
        blockers.append("acceptance_activation_pointer_missing")
    blockers = _unique(blockers)

    source_bytes: bytes | None = None
    if source_path is not None and source_path.exists():
        source_bytes = source_path.read_bytes()
        actual_sha = hashlib.sha256(source_bytes).hexdigest()
        if activation_plan.source_sha256 and actual_sha != activation_plan.source_sha256:
            blockers.append("source_sha256_mismatch")

    activation_verified = False
    rollback_verified = False
    acceptance_prepared = False
    pointer_after_activation: str | None = None
    pointer_after_rollback: str | None = None
    pointer_target_before: str | None = None
    interrupted_activation_recovered = False
    acceptance_conflict_detected = False

    if prepare_acceptance_evidence and not blockers:
        if (
            source_bytes is None
            or store_skill_path is None
            or generation_skill_path is None
            or activation_pointer is None
            or rollback_target is None
        ):
            raise ShadowActivationPlanError(
                "acceptance required evidence missing after preflight"
            )
        source_bytes = cast(bytes, source_bytes)
        store_skill_path = cast(Path, store_skill_path)
        generation_skill_path = cast(Path, generation_skill_path)
        activation_pointer = cast(Path, activation_pointer)
        rollback_target = cast(Path, rollback_target)
        generation_dir = generation_skill_path.parent.parent.parent
        write_blockers: list[str] = []
        rollback_marker = rollback_target / ".acceptance_rollback_target"
        rollback_marker_data = b"shadow activation acceptance rollback target\n"
        _collect_acceptance_file_conflicts(
            [
                (store_skill_path, source_bytes),
                (generation_skill_path, source_bytes),
                (rollback_marker, rollback_marker_data),
            ],
            write_blockers,
        )
        pointer_target_before = _activation_pointer_target(activation_pointer)
        pointer_target_path_before = _activation_pointer_target_path(
            pointer_target_before,
            activation_pointer,
        )
        if (
            pointer_target_path_before is not None
            and not _same_path(pointer_target_path_before, rollback_target)
            and not _same_path(pointer_target_path_before, generation_dir)
        ):
            write_blockers.append("acceptance_pointer_precondition_mismatch")
        if write_blockers:
            blockers.extend(write_blockers)
            acceptance_conflict_detected = True
        else:
            interrupted_activation_recovered = _same_path(
                pointer_target_path_before,
                generation_dir,
            )
            _write_bytes(store_skill_path, source_bytes)
            _write_bytes(generation_skill_path, source_bytes)
            _write_bytes(rollback_marker, rollback_marker_data)
            _write_pointer(activation_pointer, rollback_target)
            _write_pointer(activation_pointer, generation_dir)
            pointer_after_activation = _activation_pointer_target(activation_pointer)
            activation_verified = _same_path(
                _activation_pointer_target_path(pointer_after_activation, activation_pointer),
                generation_dir,
            )
            _write_pointer(activation_pointer, rollback_target)
            pointer_after_rollback = _activation_pointer_target(activation_pointer)
            rollback_verified = _same_path(
                _activation_pointer_target_path(pointer_after_rollback, activation_pointer),
                rollback_target,
            )
            acceptance_prepared = activation_verified and rollback_verified
            if not activation_verified:
                blockers.append("acceptance_activation_verification_failed")
            if not rollback_verified:
                blockers.append("acceptance_rollback_verification_failed")
    elif prepare_acceptance_evidence and blockers:
        warnings.append("acceptance evidence was not prepared because blockers are present")

    blockers = _unique(blockers)
    accepted = prepare_acceptance_evidence and acceptance_prepared and not blockers
    planned = not prepare_acceptance_evidence and not blockers
    return ShadowActivationAcceptanceReport(
        candidate_id=candidate_id,
        skill_name=activation_plan.skill_name,
        outcome="accepted" if accepted else "planned" if planned else "blocked",
        acceptance_prepared=acceptance_prepared,
        activation_verified=activation_verified,
        rollback_verified=rollback_verified,
        planned_managed_prefix=activation_plan.managed_prefix,
        acceptance_prefix=str(prefix),
        acceptance_prefix_exists=prefix.exists(),
        profile_name=profile_name,
        source_skill_path=str(source_path) if source_path is not None else None,
        source_sha256=activation_plan.source_sha256,
        acceptance_store_skill_path=(
            str(store_skill_path) if store_skill_path is not None else None
        ),
        acceptance_generation_skill_path=(
            str(generation_skill_path) if generation_skill_path is not None else None
        ),
        acceptance_activation_pointer=(
            str(activation_pointer) if activation_pointer is not None else None
        ),
        previous_generation=activation_plan.previous_generation,
        planned_generation=activation_plan.planned_generation,
        acceptance_rollback_target=(
            str(rollback_target) if rollback_target is not None else None
        ),
        activation_pointer_before=pointer_target_before,
        activation_pointer_after_activation=pointer_after_activation,
        activation_pointer_after_rollback=pointer_after_rollback,
        interrupted_activation_recovered=interrupted_activation_recovered,
        acceptance_conflict_detected=acceptance_conflict_detected,
        shadow_plan_digest=activation_plan.shadow_plan_digest,
        acceptance_plan_digest=_acceptance_plan_digest(
            candidate_id=candidate_id,
            planned_managed_prefix=planned_prefix,
            acceptance_prefix=prefix,
            source_sha256=activation_plan.source_sha256,
            store_skill_path=store_skill_path,
            generation_skill_path=generation_skill_path,
            activation_pointer=activation_pointer,
            rollback_target=rollback_target,
            shadow_plan_digest=activation_plan.shadow_plan_digest,
        ),
        shadow_activation_plan=activation_plan,
        blockers=blockers,
        warnings=warnings,
        next_steps=_acceptance_next_steps(accepted, planned),
        acceptance_prefix_mutated=acceptance_prepared,
        mutation_supported=prepare_acceptance_evidence,
    )


def build_shadow_write_gate_report(
    candidate_id: str,
    *,
    runs_dir: Path,
    skills_dir: Path,
    managed_prefix: Path | None = None,
    acceptance_prefix: Path | None = None,
    profile_name: str = "default",
    collision_policy: str = "block_existing",
    permission_approval_id: str | None = None,
    plan_approval_id: str | None = None,
    acceptance_plan_digest: str | None = None,
) -> ShadowWriteGateReport:
    activation_plan = build_shadow_activation_plan(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=skills_dir,
        managed_prefix=managed_prefix,
        profile_name=profile_name,
        collision_policy=collision_policy,
        permission_approval_id=permission_approval_id,
        plan_approval_id=plan_approval_id,
    )
    rollback_plan = build_shadow_rollback_plan(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=skills_dir,
        managed_prefix=managed_prefix,
        profile_name=profile_name,
        collision_policy=collision_policy,
        permission_approval_id=permission_approval_id,
        plan_approval_id=plan_approval_id,
    )
    acceptance = build_shadow_activation_acceptance_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=skills_dir,
        managed_prefix=managed_prefix,
        acceptance_prefix=acceptance_prefix,
        profile_name=profile_name,
        collision_policy=collision_policy,
        permission_approval_id=permission_approval_id,
        plan_approval_id=plan_approval_id,
        prepare_acceptance_evidence=False,
    )

    blockers = list(activation_plan.blockers)
    blockers.extend(rollback_plan.blockers)
    blockers.extend(acceptance.blockers)
    warnings = list(activation_plan.warnings)
    warnings.extend(rollback_plan.warnings)
    warnings.extend(acceptance.warnings)

    source_path = Path(acceptance.source_skill_path) if acceptance.source_skill_path else None
    source_hash_verified = _path_sha256_matches(source_path, activation_plan.source_sha256)
    if not source_hash_verified:
        blockers.append("source_hash_not_verified")

    store_path = (
        Path(acceptance.acceptance_store_skill_path)
        if acceptance.acceptance_store_skill_path
        else None
    )
    store_verified = _path_sha256_matches(store_path, activation_plan.source_sha256)
    if not store_verified:
        blockers.append("acceptance_store_missing_or_hash_mismatch")

    generation_path = (
        Path(acceptance.acceptance_generation_skill_path)
        if acceptance.acceptance_generation_skill_path
        else None
    )
    generation_verified = _path_sha256_matches(
        generation_path,
        activation_plan.source_sha256,
    )
    if not generation_verified:
        blockers.append("acceptance_generation_missing_or_hash_mismatch")

    pointer_path = (
        Path(acceptance.acceptance_activation_pointer)
        if acceptance.acceptance_activation_pointer
        else None
    )
    rollback_target = (
        Path(acceptance.acceptance_rollback_target)
        if acceptance.acceptance_rollback_target
        else None
    )
    pointer_target = _activation_pointer_target(pointer_path)
    pointer_target_path = _activation_pointer_target_path(pointer_target, pointer_path)
    pointer_restored = _same_path(pointer_target_path, rollback_target)
    if not pointer_restored:
        blockers.append("acceptance_pointer_not_restored_to_rollback")

    marker_path = (
        rollback_target / ".acceptance_rollback_target"
        if rollback_target is not None
        else None
    )
    rollback_marker_verified = (
        marker_path is not None
        and marker_path.exists()
        and marker_path.read_bytes() == b"shadow activation acceptance rollback target\n"
    )
    if not rollback_marker_verified:
        blockers.append("acceptance_rollback_marker_missing")

    digest_verified = False
    if not acceptance.acceptance_plan_digest:
        blockers.append("acceptance_plan_digest_missing")
    elif acceptance_plan_digest is None:
        blockers.append("acceptance_plan_digest_expected_missing")
    else:
        digest_verified = acceptance.acceptance_plan_digest == acceptance_plan_digest
        if not digest_verified:
            blockers.append("acceptance_plan_digest_mismatch")

    blockers = _unique(blockers)
    warnings = _unique(warnings)
    ready = (
        not blockers
        and activation_plan.ready_for_shadow_activation_preview
        and rollback_plan.rollback_verifiable
        and source_hash_verified
        and store_verified
        and generation_verified
        and pointer_restored
        and rollback_marker_verified
        and digest_verified
    )

    return ShadowWriteGateReport(
        candidate_id=candidate_id,
        skill_name=activation_plan.skill_name,
        outcome="ready_for_human_managed_prefix_write" if ready else "blocked",
        ready_for_human_managed_prefix_write=ready,
        managed_prefix=activation_plan.managed_prefix,
        acceptance_prefix=acceptance.acceptance_prefix,
        profile_name=profile_name,
        source_skill_path=acceptance.source_skill_path,
        source_sha256=activation_plan.source_sha256,
        source_hash_verified=source_hash_verified,
        acceptance_store_skill_path=acceptance.acceptance_store_skill_path,
        acceptance_store_verified=store_verified,
        acceptance_generation_skill_path=acceptance.acceptance_generation_skill_path,
        acceptance_generation_verified=generation_verified,
        acceptance_activation_pointer=acceptance.acceptance_activation_pointer,
        acceptance_pointer_restored=pointer_restored,
        acceptance_pointer_target=pointer_target,
        acceptance_rollback_target=acceptance.acceptance_rollback_target,
        acceptance_rollback_marker_verified=rollback_marker_verified,
        durable_plan_digest=activation_plan.durable_plan_digest,
        shadow_plan_digest=activation_plan.shadow_plan_digest,
        rollback_plan_digest=rollback_plan.rollback_plan_digest,
        acceptance_plan_digest=acceptance.acceptance_plan_digest,
        expected_acceptance_plan_digest=acceptance_plan_digest,
        acceptance_plan_digest_verified=digest_verified,
        shadow_activation_plan=activation_plan,
        shadow_rollback_plan=rollback_plan,
        shadow_activation_acceptance=acceptance,
        blockers=blockers,
        warnings=warnings,
        next_steps=_write_gate_next_steps(ready),
    )


def build_shadow_managed_write_report(
    candidate_id: str,
    *,
    runs_dir: Path,
    skills_dir: Path,
    dry_run: bool = True,
    managed_prefix: Path | None = None,
    acceptance_prefix: Path | None = None,
    profile_name: str = "default",
    collision_policy: str = "block_existing",
    permission_approval_id: str | None = None,
    plan_approval_id: str | None = None,
    expected_source_sha256: str | None = None,
    expected_durable_plan_digest: str | None = None,
    expected_shadow_plan_digest: str | None = None,
    expected_rollback_plan_digest: str | None = None,
    expected_acceptance_plan_digest: str | None = None,
    expected_managed_write_plan_digest: str | None = None,
    expected_checkpoint_hash: str | None = None,
    write_approval_id: str | None = None,
) -> ShadowManagedWriteReport:
    try:
        receipt = build_skill_receipt_report(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            collision_policy=collision_policy,
            permission_approval_id=permission_approval_id,
            plan_approval_id=plan_approval_id,
        )
        checkpoint = build_evidence_checkpoint_report(
            runs_dir=runs_dir,
            dry_run=True,
            verify=True,
        )
        write_gate = build_shadow_write_gate_report(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            managed_prefix=managed_prefix,
            acceptance_prefix=acceptance_prefix,
            profile_name=profile_name,
            collision_policy=collision_policy,
            permission_approval_id=permission_approval_id,
            plan_approval_id=plan_approval_id,
            acceptance_plan_digest=expected_acceptance_plan_digest or None,
        )
    except (SkillReceiptError, EvidenceCheckpointError, AdmissionPlanError) as exc:
        raise ShadowActivationPlanError(str(exc)) from exc

    blockers: list[str] = []
    warnings: list[str] = []
    receipt_blockers, reversibility_accepted = _managed_write_receipt_blockers(receipt)
    blockers.extend(receipt_blockers)
    if checkpoint.blockers:
        blockers.extend(checkpoint.blockers)
    warnings.extend(receipt.durable_admission_preview.warnings)
    warnings.extend(checkpoint.warnings)
    warnings.extend(write_gate.warnings)

    source_sha256 = write_gate.source_sha256
    durable_plan_digest = write_gate.durable_plan_digest
    shadow_plan_digest = write_gate.shadow_plan_digest
    rollback_plan_digest = write_gate.rollback_plan_digest
    acceptance_plan_digest = write_gate.acceptance_plan_digest
    managed_prefix_path = Path(write_gate.managed_prefix)
    store_skill_path = (
        Path(write_gate.shadow_activation_plan.store_skill_path)
        if write_gate.shadow_activation_plan.store_skill_path
        else None
    )
    generation_skill_path = (
        Path(write_gate.shadow_activation_plan.generation_skill_path)
        if write_gate.shadow_activation_plan.generation_skill_path
        else None
    )
    activation_pointer = (
        Path(write_gate.shadow_activation_plan.activation_pointer)
        if write_gate.shadow_activation_plan.activation_pointer
        else None
    )
    rollback_target = (
        Path(write_gate.shadow_rollback_plan.rollback_target)
        if write_gate.shadow_rollback_plan.rollback_target
        else None
    )
    managed_write_plan_digest = _managed_write_plan_digest(
        candidate_id=candidate_id,
        source_sha256=source_sha256,
        durable_plan_digest=durable_plan_digest,
        shadow_plan_digest=shadow_plan_digest,
        rollback_plan_digest=rollback_plan_digest,
        acceptance_plan_digest=acceptance_plan_digest,
        managed_prefix=managed_prefix_path,
        profile_name=write_gate.profile_name,
        store_skill_path=store_skill_path,
        generation_skill_path=generation_skill_path,
        activation_pointer=activation_pointer,
        rollback_target=rollback_target,
    )
    receipt_digest = expected_managed_write_plan_digest or managed_write_plan_digest
    write_receipt_path = _write_receipt_path(
        managed_prefix_path,
        write_gate.profile_name,
        receipt_digest,
    )
    existing_write_receipt = _read_write_receipt(write_receipt_path)
    receipt_already_applied = existing_write_receipt is not None
    if receipt_already_applied:
        receipt_blockers_for_state = _write_receipt_conflict_blockers(
            existing_write_receipt,
            candidate_id=candidate_id,
            managed_write_plan_digest=receipt_digest,
            managed_prefix=managed_prefix_path,
            profile_name=write_gate.profile_name,
            expected_source_sha256=expected_source_sha256,
            expected_durable_plan_digest=expected_durable_plan_digest,
            expected_shadow_plan_digest=expected_shadow_plan_digest,
            expected_rollback_plan_digest=expected_rollback_plan_digest,
            expected_acceptance_plan_digest=expected_acceptance_plan_digest,
        )
        blockers.extend(receipt_blockers_for_state)
        if not receipt_blockers_for_state:
            source_sha256 = str(existing_write_receipt["source_sha256"])
            durable_plan_digest = str(existing_write_receipt["durable_plan_digest"])
            shadow_plan_digest = str(existing_write_receipt["shadow_plan_digest"])
            rollback_plan_digest = str(existing_write_receipt["rollback_plan_digest"])
            acceptance_plan_digest = str(existing_write_receipt["acceptance_plan_digest"])
            managed_write_plan_digest = str(existing_write_receipt["managed_write_plan_digest"])
            store_skill_path = Path(str(existing_write_receipt["store_skill_path"]))
            generation_skill_path = Path(str(existing_write_receipt["generation_skill_path"]))
            activation_pointer = Path(str(existing_write_receipt["activation_pointer"]))
            rollback_target = Path(str(existing_write_receipt["rollback_target"]))
    missing_receipt_after_pointer_switch = False
    if not receipt_already_applied and expected_managed_write_plan_digest:
        missing_receipt_after_pointer_switch = _missing_receipt_after_pointer_switch(
            activation_pointer=activation_pointer,
            source_sha256=source_sha256,
            store_skill_path=store_skill_path,
            skill_name=write_gate.skill_name,
        )
        if missing_receipt_after_pointer_switch:
            blockers.append("managed_write_receipt_missing_after_pointer_switch")
    planned_write_path_blockers = _managed_prefix_write_blockers(
        managed_prefix_path,
        skills_dir,
        runs_dir,
        [
            store_skill_path,
            generation_skill_path,
            activation_pointer,
            rollback_target,
            write_receipt_path,
        ],
    )
    blockers.extend(planned_write_path_blockers)
    if not receipt_already_applied and not missing_receipt_after_pointer_switch and write_gate.blockers:
        blockers.extend(write_gate.blockers)

    require_exact_values = not dry_run
    source_expected_ok = _expected_matches(
        actual=source_sha256,
        expected=expected_source_sha256,
        mismatch_blocker="expected_source_sha256_mismatch",
        missing_blocker="expected_source_sha256_missing",
        required=require_exact_values,
        blockers=blockers,
    )
    durable_expected_ok = _expected_matches(
        actual=durable_plan_digest,
        expected=expected_durable_plan_digest,
        mismatch_blocker="expected_durable_plan_digest_mismatch",
        missing_blocker="expected_durable_plan_digest_missing",
        required=require_exact_values,
        blockers=blockers,
    )
    shadow_expected_ok = _expected_matches(
        actual=shadow_plan_digest,
        expected=expected_shadow_plan_digest,
        mismatch_blocker="expected_shadow_plan_digest_mismatch",
        missing_blocker="expected_shadow_plan_digest_missing",
        required=require_exact_values,
        blockers=blockers,
    )
    rollback_expected_ok = _expected_matches(
        actual=rollback_plan_digest,
        expected=expected_rollback_plan_digest,
        mismatch_blocker="expected_rollback_plan_digest_mismatch",
        missing_blocker="expected_rollback_plan_digest_missing",
        required=require_exact_values,
        blockers=blockers,
    )
    acceptance_expected_ok = _expected_matches(
        actual=acceptance_plan_digest,
        expected=expected_acceptance_plan_digest,
        mismatch_blocker="expected_acceptance_plan_digest_mismatch",
        missing_blocker="expected_acceptance_plan_digest_missing",
        required=require_exact_values,
        blockers=blockers,
    )
    managed_write_expected_ok = _expected_matches(
        actual=managed_write_plan_digest,
        expected=expected_managed_write_plan_digest,
        mismatch_blocker="expected_managed_write_plan_digest_mismatch",
        missing_blocker="expected_managed_write_plan_digest_missing",
        required=require_exact_values,
        blockers=blockers,
    )
    checkpoint_hash_ok = _expected_matches(
        actual=checkpoint.latest_checkpoint_hash,
        expected=expected_checkpoint_hash,
        mismatch_blocker="expected_checkpoint_hash_mismatch",
        missing_blocker="expected_checkpoint_hash_missing",
        required=require_exact_values,
        blockers=blockers,
    )
    exact_expected_values_verified = all(
        [
            source_expected_ok,
            durable_expected_ok,
            shadow_expected_ok,
            rollback_expected_ok,
            acceptance_expected_ok,
            managed_write_expected_ok,
            checkpoint_hash_ok,
        ]
    )
    write_approval = _find_write_approval_resolution(
        managed_write_plan_digest=managed_write_plan_digest,
        candidate_id=candidate_id,
        runs_dir=runs_dir,
        write_approval_id=write_approval_id,
    )
    write_approval_present = bool(write_approval_id)
    if write_approval.blocker and (write_approval_present or not dry_run):
        blockers.append(write_approval.blocker)

    blockers = _unique(blockers)
    warnings = _unique(warnings)
    receipt_acceptable = not receipt_blockers
    checkpoint_verified = checkpoint.outcome == "verified" and not checkpoint.blockers
    gate_ready = write_gate.ready_for_human_managed_prefix_write
    write_approval_verified = write_approval.verified
    already_applied_verified = False
    store_verified = False
    generation_verified = False
    activation_pointer_updated = False
    activation_pointer_verified = False
    rollback_target_verified = False
    interrupted_activation_recovered = False
    managed_prefix_mutated = False
    profile_mutated = False
    pointer_target = _activation_pointer_target(activation_pointer)

    if receipt_already_applied and not blockers:
        already_applied_verified = _verify_managed_write_applied_state(
            store_skill_path=store_skill_path,
            generation_skill_path=generation_skill_path,
            activation_pointer=activation_pointer,
            rollback_target=rollback_target,
            source_sha256=source_sha256,
        )
        store_verified = _path_sha256_matches(store_skill_path, source_sha256)
        generation_verified = _path_sha256_matches(generation_skill_path, source_sha256)
        pointer_target = _activation_pointer_target(activation_pointer)
        activation_pointer_verified = _same_path(
            _activation_pointer_target_path(pointer_target, activation_pointer),
            generation_skill_path.parent.parent.parent if generation_skill_path else None,
        )
        rollback_target_verified = bool(rollback_target and rollback_target.exists())
        if not already_applied_verified:
            blockers.append("managed_write_receipt_state_mismatch")
            blockers = _unique(blockers)

    gate_ready_for_mutation = (
        not blockers
        and receipt_acceptable
        and checkpoint_verified
        and (gate_ready or already_applied_verified)
        and write_approval_verified
        and exact_expected_values_verified
    )
    if not dry_run and gate_ready_for_mutation and not already_applied_verified:
        mutation_state = _apply_shadow_managed_write(
            candidate_id=candidate_id,
            skill_name=write_gate.skill_name,
            managed_prefix=managed_prefix_path,
            profile_name=write_gate.profile_name,
            source_skill_path=Path(write_gate.source_skill_path) if write_gate.source_skill_path else None,
            source_sha256=source_sha256,
            store_skill_path=store_skill_path,
            generation_skill_path=generation_skill_path,
            activation_pointer=activation_pointer,
            rollback_target=rollback_target,
            managed_write_plan_digest=managed_write_plan_digest,
            durable_plan_digest=durable_plan_digest,
            shadow_plan_digest=shadow_plan_digest,
            rollback_plan_digest=rollback_plan_digest,
            acceptance_plan_digest=acceptance_plan_digest,
            write_approval_id=write_approval.resolution_id,
            checkpoint_hash=checkpoint.latest_checkpoint_hash,
            write_receipt_path=write_receipt_path,
            skills_dir=skills_dir,
            runs_dir=runs_dir,
        )
        blockers.extend(mutation_state["blockers"])
        blockers = _unique(blockers)
        store_verified = bool(mutation_state["store_verified"])
        generation_verified = bool(mutation_state["generation_verified"])
        activation_pointer_updated = bool(mutation_state["activation_pointer_updated"])
        activation_pointer_verified = bool(mutation_state["activation_pointer_verified"])
        rollback_target_verified = bool(mutation_state["rollback_target_verified"])
        interrupted_activation_recovered = bool(mutation_state["interrupted_activation_recovered"])
        managed_prefix_mutated = bool(mutation_state["managed_prefix_mutated"])
        profile_mutated = bool(mutation_state["profile_mutated"])
        pointer_target = str(mutation_state["activation_pointer_target"] or "") or None

    ready = gate_ready_for_mutation
    if blockers:
        outcome = "blocked"
    elif already_applied_verified:
        outcome = "already_applied"
    elif not dry_run and managed_prefix_mutated:
        outcome = "managed_prefix_write_applied"
    elif not write_approval_verified:
        outcome = "approval_required"
    else:
        outcome = "ready_for_managed_prefix_write"

    return ShadowManagedWriteReport(
        candidate_id=candidate_id,
        skill_name=write_gate.skill_name,
        outcome=outcome,
        ready_for_managed_prefix_write=ready,
        dry_run=dry_run,
        mutation_supported=not dry_run,
        managed_prefix=write_gate.managed_prefix,
        acceptance_prefix=write_gate.acceptance_prefix,
        profile_name=write_gate.profile_name,
        source_skill_path=write_gate.source_skill_path,
        source_sha256=source_sha256,
        source_hash_verified=write_gate.source_hash_verified,
        store_skill_path=str(store_skill_path) if store_skill_path is not None else None,
        generation_skill_path=(
            str(generation_skill_path) if generation_skill_path is not None else None
        ),
        activation_pointer=str(activation_pointer) if activation_pointer is not None else None,
        rollback_target=str(rollback_target) if rollback_target is not None else None,
        durable_plan_digest=durable_plan_digest,
        shadow_plan_digest=shadow_plan_digest,
        rollback_plan_digest=rollback_plan_digest,
        acceptance_plan_digest=acceptance_plan_digest,
        managed_write_plan_digest=managed_write_plan_digest,
        expected_source_sha256=expected_source_sha256 or None,
        expected_durable_plan_digest=expected_durable_plan_digest or None,
        expected_shadow_plan_digest=expected_shadow_plan_digest or None,
        expected_rollback_plan_digest=expected_rollback_plan_digest or None,
        expected_acceptance_plan_digest=expected_acceptance_plan_digest or None,
        expected_managed_write_plan_digest=expected_managed_write_plan_digest or None,
        expected_checkpoint_hash=expected_checkpoint_hash or None,
        expected_source_sha256_verified=source_expected_ok,
        durable_plan_digest_verified=durable_expected_ok,
        shadow_plan_digest_verified=shadow_expected_ok,
        rollback_plan_digest_verified=rollback_expected_ok,
        acceptance_plan_digest_verified=acceptance_expected_ok
        and write_gate.acceptance_plan_digest_verified,
        managed_write_plan_digest_verified=managed_write_expected_ok,
        checkpoint_verified=checkpoint_verified,
        checkpoint_hash_verified=checkpoint_hash_ok,
        latest_checkpoint_hash=checkpoint.latest_checkpoint_hash,
        write_approval_id=write_approval.resolution_id or write_approval_id or None,
        write_approval_digest=write_approval.digest,
        write_approval_expires_at=write_approval.expires_at,
        write_approval_present=write_approval_present,
        write_approval_verified=write_approval_verified,
        exact_expected_values_verified=exact_expected_values_verified,
        receipt_acceptable=receipt_acceptable,
        receipt_reversibility_accepted=reversibility_accepted,
        shadow_write_gate_ready=gate_ready,
        rollback_ready=write_gate.shadow_rollback_plan.rollback_verifiable,
        write_receipt_path=str(write_receipt_path),
        store_verified=store_verified,
        generation_verified=generation_verified,
        activation_pointer_target=pointer_target,
        activation_pointer_updated=activation_pointer_updated,
        activation_pointer_verified=activation_pointer_verified,
        rollback_target_verified=rollback_target_verified,
        already_applied=already_applied_verified,
        interrupted_activation_recovered=interrupted_activation_recovered,
        skill_receipt=receipt,
        evidence_checkpoint=checkpoint,
        shadow_write_gate=write_gate,
        blockers=blockers,
        warnings=warnings,
        next_steps=_managed_write_next_steps(outcome, managed_write_plan_digest),
        managed_prefix_mutated=managed_prefix_mutated,
        profile_mutated=profile_mutated,
    )


def _write_receipt_path(
    managed_prefix: Path,
    profile_name: str,
    managed_write_plan_digest: str | None,
) -> Path:
    digest = managed_write_plan_digest or "missing-digest"
    return managed_prefix / "profiles" / profile_name / "write_receipts" / f"{digest}.json"


def _read_write_receipt(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"_invalid": True}
    return data if isinstance(data, dict) else {"_invalid": True}


def _write_receipt_conflict_blockers(
    receipt: dict[str, Any],
    *,
    candidate_id: str,
    managed_write_plan_digest: str,
    managed_prefix: Path,
    profile_name: str,
    expected_source_sha256: str | None,
    expected_durable_plan_digest: str | None,
    expected_shadow_plan_digest: str | None,
    expected_rollback_plan_digest: str | None,
    expected_acceptance_plan_digest: str | None,
) -> list[str]:
    if receipt.get("_invalid") is True:
        return ["managed_write_receipt_invalid"]
    checks = {
        "candidate_id": candidate_id,
        "managed_write_plan_digest": managed_write_plan_digest,
        "managed_prefix": str(managed_prefix),
        "profile_name": profile_name,
    }
    optional_checks = {
        "source_sha256": expected_source_sha256,
        "durable_plan_digest": expected_durable_plan_digest,
        "shadow_plan_digest": expected_shadow_plan_digest,
        "rollback_plan_digest": expected_rollback_plan_digest,
        "acceptance_plan_digest": expected_acceptance_plan_digest,
    }
    blockers: list[str] = []
    for key, expected in checks.items():
        if receipt.get(key) != expected:
            blockers.append(f"managed_write_receipt_{key}_mismatch")
    for key, expected in optional_checks.items():
        if expected and receipt.get(key) != expected:
            blockers.append(f"managed_write_receipt_{key}_mismatch")
    for key in [
        "store_skill_path",
        "generation_skill_path",
        "activation_pointer",
        "rollback_target",
    ]:
        if not receipt.get(key):
            blockers.append(f"managed_write_receipt_{key}_missing")
    return _unique(blockers)


def _apply_shadow_managed_write(
    *,
    candidate_id: str,
    skill_name: str | None,
    managed_prefix: Path,
    profile_name: str,
    source_skill_path: Path | None,
    source_sha256: str | None,
    store_skill_path: Path | None,
    generation_skill_path: Path | None,
    activation_pointer: Path | None,
    rollback_target: Path | None,
    managed_write_plan_digest: str | None,
    durable_plan_digest: str | None,
    shadow_plan_digest: str | None,
    rollback_plan_digest: str | None,
    acceptance_plan_digest: str | None,
    write_approval_id: str | None,
    checkpoint_hash: str | None,
    write_receipt_path: Path,
    skills_dir: Path,
    runs_dir: Path,
) -> dict[str, Any]:
    state: dict[str, Any] = {
        "blockers": [],
        "store_verified": False,
        "generation_verified": False,
        "activation_pointer_updated": False,
        "activation_pointer_verified": False,
        "rollback_target_verified": False,
        "interrupted_activation_recovered": False,
        "managed_prefix_mutated": False,
        "profile_mutated": False,
        "activation_pointer_target": None,
    }
    blockers: list[str] = state["blockers"]
    paths = [store_skill_path, generation_skill_path, activation_pointer, rollback_target, write_receipt_path]
    blockers.extend(_managed_prefix_write_blockers(managed_prefix, skills_dir, runs_dir, paths))
    if source_skill_path is None or not source_skill_path.exists() or not source_skill_path.is_file():
        blockers.append("managed_write_source_missing")
    if source_sha256 is None:
        blockers.append("managed_write_source_sha256_missing")
    if store_skill_path is None:
        blockers.append("managed_write_store_path_missing")
    if generation_skill_path is None:
        blockers.append("managed_write_generation_path_missing")
    if activation_pointer is None:
        blockers.append("managed_write_activation_pointer_missing")
    if rollback_target is None:
        blockers.append("managed_write_rollback_target_missing")
    if managed_write_plan_digest is None:
        blockers.append("managed_write_plan_digest_missing")
    if blockers:
        state["blockers"] = _unique(blockers)
        return state

    source_skill_path = cast(Path, source_skill_path)
    source_sha256 = cast(str, source_sha256)
    store_skill_path = cast(Path, store_skill_path)
    generation_skill_path = cast(Path, generation_skill_path)
    activation_pointer = cast(Path, activation_pointer)
    rollback_target = cast(Path, rollback_target)
    managed_write_plan_digest = cast(str, managed_write_plan_digest)

    try:
        source_bytes = source_skill_path.read_bytes()
    except OSError:
        blockers.append("managed_write_source_read_failed")
        state["blockers"] = _unique(blockers)
        return state
    if hashlib.sha256(source_bytes).hexdigest() != source_sha256:
        blockers.append("managed_write_source_hash_mismatch")
    if not rollback_target.exists() or not rollback_target.is_dir():
        blockers.append("managed_write_rollback_target_missing")
    pointer_target_before = _activation_pointer_target(activation_pointer)
    pointer_target_path_before = _activation_pointer_target_path(
        pointer_target_before,
        activation_pointer,
    )
    generation_dir = generation_skill_path.parent.parent.parent
    if not _same_path(pointer_target_path_before, rollback_target):
        blockers.append("managed_write_activation_pointer_precondition_mismatch")
    if store_skill_path.exists():
        if not store_skill_path.is_file():
            blockers.append("managed_write_store_conflict")
        else:
            try:
                store_bytes = store_skill_path.read_bytes()
            except OSError:
                blockers.append("managed_write_store_read_failed")
            else:
                if store_bytes != source_bytes:
                    blockers.append("managed_write_store_conflict")
    if generation_skill_path.exists():
        if not generation_skill_path.is_file():
            blockers.append("managed_write_generation_conflict")
        else:
            try:
                generation_bytes = generation_skill_path.read_bytes()
            except OSError:
                blockers.append("managed_write_generation_read_failed")
            else:
                if generation_bytes != source_bytes:
                    blockers.append("managed_write_generation_conflict")
    if write_receipt_path.exists():
        blockers.append("managed_write_receipt_conflict")
    if blockers:
        state["blockers"] = _unique(blockers)
        return state

    blockers.extend(
        _managed_prefix_write_blockers(
            managed_prefix,
            skills_dir,
            runs_dir,
            [store_skill_path, generation_skill_path, activation_pointer, rollback_target, write_receipt_path],
        )
    )
    if blockers:
        state["blockers"] = _unique(blockers)
        return state

    pointer_switched = False
    state["interrupted_activation_recovered"] = bool(
        store_skill_path.exists() or generation_skill_path.exists()
    )
    try:
        _write_managed_bytes(store_skill_path, source_bytes)
        _write_managed_bytes(generation_skill_path, source_bytes)
        _atomic_write_text(activation_pointer, str(generation_dir))
        pointer_switched = True
        state["activation_pointer_updated"] = True
        state["managed_prefix_mutated"] = True
        state["profile_mutated"] = True
    except OSError:
        blockers.append("managed_write_io_failure")
        state["managed_prefix_mutated"] = bool(store_skill_path.exists() or generation_skill_path.exists())
        state["profile_mutated"] = pointer_switched
        if pointer_switched:
            try:
                _atomic_write_text(activation_pointer, str(rollback_target))
                state["activation_pointer_target"] = _activation_pointer_target(activation_pointer)
            except OSError:
                blockers.append("managed_write_pointer_restore_failed")
        state["blockers"] = _unique(blockers)
        return state

    pointer_target_after = _activation_pointer_target(activation_pointer)
    state["activation_pointer_target"] = pointer_target_after
    state["store_verified"] = _path_sha256_matches(store_skill_path, source_sha256)
    state["generation_verified"] = _path_sha256_matches(generation_skill_path, source_sha256)
    state["activation_pointer_verified"] = _same_path(
        _activation_pointer_target_path(pointer_target_after, activation_pointer),
        generation_dir,
    )
    state["rollback_target_verified"] = rollback_target.exists() and rollback_target.is_dir()
    if not state["store_verified"]:
        blockers.append("managed_write_store_verification_failed")
    if not state["generation_verified"]:
        blockers.append("managed_write_generation_verification_failed")
    if not state["activation_pointer_verified"]:
        blockers.append("managed_write_pointer_verification_failed")
    if not state["rollback_target_verified"]:
        blockers.append("managed_write_rollback_verification_failed")
    if blockers:
        state["blockers"] = _unique(blockers)
        return state

    receipt = {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "skill_name": skill_name,
        "managed_write_plan_digest": managed_write_plan_digest,
        "source_sha256": source_sha256,
        "durable_plan_digest": durable_plan_digest,
        "shadow_plan_digest": shadow_plan_digest,
        "rollback_plan_digest": rollback_plan_digest,
        "acceptance_plan_digest": acceptance_plan_digest,
        "managed_prefix": str(managed_prefix),
        "profile_name": profile_name,
        "store_skill_path": str(store_skill_path),
        "generation_skill_path": str(generation_skill_path),
        "activation_pointer": str(activation_pointer),
        "rollback_target": str(rollback_target),
        "write_approval_id": write_approval_id,
        "checkpoint_hash": checkpoint_hash,
        "applied_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        _atomic_write_text(
            write_receipt_path,
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        )
    except OSError:
        blockers.append("managed_write_receipt_write_failed")
        try:
            _atomic_write_text(activation_pointer, str(rollback_target))
            state["activation_pointer_target"] = _activation_pointer_target(activation_pointer)
            state["activation_pointer_verified"] = False
        except OSError:
            blockers.append("managed_write_pointer_restore_failed")
        state["blockers"] = _unique(blockers)
        return state
    state["managed_prefix_mutated"] = True
    state["blockers"] = _unique(blockers)
    return state


def _managed_prefix_write_blockers(
    managed_prefix: Path,
    skills_dir: Path,
    runs_dir: Path,
    paths: list[Path | None],
) -> list[str]:
    blockers: list[str] = []
    if managed_prefix.exists() and managed_prefix.is_symlink():
        blockers.append(f"managed_write_path_symlink:{managed_prefix}")
    if _is_within(managed_prefix, skills_dir):
        blockers.append("managed_prefix_overlaps_skills_dir")
    for forbidden_name in [
        "admission_snapshots",
        "admission_staging",
        "shadow_activation_acceptance",
    ]:
        if _is_within(managed_prefix, runs_dir / forbidden_name):
            blockers.append(f"managed_prefix_overlaps_{forbidden_name}")
    forbidden_roots = [
        skills_dir,
        runs_dir / "admission_snapshots",
        runs_dir / "admission_staging",
        runs_dir / "shadow_activation_acceptance",
    ]
    for path in paths:
        if path is None:
            continue
        if _has_symlink_component(path, managed_prefix):
            blockers.append(f"managed_write_path_symlink:{path}")
        if not _is_within(path, managed_prefix):
            blockers.append(f"managed_write_path_outside_prefix:{path}")
        for forbidden_root in forbidden_roots:
            if _is_within(path, forbidden_root):
                blockers.append(f"managed_write_path_forbidden:{path}")
    return _unique(blockers)


def _has_symlink_component(path: Path, managed_prefix: Path) -> bool:
    current = path
    stop = managed_prefix.parent
    while True:
        if current.exists() and current.is_symlink():
            return True
        if current == stop or current.parent == current:
            return False
        current = current.parent


def _missing_receipt_after_pointer_switch(
    *,
    activation_pointer: Path | None,
    source_sha256: str | None,
    store_skill_path: Path | None,
    skill_name: str | None,
) -> bool:
    if activation_pointer is None or source_sha256 is None or not skill_name:
        return False
    pointer_target = _activation_pointer_target(activation_pointer)
    pointer_target_path = _activation_pointer_target_path(pointer_target, activation_pointer)
    if pointer_target_path is None or not pointer_target_path.exists():
        return False
    generation_skill_path = pointer_target_path / "skills" / skill_name / "SKILL.md"
    return _path_sha256_matches(store_skill_path, source_sha256) and _path_sha256_matches(
        generation_skill_path,
        source_sha256,
    )


def _verify_managed_write_applied_state(
    *,
    store_skill_path: Path | None,
    generation_skill_path: Path | None,
    activation_pointer: Path | None,
    rollback_target: Path | None,
    source_sha256: str | None,
) -> bool:
    if generation_skill_path is None:
        return False
    generation_dir = generation_skill_path.parent.parent.parent
    pointer_target = _activation_pointer_target(activation_pointer)
    return (
        _path_sha256_matches(store_skill_path, source_sha256)
        and _path_sha256_matches(generation_skill_path, source_sha256)
        and _same_path(
            _activation_pointer_target_path(pointer_target, activation_pointer),
            generation_dir,
        )
        and bool(rollback_target and rollback_target.exists() and rollback_target.is_dir())
    )


def _write_managed_bytes(path: Path, data: bytes) -> bool:
    if path.exists() and path.read_bytes() == data:
        return False
    _atomic_write_bytes(path, data)
    return True


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        tmp_path.write_bytes(data)
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        tmp_path.write_text(text, encoding="utf-8")
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass


def _store_dir(prefix: Path, source_sha256: str | None, skill_name: str) -> Path | None:
    if not source_sha256 or not skill_name:
        return None
    return prefix / "store" / f"sha256-{source_sha256}" / "skills" / skill_name


def _latest_generation(profile_dir: Path) -> int | None:
    generations_dir = profile_dir / "generations"
    if not generations_dir.exists():
        return None
    generations: list[int] = []
    for item in generations_dir.iterdir():
        if item.is_dir() and item.name.isdigit():
            generations.append(int(item.name))
    return max(generations) if generations else None


def _shadow_plan_digest(
    *,
    candidate_id: str,
    source_sha256: str | None,
    durable_plan_digest: str | None,
    managed_prefix: Path,
    store_skill_path: Path | None,
    profile_name: str,
    activation_pointer: Path,
    planned_generation: int | None,
    generation_skill_path: Path | None,
    previous_generation: int | None,
    rollback_target: str | None,
) -> str:
    payload: dict[str, Any] = {
        "candidate_id": candidate_id,
        "source_sha256": source_sha256,
        "durable_plan_digest": durable_plan_digest,
        "managed_prefix": str(managed_prefix),
        "store_skill_path": str(store_skill_path) if store_skill_path else None,
        "profile_name": profile_name,
        "activation_pointer": str(activation_pointer),
        "planned_generation": planned_generation,
        "generation_skill_path": (
            str(generation_skill_path) if generation_skill_path else None
        ),
        "previous_generation": previous_generation,
        "rollback_target": rollback_target,
        "collision_policy": "shadow_managed_prefix_only",
        "activation_policy": "profile_pointer_switch",
        "canary_scope": "manual",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _rollback_plan_digest(
    *,
    candidate_id: str,
    managed_prefix: Path,
    profile_name: str,
    activation_pointer: Path | None,
    activation_pointer_target: str | None,
    current_generation: int | None,
    planned_generation: int | None,
    rollback_generation: int | None,
    rollback_target: Path | None,
    shadow_plan_digest: str | None,
) -> str:
    payload: dict[str, Any] = {
        "candidate_id": candidate_id,
        "managed_prefix": str(managed_prefix),
        "profile_name": profile_name,
        "activation_pointer": str(activation_pointer) if activation_pointer else None,
        "activation_pointer_target": activation_pointer_target,
        "current_generation": current_generation,
        "planned_generation": planned_generation,
        "rollback_generation": rollback_generation,
        "rollback_target": str(rollback_target) if rollback_target else None,
        "shadow_plan_digest": shadow_plan_digest,
        "rollback_policy": "profile_pointer_restore",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _acceptance_plan_digest(
    *,
    candidate_id: str,
    planned_managed_prefix: Path,
    acceptance_prefix: Path,
    source_sha256: str | None,
    store_skill_path: Path | None,
    generation_skill_path: Path | None,
    activation_pointer: Path | None,
    rollback_target: Path | None,
    shadow_plan_digest: str | None,
) -> str:
    payload: dict[str, Any] = {
        "candidate_id": candidate_id,
        "planned_managed_prefix": str(planned_managed_prefix),
        "acceptance_prefix": str(acceptance_prefix),
        "source_sha256": source_sha256,
        "store_skill_path": str(store_skill_path) if store_skill_path else None,
        "generation_skill_path": (
            str(generation_skill_path) if generation_skill_path else None
        ),
        "activation_pointer": str(activation_pointer) if activation_pointer else None,
        "rollback_target": str(rollback_target) if rollback_target else None,
        "shadow_plan_digest": shadow_plan_digest,
        "acceptance_scope": "runs_dir_only",
        "activation_policy": "profile_pointer_switch",
        "rollback_policy": "profile_pointer_restore",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _managed_write_plan_digest(
    *,
    candidate_id: str,
    source_sha256: str | None,
    durable_plan_digest: str | None,
    shadow_plan_digest: str | None,
    rollback_plan_digest: str | None,
    acceptance_plan_digest: str | None,
    managed_prefix: Path,
    profile_name: str,
    store_skill_path: Path | None,
    generation_skill_path: Path | None,
    activation_pointer: Path | None,
    rollback_target: Path | None,
) -> str:
    payload: dict[str, Any] = {
        "candidate_id": candidate_id,
        "source_sha256": source_sha256,
        "durable_plan_digest": durable_plan_digest,
        "shadow_plan_digest": shadow_plan_digest,
        "rollback_plan_digest": rollback_plan_digest,
        "acceptance_plan_digest": acceptance_plan_digest,
        "managed_prefix": str(managed_prefix),
        "profile_name": profile_name,
        "store_skill_path": str(store_skill_path) if store_skill_path else None,
        "generation_skill_path": (
            str(generation_skill_path) if generation_skill_path else None
        ),
        "activation_pointer": str(activation_pointer) if activation_pointer else None,
        "rollback_target": str(rollback_target) if rollback_target else None,
        "managed_prefix_write_policy": "managed_prefix_only_write",
        "profile_activation_policy": "profile_pointer_switch",
        "rollback_policy": "profile_pointer_rollback",
        "stable_routing_policy": "stable_routing_unchanged",
        "governor_policy": "governor_advisory_only",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _default_acceptance_prefix(
    runs_dir: Path,
    candidate_id: str,
    shadow_plan_digest: str | None,
) -> Path:
    digest = (shadow_plan_digest or "no-digest")[:12]
    safe_candidate_id = re.sub(r"[^A-Za-z0-9_.-]", "_", candidate_id)
    return runs_dir / "shadow_activation_acceptance" / f"{safe_candidate_id}_{digest}"


def _map_planned_path(
    value: str | None,
    *,
    planned_prefix: Path,
    acceptance_prefix: Path,
) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    try:
        relative = path.resolve(strict=False).relative_to(
            planned_prefix.resolve(strict=False)
        )
    except ValueError:
        return None
    return acceptance_prefix / relative


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
    except ValueError:
        return False
    return True


def _collect_acceptance_file_conflicts(
    files: list[tuple[Path, bytes]],
    blockers: list[str],
) -> None:
    for path, data in files:
        if path.exists() and path.read_bytes() != data:
            blockers.append(f"acceptance_evidence_conflict:{path}")


def _write_bytes(path: Path, data: bytes) -> None:
    if path.exists() and path.read_bytes() != data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _write_pointer(path: Path, target: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(target), encoding="utf-8")


def _activation_pointer_target(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    if path.is_symlink():
        try:
            return str(path.readlink())
        except OSError:
            return None
    if path.is_file():
        try:
            return path.read_text(encoding="utf-8").strip() or None
        except OSError:
            return None
    return str(path)


def _path_sha256_matches(path: Path | None, expected_sha256: str | None) -> bool:
    if path is None or expected_sha256 is None or not path.exists() or not path.is_file():
        return False
    return hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha256


def _activation_pointer_target_path(
    pointer_target: str | None,
    activation_pointer: Path | None,
) -> Path | None:
    if not pointer_target:
        return None
    target = Path(pointer_target)
    if not target.is_absolute() and activation_pointer is not None:
        target = activation_pointer.parent / target
    return target


def _same_path(left: Path | None, right: Path | None) -> bool:
    if left is None or right is None:
        return False
    return left.resolve(strict=False) == right.resolve(strict=False)


def _current_generation(pointer_target: str | None) -> int | None:
    if not pointer_target:
        return None
    name = Path(pointer_target).name
    return int(name) if name.isdigit() else None


def _next_steps(ready: bool, previous_generation: int | None) -> list[str]:
    if not ready:
        return [
            "Resolve durable admission preview blockers before shadow activation.",
            "Rerun shadow-activation-plan after exact review evidence is available.",
        ]
    steps = [
        "Use this as a dry-run activation plan only; shadow-managed-write owns managed-prefix mutation.",
        "Run shadow-activation-acceptance and shadow-write-gate before any managed-prefix write.",
    ]
    if previous_generation is None:
        steps.append("No rollback generation exists yet; first activation must record one.")
    else:
        steps.append("shadow-managed-write must preserve rollback to the previous generation.")
    return steps


def _rollback_next_steps(verifiable: bool, pointer_exists: bool) -> list[str]:
    if verifiable:
        steps = [
            "Use this as rollback proof only; shadow-managed-write owns profile switching.",
            "shadow-managed-write must restore the activation pointer to the rollback target on failure.",
        ]
        if not pointer_exists:
            steps.append("No current activation pointer exists yet; first activation must create one atomically.")
        return steps
    return [
        "Create or recover a previous generation before enabling activation rollback.",
        "Rerun shadow-rollback-plan after shadow activation blockers are resolved.",
    ]


def _acceptance_next_steps(accepted: bool, planned: bool) -> list[str]:
    if accepted:
        return [
            "Use this as controlled-prefix acceptance evidence only; durable skills remain untouched.",
            "Keep actual write mode behind a separate human-approved gate.",
        ]
    if planned:
        return [
            "Run with --prepare-acceptance-evidence to exercise pointer switch and rollback inside runs/.",
            "Review acceptance_plan_digest before any future write-mode implementation.",
        ]
    return [
        "Resolve shadow activation acceptance blockers before preparing sandbox evidence.",
        "Rerun shadow-activation-acceptance after the activation plan has rollback evidence.",
    ]


def _write_gate_next_steps(ready: bool) -> list[str]:
    if ready:
        return [
            "Use this report as pre-write evidence only; shadow-write-gate itself does not mutate the managed prefix.",
            "shadow-managed-write must require this exact acceptance_plan_digest before switching the real pointer.",
        ]
    return [
        "Prepare acceptance evidence under runs/ and rerun shadow-write-gate.",
        "Resolve blockers before running shadow-managed-write against the managed prefix.",
    ]


def _managed_write_receipt_blockers(receipt: Any) -> tuple[list[str], bool]:
    proofs = {proof.category: proof for proof in receipt.proofs}
    blockers: list[str] = []

    origin = proofs.get("origin")
    if origin is None or origin.status in {"missing", "blocked"}:
        blockers.append("receipt_origin_missing_or_blocked")

    utility = proofs.get("utility")
    if utility is None or utility.status in {"missing", "blocked"}:
        blockers.append("receipt_utility_missing_or_blocked")

    containment = proofs.get("containment")
    if containment is None or containment.status == "blocked":
        blockers.append("receipt_containment_blocked")

    compatibility = proofs.get("compatibility")
    if compatibility is None or compatibility.status == "blocked":
        blockers.append("receipt_compatibility_blocked")

    approval = proofs.get("approval")
    if approval is None or approval.status != "present":
        blockers.append("receipt_approval_missing_or_blocked")

    reversibility = proofs.get("reversibility")
    reversibility_accepted = False
    if reversibility is None:
        blockers.append("receipt_reversibility_missing")
    elif set(reversibility.blockers) == {"write_mode_rollback_not_implemented"}:
        reversibility_accepted = True
    elif reversibility.status != "present":
        blockers.append("receipt_reversibility_blocked")

    return _unique(blockers), reversibility_accepted


@dataclass(frozen=True)
class _WriteApprovalEvidence:
    verified: bool
    blocker: str
    resolution_id: str | None = None
    digest: str | None = None
    expires_at: str | None = None


def _find_write_approval_resolution(
    *,
    managed_write_plan_digest: str | None,
    candidate_id: str,
    runs_dir: Path,
    write_approval_id: str | None,
) -> _WriteApprovalEvidence:
    if not write_approval_id:
        return _WriteApprovalEvidence(False, "write_approval_id_missing")
    if managed_write_plan_digest is None:
        return _WriteApprovalEvidence(False, "managed_write_plan_digest_missing")
    try:
        ledger = load_input_request_resolution_ledger(runs_dir)
    except InputResolutionLedgerError:
        return _WriteApprovalEvidence(
            False,
            "write_approval_invalid",
            resolution_id=write_approval_id,
        )

    matches = [
        record
        for record in ledger.resolutions
        if (
            (record.id == write_approval_id or record.input_request_id == write_approval_id)
            and record.decision == "approve_review"
            and record.status == "resolved"
            and record.source_request.kind == "durable_admission_review"
            and record.source_request.related_candidate_id == candidate_id
        )
    ]
    if not matches:
        return _WriteApprovalEvidence(
            False,
            "write_approval_invalid",
            resolution_id=write_approval_id,
        )

    mismatch_seen: _WriteApprovalEvidence | None = None
    expired_seen: _WriteApprovalEvidence | None = None
    missing_expiry_seen: _WriteApprovalEvidence | None = None
    for record in reversed(matches):
        digest = _note_token(record.notes, "managed_write_plan_digest")
        expires_at = _note_token(record.notes, "expires_at")
        resolution_id = record.id
        if digest != managed_write_plan_digest:
            mismatch_seen = _WriteApprovalEvidence(
                False,
                "write_approval_digest_mismatch",
                resolution_id=resolution_id,
                digest=digest,
                expires_at=expires_at,
            )
            continue
        if not expires_at:
            missing_expiry_seen = _WriteApprovalEvidence(
                False,
                "write_approval_expiry_missing",
                resolution_id=resolution_id,
                digest=digest,
            )
            continue
        if _approval_expired(expires_at):
            expired_seen = _WriteApprovalEvidence(
                False,
                "write_approval_expired",
                resolution_id=resolution_id,
                digest=digest,
                expires_at=expires_at,
            )
            continue
        return _WriteApprovalEvidence(
            True,
            "",
            resolution_id=resolution_id,
            digest=digest,
            expires_at=expires_at,
        )

    return (
        mismatch_seen
        or expired_seen
        or missing_expiry_seen
        or _WriteApprovalEvidence(
            False,
            "write_approval_invalid",
            resolution_id=write_approval_id,
        )
    )


def _note_token(notes: str, key: str) -> str | None:
    prefix = f"{key}="
    for token in notes.replace(",", " ").split():
        if token.startswith(prefix):
            return token[len(prefix):].strip()
    return None


def _approval_expired(expires_at: str) -> bool:
    try:
        parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc) <= datetime.now(timezone.utc)


def _expected_matches(
    *,
    actual: str | None,
    expected: str | None,
    mismatch_blocker: str,
    missing_blocker: str,
    required: bool,
    blockers: list[str],
) -> bool:
    if not expected:
        if required:
            blockers.append(missing_blocker)
        return False
    matched = actual == expected
    if not matched:
        blockers.append(mismatch_blocker)
    return matched


def _managed_write_next_steps(outcome: str, digest: str | None) -> list[str]:
    if outcome == "approval_required":
        steps = [
            "Record a separate human write approval before any managed-prefix mutation.",
            "Append and verify an evidence checkpoint after approval, then rerun this dry-run with expected hashes and digests.",
        ]
        if digest:
            steps.insert(
                1,
                f"Use managed_write_plan_digest={digest} in the write approval notes.",
            )
        return steps
    if outcome == "ready_for_managed_prefix_write":
        return [
            "This dry-run is ready for --no-dry-run with the same expected hashes, digests, checkpoint, and write approval.",
            "Do not use admit-candidate --no-dry-run for managed-prefix activation.",
        ]
    if outcome in {"managed_prefix_write_applied", "already_applied"}:
        return ["Verify rollback and checkpoint evidence after the managed-prefix write."]
    return [
        "Resolve managed-write blockers without mutating durable skills or routing.",
        "Rerun shadow-managed-write --dry-run after receipt, checkpoint, and shadow gate evidence are clean.",
    ]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
