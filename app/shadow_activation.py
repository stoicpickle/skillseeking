from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.admission_plan import AdmissionPlanError
from app.durable_admission import build_durable_admission_preview
from app.models import (
    ShadowActivationAcceptanceReport,
    ShadowActivationPlanReport,
    ShadowRollbackPlanReport,
    ShadowWriteGateReport,
)


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
    previous_generation = _latest_generation(profile_dir)
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
        assert source_bytes is not None
        assert store_skill_path is not None
        assert generation_skill_path is not None
        assert activation_pointer is not None
        assert rollback_target is not None
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
        "Use this as a dry-run activation plan only; no managed prefix writes are enabled.",
        "Implement interruption-safe generation activation before any write-mode slice.",
    ]
    if previous_generation is None:
        steps.append("No rollback generation exists yet; first activation must record one.")
    else:
        steps.append("Future write mode must preserve rollback to the previous generation.")
    return steps


def _rollback_next_steps(verifiable: bool, pointer_exists: bool) -> list[str]:
    if verifiable:
        steps = [
            "Use this as rollback proof only; profile switching remains unavailable.",
            "Future write mode must restore the activation pointer to the rollback target on failure.",
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
            "Use this report as a human approval gate only; no managed-prefix write is enabled.",
            "Future write mode must require this exact acceptance_plan_digest before switching the real pointer.",
        ]
    return [
        "Prepare acceptance evidence under runs/ and rerun shadow-write-gate.",
        "Resolve blockers before implementing any real managed-prefix write mode.",
    ]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
