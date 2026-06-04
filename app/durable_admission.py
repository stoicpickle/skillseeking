from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from app.admission_plan import AdmissionPlanError, build_admission_plan
from app.input_resolution_ledger import (
    InputResolutionLedgerError,
    latest_input_request_resolutions,
    load_input_request_resolution_ledger,
)
from app.models import (
    AdmissionDependencyDiff,
    AdmissionDependencyInstallContract,
    AdmissionDependencyInstallItem,
    AdmissionPlanReport,
    AdmissionPermissionDependencyDiff,
    AdmissionPermissionDiffItem,
    AdmissionSourceArtifact,
    DurableAdmissionPreviewOutcome,
    DurableAdmissionPreviewReport,
    DurableAdmissionWriteOperation,
    DurableAdmissionWritePlan,
)


VALID_COLLISION_POLICIES: set[str] = {
    "block_existing",
    "allow_replace_with_approval",
}

APPROVAL_BLOCKERS: set[str] = {
    "durable_review_resolution_missing",
    "plan_digest_approval_missing",
    "plan_digest_approval_invalid",
    "plan_digest_approval_mismatch",
    "plan_digest_approval_expiry_missing",
    "plan_digest_approval_expired",
}

DEPENDENCY_EVIDENCE_UNSAFE_ADMISSION_BLOCKERS: set[str] = {
    "candidate_blocked",
    "candidate_duplicate",
    "candidate_quarantined",
    "candidate_repair_required",
    "candidate_temporary_use_missing",
    "candidate_validation_failures",
    "candidate_validation_pass_missing",
    "evidence_run_log_missing",
    "matching_request_missing",
    "promotion_approval_missing",
    "source_path_outside_runs",
    "source_permission_widening",
    "source_scripted_unsupported",
    "source_skill_missing",
    "source_skill_parse_failed",
    "source_skill_path_missing",
    "source_validation_failed",
}


def build_durable_admission_preview(
    candidate_id: str,
    *,
    runs_dir: Path,
    skills_dir: Path,
    dry_run: bool = True,
    collision_policy: str = "block_existing",
    permission_approval_id: str | None = None,
    plan_approval_id: str | None = None,
    prepare_write_evidence: bool = False,
    expected_source_sha256: str | None = None,
    prepare_dependency_evidence: bool = False,
    expected_dependency_plan_digest: str | None = None,
    dependency_approval_id: str | None = None,
) -> DurableAdmissionPreviewReport:
    if not dry_run:
        raise AdmissionPlanError(
            "durable admission mutation is not implemented; rerun with --dry-run"
        )
    if collision_policy not in VALID_COLLISION_POLICIES:
        allowed = ", ".join(sorted(VALID_COLLISION_POLICIES))
        raise AdmissionPlanError(
            f"invalid collision policy: {collision_policy}; allowed: {allowed}"
        )

    admission_plan = build_admission_plan(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=skills_dir,
    )
    source_path = _selected_source_path(admission_plan)
    source_sha256 = (
        _sha256(source_path)
        if source_path is not None and _source_hashing_allowed(admission_plan)
        else None
    )
    target_dir, target_path = _target_paths(admission_plan, skills_dir)
    snapshot_dir, snapshot_path = _snapshot_paths(candidate_id, source_sha256, runs_dir)
    destination_stage_dir, destination_stage_path = _destination_stage_paths(
        candidate_id,
        source_sha256,
        target_dir,
        runs_dir,
    )
    blockers = list(admission_plan.blockers)
    write_blockers = list(blockers)
    warnings = list(admission_plan.warnings)
    required_human_records = [
        "promotion_approved_by",
        "promotion_approved_at",
        "durable_admission_review approve_review resolution",
        "plan digest approval resolution",
    ]
    permission_widening = list(admission_plan.durable_registry.permission_widening)
    if permission_widening:
        required_human_records.append("permission widening approval resolution")
        if not permission_approval_id:
            write_blockers.append("permission_widening_approval_missing")
        elif not _has_permission_approval_resolution(permission_approval_id, runs_dir):
            write_blockers.append("permission_widening_approval_invalid")

    review_approved = _has_approve_review_resolution(admission_plan, runs_dir)
    name_collision = admission_plan.durable_registry.name_collision is not None

    if not admission_plan.ready_for_durable_review and not _only_replaceable_collision(
        blockers,
        name_collision=name_collision,
        collision_policy=collision_policy,
    ):
        blockers.append(f"admission_plan_outcome:{admission_plan.outcome}")
        write_blockers.append(f"admission_plan_outcome:{admission_plan.outcome}")
    if not review_approved:
        blockers.append("durable_review_resolution_missing")
        write_blockers.append("durable_review_resolution_missing")
    elif name_collision and collision_policy == "block_existing":
        write_blockers.append("durable_name_collision")

    replacement_approved = bool(
        name_collision
        and collision_policy == "allow_replace_with_approval"
        and review_approved
    )
    permission_widening_approved = bool(
        permission_widening
        and permission_approval_id
        and _has_permission_approval_resolution(permission_approval_id, runs_dir)
    )
    permission_dependency_diff = _permission_dependency_diff(admission_plan)
    dependency_install_contract = _dependency_install_contract(
        admission_plan=admission_plan,
        candidate_id=candidate_id,
        source_path=source_path,
        source_sha256=source_sha256,
        target_path=target_path,
        runs_dir=runs_dir,
        dependency_diff=permission_dependency_diff.dependency_diff,
        prepare_dependency_evidence=prepare_dependency_evidence,
        expected_dependency_plan_digest=expected_dependency_plan_digest,
        expected_source_sha256=expected_source_sha256,
        dependency_approval_id=dependency_approval_id,
    )
    write_blockers.extend(permission_dependency_diff.blockers)
    write_blockers.extend(dependency_install_contract.blockers)

    if replacement_approved:
        write_blockers = [
            blocker for blocker in write_blockers if blocker != "durable_name_collision"
        ]

    write_blockers = _unique(write_blockers)
    source_hash_verified = bool(
        source_sha256 is not None
        and (
            expected_source_sha256 is None
            or expected_source_sha256 == source_sha256
        )
    )
    if (
        prepare_write_evidence
        and expected_source_sha256 is not None
        and expected_source_sha256 != source_sha256
    ):
        write_blockers.append("source_hash_mismatch")
    evidence_state = _empty_evidence_state(
        prepare_write_evidence=prepare_write_evidence,
        expected_source_sha256=expected_source_sha256,
        source_hash_verified=source_hash_verified,
        destination_stage_dir=destination_stage_dir,
        destination_stage_path=destination_stage_path,
    )
    write_blockers = _unique(write_blockers)
    plan_operation = _write_operation(
        blockers=_plan_blockers_for_digest(
            write_blockers,
            name_collision=name_collision,
            collision_policy=collision_policy,
        ),
        name_collision=name_collision,
        collision_policy=collision_policy,
    )
    plan_digest = _plan_digest(
        candidate_id=candidate_id,
        operation=plan_operation,
        source_path=source_path,
        source_sha256=source_sha256,
        target_dir=target_dir,
        target_path=target_path,
        snapshot_dir=snapshot_dir,
        snapshot_path=snapshot_path,
        destination_stage_dir=destination_stage_dir,
        destination_stage_path=destination_stage_path,
        collision_policy=collision_policy,
        permission_approval_id=permission_approval_id,
        permission_dependency_diff=permission_dependency_diff,
        permission_widening=permission_widening,
        dependency_install_contract=dependency_install_contract,
        prepare_write_evidence=prepare_write_evidence,
        expected_source_sha256=expected_source_sha256,
        prepare_dependency_evidence=prepare_dependency_evidence,
        expected_dependency_plan_digest=expected_dependency_plan_digest,
        dependency_approval_id=dependency_approval_id,
    )
    plan_approval = _find_plan_approval_resolution(
        plan_digest=plan_digest,
        candidate_id=candidate_id,
        runs_dir=runs_dir,
        plan_approval_id=plan_approval_id,
    )
    if not plan_approval.verified:
        write_blockers.append(plan_approval.blocker)
    write_blockers = _unique(write_blockers)
    if prepare_write_evidence and not write_blockers:
        evidence_blockers, evidence_state = _prepare_write_evidence(
            source_path=source_path,
            source_sha256=source_sha256,
            snapshot_path=snapshot_path,
            destination_stage_path=destination_stage_path,
            state=evidence_state,
        )
        write_blockers = _unique([*write_blockers, *evidence_blockers])
    operation = _write_operation(
        blockers=write_blockers,
        name_collision=name_collision,
        collision_policy=collision_policy,
    )
    write_plan = DurableAdmissionWritePlan(
        operation=operation,
        plan_digest=plan_digest,
        plan_approval_id=plan_approval.resolution_id,
        plan_approval_digest=plan_approval.digest,
        plan_approval_expires_at=plan_approval.expires_at,
        plan_approval_verified=plan_approval.verified,
        source_skill_path=str(source_path) if source_path is not None else None,
        source_sha256=source_sha256,
        target_skill_dir=str(target_dir) if target_dir is not None else None,
        target_skill_path=str(target_path) if target_path is not None else None,
        snapshot_dir=str(snapshot_dir) if snapshot_dir is not None else None,
        snapshot_skill_path=str(snapshot_path) if snapshot_path is not None else None,
        snapshot_sha256=source_sha256,
        prepare_write_evidence=prepare_write_evidence,
        expected_source_sha256=expected_source_sha256,
        source_hash_verified=evidence_state.source_hash_verified,
        source_snapshot_created=evidence_state.source_snapshot_created,
        source_snapshot_retained=evidence_state.source_snapshot_retained,
        destination_stage_dir=evidence_state.destination_stage_dir,
        destination_stage_skill_path=evidence_state.destination_stage_skill_path,
        destination_stage_sha256=evidence_state.destination_stage_sha256,
        destination_stage_created=evidence_state.destination_stage_created,
        collision_policy=collision_policy,
        permission_approval_id=permission_approval_id,
        permission_dependency_diff=permission_dependency_diff,
        dependency_install_contract=dependency_install_contract,
        replacement_approved=replacement_approved,
        permission_widening_approved=permission_widening_approved,
        blockers=write_blockers,
        warnings=warnings,
    )

    blockers = _unique(write_plan.blockers)
    ready = not write_plan.blockers
    return DurableAdmissionPreviewReport(
        candidate_id=candidate_id,
        outcome="ready_for_mutation_preview" if ready else _blocked_outcome(blockers),
        ready_for_mutation_preview=ready,
        source_skill_path=str(source_path) if source_path is not None else None,
        source_sha256=source_sha256,
        target_skill_dir=str(target_dir) if target_dir is not None else None,
        target_skill_path=str(target_path) if target_path is not None else None,
        write_plan=write_plan,
        required_human_records=required_human_records,
        blockers=write_plan.blockers,
        warnings=warnings,
        next_steps=_next_steps(ready),
        admission_plan=admission_plan,
    )


def _selected_source_path(report: AdmissionPlanReport) -> Path | None:
    if not report.selected_source_artifact:
        return None
    path = Path(report.selected_source_artifact)
    return path if path.exists() else None


def _source_hashing_allowed(report: AdmissionPlanReport) -> bool:
    return "source_path_outside_runs" not in report.blockers


def _target_paths(
    report: AdmissionPlanReport,
    skills_dir: Path,
) -> tuple[Path | None, Path | None]:
    skill_name = report.candidate.get("skill_name")
    if not skill_name:
        selected = next(
            (
                artifact
                for artifact in report.source_artifacts
                if artifact.skill_path == report.selected_source_artifact
            ),
            None,
        )
        skill_name = selected.skill_name if selected is not None else None
    if not skill_name:
        return None, None
    target_dir = skills_dir / str(skill_name)
    return target_dir, target_dir / "SKILL.md"


def _has_approve_review_resolution(
    report: AdmissionPlanReport,
    runs_dir: Path,
) -> bool:
    try:
        ledger = load_input_request_resolution_ledger(runs_dir)
    except InputResolutionLedgerError:
        return False
    latest = latest_input_request_resolutions(ledger)
    if report.input_request is not None:
        resolution = latest.get(report.input_request.id)
        if (
            resolution is not None
            and resolution.decision == "approve_review"
            and resolution.status == "resolved"
        ):
            return True
    return any(
        resolution.decision == "approve_review"
        and resolution.status == "resolved"
        and resolution.source_request.kind == "durable_admission_review"
        and resolution.source_request.related_candidate_id == report.candidate_id
        for resolution in latest.values()
    )


def _has_permission_approval_resolution(
    approval_id: str,
    runs_dir: Path,
) -> bool:
    try:
        ledger = load_input_request_resolution_ledger(runs_dir)
    except InputResolutionLedgerError:
        return False
    resolution = next(
        (
            record
            for record in ledger.resolutions
            if record.id == approval_id or record.input_request_id == approval_id
        ),
        None,
    )
    return (
        resolution is not None
        and resolution.decision in {"approve_review", "approve_workflow"}
        and resolution.status == "resolved"
    )


def _permission_dependency_diff(
    report: AdmissionPlanReport,
) -> AdmissionPermissionDependencyDiff:
    source = _selected_source_artifact(report)
    current_permissions = _current_permissions(report)
    current_tools = _current_tools(report)
    requested_permissions = source.permissions if source is not None else {}
    requested_tools = source.allowed_tools if source is not None else []

    permission_changes = [
        _permission_diff_item(
            class_name=class_name,
            current_enabled=bool(current_permissions.get(class_name, False)),
            requested_enabled=bool(requested_permissions.get(class_name, False)),
        )
        for class_name in [
            "read_files",
            "write_files",
            "network",
            "secrets",
            "execute_code",
        ]
    ]
    added_permissions = [
        item.class_name for item in permission_changes if item.change == "added"
    ]
    removed_permissions = [
        item.class_name for item in permission_changes if item.change == "removed"
    ]
    added_tools = sorted(set(requested_tools) - set(current_tools))
    removed_tools = sorted(set(current_tools) - set(requested_tools))

    dependency_declarations = source.dependency_declarations if source is not None else {}
    dependency_blockers: list[str] = []
    dependency_warnings: list[str] = []
    dependency_names = _dependency_names(dependency_declarations)
    realized_names = _realized_dependency_names(dependency_declarations)
    unresolved_names = sorted(set(dependency_names) - set(realized_names))
    exact_realization_available = bool(dependency_names) and not unresolved_names
    if dependency_declarations:
        if unresolved_names:
            dependency_blockers.append("dependency_realization_missing")
        else:
            dependency_blockers.append("dependency_install_unsupported")

    blockers = list(dependency_blockers)
    if added_tools:
        blockers.append("tool_widening_approval_missing")

    return AdmissionPermissionDependencyDiff(
        permission_changes=permission_changes,
        added_permission_classes=added_permissions,
        removed_permission_classes=removed_permissions,
        added_tools=added_tools,
        removed_tools=removed_tools,
        permission_approval_required=bool(added_permissions or added_tools),
        dependency_diff=AdmissionDependencyDiff(
            dependencies_declared=bool(dependency_declarations),
            declaration_keys=sorted(dependency_declarations),
            exact_realization_available=(
                exact_realization_available if dependency_declarations else True
            ),
            added=dependency_names,
            blockers=dependency_blockers,
            realized=realized_names,
            unresolved=unresolved_names,
            warnings=dependency_warnings,
        ),
        blockers=_unique(blockers),
        warnings=dependency_warnings,
    )


def _dependency_names(declarations: dict[str, Any]) -> list[str]:
    names: set[str] = set()
    for key in ["dependencies", "requirements", "packages"]:
        names.update(_dependency_names_from_value(declarations.get(key)))
    lock_value = declarations.get("dependency_lock")
    if isinstance(lock_value, dict):
        for key in ["dependencies", "packages"]:
            names.update(_dependency_names_from_value(lock_value.get(key)))
    return sorted(names)


def _dependency_names_from_value(value: Any) -> set[str]:
    if isinstance(value, list):
        return {
            name
            for item in value
            if (name := _dependency_name_from_value(item))
        }
    if isinstance(value, dict):
        names: set[str] = set()
        for key, item in value.items():
            if isinstance(item, dict) and item.get("name"):
                names.add(str(item["name"]))
            else:
                names.add(str(key))
        return names
    return set()


def _dependency_name_from_value(value: Any) -> str:
    if isinstance(value, str):
        return value.split("==", 1)[0].split(">=", 1)[0].split("<=", 1)[0].strip()
    if isinstance(value, dict) and value.get("name"):
        return str(value["name"])
    return ""


def _realized_dependency_names(declarations: dict[str, Any]) -> list[str]:
    realization = declarations.get("dependency_realization")
    if isinstance(realization, list):
        return sorted(
            {
                str(item["name"])
                for item in realization
                if isinstance(item, dict)
                and item.get("name")
                and item.get("version")
                and item.get("sha256")
            }
        )
    if isinstance(realization, dict):
        return sorted(
            str(name)
            for name, item in realization.items()
            if isinstance(item, dict) and item.get("version") and item.get("sha256")
        )
    return []


def _dependency_install_contract(
    *,
    admission_plan: AdmissionPlanReport,
    candidate_id: str,
    source_path: Path | None,
    source_sha256: str | None,
    target_path: Path | None,
    runs_dir: Path,
    dependency_diff: AdmissionDependencyDiff,
    prepare_dependency_evidence: bool,
    expected_dependency_plan_digest: str | None,
    expected_source_sha256: str | None,
    dependency_approval_id: str | None,
) -> AdmissionDependencyInstallContract:
    source = _selected_source_artifact(admission_plan)
    declarations = source.dependency_declarations if source is not None else {}
    normalized_dependencies = _normalized_dependency_items(declarations, dependency_diff)
    manifest_path, manifest_path_blocker = _dependency_evidence_manifest_path(
        candidate_id,
        source_sha256,
        runs_dir,
    )
    dependency_plan_digest = _dependency_plan_digest(
        candidate_id=candidate_id,
        source_path=source_path,
        source_sha256=source_sha256,
        target_path=target_path,
        manifest_path=manifest_path,
        normalized_dependencies=normalized_dependencies,
    )
    blockers = list(dependency_diff.blockers)
    warnings = list(dependency_diff.warnings)
    unsafe_admission_blockers = _dependency_evidence_unsafe_admission_blockers(
        admission_plan.blockers
    )
    if manifest_path_blocker is not None:
        blockers.append(manifest_path_blocker)
    if prepare_dependency_evidence:
        blockers.extend(unsafe_admission_blockers)
    digest_verified = bool(
        expected_dependency_plan_digest is not None
        and expected_dependency_plan_digest == dependency_plan_digest
    )
    if (
        expected_dependency_plan_digest is not None
        and expected_dependency_plan_digest != dependency_plan_digest
    ):
        blockers.append("dependency_plan_digest_mismatch")
    if (
        prepare_dependency_evidence
        and expected_source_sha256 is not None
        and expected_source_sha256 != source_sha256
    ):
        blockers.append("source_hash_mismatch")

    approval = _find_dependency_approval_resolution(
        dependency_plan_digest=dependency_plan_digest,
        candidate_id=candidate_id,
        runs_dir=runs_dir,
        dependency_approval_id=dependency_approval_id,
    )
    if dependency_approval_id and not approval.verified:
        blockers.append(approval.blocker)

    manifest_sha256: str | None = None
    manifest_created = False
    manifest_retained = False
    write_preventing_blockers = {
        "dependency_evidence_manifest_path_escape",
        "dependency_plan_digest_mismatch",
        "source_hash_mismatch",
        "source_skill_missing",
        *unsafe_admission_blockers,
    }
    if prepare_dependency_evidence and not (set(blockers) & write_preventing_blockers):
        evidence_blockers, manifest_sha256, manifest_created, manifest_retained = (
            _prepare_dependency_evidence_manifest(
                candidate_id=candidate_id,
                source_path=source_path,
                source_sha256=source_sha256,
                target_path=target_path,
                manifest_path=manifest_path,
                runs_dir=runs_dir,
                normalized_dependencies=normalized_dependencies,
                dependency_blockers=dependency_diff.blockers,
                dependency_plan_digest=dependency_plan_digest,
            )
        )
        blockers.extend(evidence_blockers)
    return AdmissionDependencyInstallContract(
        dependency_plan_digest=dependency_plan_digest,
        expected_dependency_plan_digest=expected_dependency_plan_digest,
        dependency_plan_digest_verified=digest_verified,
        prepare_dependency_evidence=prepare_dependency_evidence,
        evidence_manifest_path=str(manifest_path) if manifest_path is not None else None,
        evidence_manifest_sha256=manifest_sha256,
        evidence_manifest_created=manifest_created,
        evidence_manifest_retained=manifest_retained,
        dependency_approval_id=approval.resolution_id,
        dependency_approval_digest=approval.digest,
        dependency_approval_expires_at=approval.expires_at,
        dependency_approval_verified=approval.verified,
        normalized_dependencies=normalized_dependencies,
        blockers=_unique(blockers),
        warnings=_unique(warnings),
    )


def _normalized_dependency_items(
    declarations: dict[str, Any],
    dependency_diff: AdmissionDependencyDiff,
) -> list[AdmissionDependencyInstallItem]:
    records: dict[str, dict[str, Any]] = {}
    for key in ["dependencies", "requirements", "packages"]:
        _collect_dependency_records(records, key, key, declarations.get(key))
    lock_value = declarations.get("dependency_lock")
    if isinstance(lock_value, dict):
        for key in ["dependencies", "packages"]:
            _collect_dependency_records(
                records,
                "dependency_lock",
                f"dependency_lock.{key}",
                lock_value.get(key),
            )
    _collect_realization_records(records, declarations.get("dependency_realization"))

    realized = set(dependency_diff.realized)
    items: list[AdmissionDependencyInstallItem] = []
    for name in sorted(records):
        record = records[name]
        specs = sorted(record["declared_specs"])
        versions = sorted(record["declared_versions"])
        warnings: list[str] = []
        if len(specs) > 1 or len(versions) > 1:
            warnings.append("dependency_declaration_conflict")
        realization_candidates = [
            {"version": version, "sha256": sha256}
            for version, sha256 in sorted(record["realization_candidates"])
        ]
        realization_version = record.get("realization_version")
        realization_sha256 = record.get("realization_sha256")
        if name in realized and realization_version and realization_sha256:
            status = "exact_realized"
        elif not record["declaration_keys"] and realization_version and realization_sha256:
            status = "realization_without_declaration"
            warnings.append("dependency_realization_without_declaration")
        else:
            status = "unresolved"
        items.append(
            AdmissionDependencyInstallItem(
                name=name,
                declaration_keys=sorted(record["declaration_keys"]),
                declaration_sources=sorted(record["declaration_sources"]),
                declared_spec=specs[0] if specs else None,
                declared_version=versions[0] if versions else None,
                declared_specs=specs,
                declared_versions=versions,
                realization_version=realization_version,
                realization_sha256=realization_sha256,
                realization_candidates=realization_candidates,
                status=status,
                warnings=warnings,
            )
        )
    return items


def _collect_dependency_records(
    records: dict[str, dict[str, Any]],
    declaration_key: str,
    declaration_source: str,
    value: Any,
) -> None:
    if isinstance(value, list):
        for item in value:
            name, declared_spec, declared_version = _dependency_record_parts(item)
            _record_dependency(
                records,
                name,
                declaration_key,
                declaration_source,
                declared_spec,
                declared_version,
            )
    elif isinstance(value, dict):
        for key, item in value.items():
            name, declared_spec, declared_version = _dependency_record_parts(item, fallback_name=str(key))
            _record_dependency(
                records,
                name,
                declaration_key,
                declaration_source,
                declared_spec,
                declared_version,
            )


def _dependency_record_parts(
    value: Any,
    *,
    fallback_name: str | None = None,
) -> tuple[str, str | None, str | None]:
    if isinstance(value, str):
        name = fallback_name or _dependency_name_from_value(value)
        declared_version = _exact_version_from_spec(value)
        if fallback_name and declared_version is None and not _looks_like_version_range(value):
            declared_version = value
        return name, value, declared_version
    if isinstance(value, dict):
        name = str(value.get("name") or fallback_name or "")
        version = value.get("version")
        spec = value.get("spec") or value.get("requirement") or version
        return name, str(spec) if spec is not None else None, str(version) if version is not None else None
    return fallback_name or "", None, None


def _record_dependency(
    records: dict[str, dict[str, Any]],
    name: str,
    declaration_key: str,
    declaration_source: str,
    declared_spec: str | None,
    declared_version: str | None,
) -> None:
    if not name:
        return
    record = records.setdefault(
        name,
        {
            "declaration_keys": set(),
            "declaration_sources": set(),
            "declared_specs": set(),
            "declared_versions": set(),
            "realization_version": None,
            "realization_sha256": None,
            "realization_candidates": set(),
        },
    )
    record["declaration_keys"].add(declaration_key)
    record["declaration_sources"].add(declaration_source)
    if declared_spec:
        record["declared_specs"].add(declared_spec)
    if declared_version:
        record["declared_versions"].add(declared_version)


def _collect_realization_records(records: dict[str, dict[str, Any]], value: Any) -> None:
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                _record_realization(records, item.get("name"), item)
    elif isinstance(value, dict):
        for name, item in value.items():
            if isinstance(item, dict):
                _record_realization(records, name, item)


def _record_realization(records: dict[str, dict[str, Any]], name_value: Any, item: dict[str, Any]) -> None:
    name = str(name_value or "")
    version = item.get("version")
    sha256 = item.get("sha256")
    if not name or not version or not sha256:
        return
    record = records.setdefault(
        name,
        {
            "declaration_keys": set(),
            "declaration_sources": set(),
            "declared_specs": set(),
            "declared_versions": set(),
            "realization_version": None,
            "realization_sha256": None,
            "realization_candidates": set(),
        },
    )
    realization = (str(version), str(sha256))
    record["realization_candidates"].add(realization)
    candidates = sorted(record["realization_candidates"])
    record["realization_version"] = candidates[0][0]
    record["realization_sha256"] = candidates[0][1]


def _exact_version_from_spec(spec: str) -> str | None:
    if "==" not in spec:
        return None
    return spec.split("==", 1)[1].split(",", 1)[0].strip() or None


def _looks_like_version_range(value: str) -> bool:
    return any(operator in value for operator in ["<", ">", "=", "~", "!"])


def _dependency_evidence_unsafe_admission_blockers(blockers: list[str]) -> list[str]:
    return [
        blocker
        for blocker in blockers
        if blocker in DEPENDENCY_EVIDENCE_UNSAFE_ADMISSION_BLOCKERS
    ]


def _dependency_evidence_manifest_path(
    candidate_id: str,
    source_sha256: str | None,
    runs_dir: Path,
) -> tuple[Path | None, str | None]:
    if source_sha256 is None:
        return None, None
    path = (
        runs_dir
        / "admission_dependency_evidence"
        / candidate_id
        / source_sha256
        / "dependency_plan.json"
    )
    return _safe_runs_child_path(path, runs_dir)


def _safe_runs_child_path(path: Path, runs_dir: Path) -> tuple[Path | None, str | None]:
    try:
        resolved_runs = runs_dir.resolve()
        resolved_path = path.resolve(strict=False)
        resolved_path.relative_to(resolved_runs)
        path.parent.resolve(strict=False).relative_to(resolved_runs)
    except (OSError, RuntimeError, ValueError):
        return None, "dependency_evidence_manifest_path_escape"
    if _path_has_existing_symlink_component(path.parent, runs_dir):
        return None, "dependency_evidence_manifest_path_escape"
    return path, None


def _path_has_existing_symlink_component(path: Path, base: Path) -> bool:
    try:
        relative = path.resolve(strict=False).relative_to(base.resolve())
    except (OSError, RuntimeError, ValueError):
        return True
    current = base
    for part in relative.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            return True
    return False


def _dependency_plan_digest(
    *,
    candidate_id: str,
    source_path: Path | None,
    source_sha256: str | None,
    target_path: Path | None,
    manifest_path: Path | None,
    normalized_dependencies: list[AdmissionDependencyInstallItem],
) -> str:
    payload = {
        "candidate_id": candidate_id,
        "source_skill_path": str(source_path) if source_path is not None else None,
        "source_sha256": source_sha256,
        "target_skill_path": str(target_path) if target_path is not None else None,
        "evidence_manifest_path": str(manifest_path) if manifest_path is not None else None,
        "policy": "no_write_dependency_evidence_only",
        "install_supported": False,
        "install_attempted": False,
        "dependencies_installed": False,
        "normalized_dependencies": [
            item.model_dump(mode="json") for item in normalized_dependencies
        ],
    }
    return hashlib.sha256(_stable_json_bytes(payload)).hexdigest()


def _prepare_dependency_evidence_manifest(
    *,
    candidate_id: str,
    source_path: Path | None,
    source_sha256: str | None,
    target_path: Path | None,
    manifest_path: Path | None,
    runs_dir: Path,
    normalized_dependencies: list[AdmissionDependencyInstallItem],
    dependency_blockers: list[str],
    dependency_plan_digest: str,
) -> tuple[list[str], str | None, bool, bool]:
    if source_path is None or source_sha256 is None:
        return ["source_skill_missing"], None, False, False
    if manifest_path is None:
        return ["dependency_evidence_manifest_path_missing"], None, False, False
    safe_manifest_path, path_blocker = _safe_runs_child_path(manifest_path, runs_dir)
    if path_blocker is not None or safe_manifest_path is None:
        return [path_blocker or "dependency_evidence_manifest_path_escape"], None, False, False
    manifest_path = safe_manifest_path
    manifest = {
        "schema_version": 1,
        "candidate_id": candidate_id,
        "source_skill_path": str(source_path),
        "source_sha256": source_sha256,
        "target_skill_path": str(target_path) if target_path is not None else None,
        "policy": "no_write_dependency_evidence_only",
        "install_supported": False,
        "install_attempted": False,
        "dependencies_installed": False,
        "normalized_dependencies": [
            item.model_dump(mode="json") for item in normalized_dependencies
        ],
        "dependency_blockers": list(dependency_blockers),
        "dependency_plan_digest": dependency_plan_digest,
    }
    content = _stable_json_bytes(manifest, trailing_newline=True)
    manifest_sha256 = hashlib.sha256(content).hexdigest()
    created, blocker = _retain_matching_file(
        manifest_path,
        content,
        manifest_sha256,
        mismatch_blocker="dependency_evidence_manifest_hash_mismatch",
        write_blocker="dependency_evidence_manifest_write_failed",
    )
    if blocker is not None:
        return [blocker], None, False, False
    return [], manifest_sha256, created, True


def _stable_json_bytes(payload: dict[str, Any], *, trailing_newline: bool = False) -> bytes:
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    if trailing_newline:
        text += "\n"
    return text.encode("utf-8")


def _find_dependency_approval_resolution(
    *,
    dependency_plan_digest: str | None,
    candidate_id: str,
    runs_dir: Path,
    dependency_approval_id: str | None,
) -> _PlanApprovalEvidence:
    if not dependency_approval_id:
        return _PlanApprovalEvidence(False, "", resolution_id=None)
    if dependency_plan_digest is None:
        return _PlanApprovalEvidence(False, "dependency_plan_digest_missing", resolution_id=dependency_approval_id)
    try:
        ledger = load_input_request_resolution_ledger(runs_dir)
    except InputResolutionLedgerError:
        return _PlanApprovalEvidence(False, "dependency_plan_approval_invalid", resolution_id=dependency_approval_id)
    matches = [
        record
        for record in ledger.resolutions
        if (
            (record.id == dependency_approval_id or record.input_request_id == dependency_approval_id)
            and record.decision == "approve_review"
            and record.status == "resolved"
            and record.source_request.kind == "durable_admission_review"
            and record.source_request.related_candidate_id == candidate_id
        )
    ]
    if not matches:
        return _PlanApprovalEvidence(False, "dependency_plan_approval_invalid", resolution_id=dependency_approval_id)

    mismatch_seen: _PlanApprovalEvidence | None = None
    expired_seen: _PlanApprovalEvidence | None = None
    missing_expiry_seen: _PlanApprovalEvidence | None = None
    for record in reversed(matches):
        digest = _note_token(record.notes, "dependency_plan_digest")
        expires_at = _note_token(record.notes, "expires_at")
        resolution_id = record.id
        if digest != dependency_plan_digest:
            mismatch_seen = _PlanApprovalEvidence(
                False,
                "dependency_plan_approval_mismatch",
                resolution_id=resolution_id,
                digest=digest,
                expires_at=expires_at,
            )
            continue
        if not expires_at:
            missing_expiry_seen = _PlanApprovalEvidence(
                False,
                "dependency_plan_approval_expiry_missing",
                resolution_id=resolution_id,
                digest=digest,
            )
            continue
        if _approval_expired(expires_at):
            expired_seen = _PlanApprovalEvidence(
                False,
                "dependency_plan_approval_expired",
                resolution_id=resolution_id,
                digest=digest,
                expires_at=expires_at,
            )
            continue
        return _PlanApprovalEvidence(
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
        or _PlanApprovalEvidence(False, "dependency_plan_approval_invalid", resolution_id=dependency_approval_id)
    )


def _permission_diff_item(
    *,
    class_name: str,
    current_enabled: bool,
    requested_enabled: bool,
) -> AdmissionPermissionDiffItem:
    change = "unchanged"
    if requested_enabled and not current_enabled:
        change = "added"
    elif current_enabled and not requested_enabled:
        change = "removed"
    return AdmissionPermissionDiffItem(
        class_name=class_name,
        current_enabled=current_enabled,
        requested_enabled=requested_enabled,
        change=change,
        approval_required=change == "added",
    )


def _selected_source_artifact(
    report: AdmissionPlanReport,
) -> AdmissionSourceArtifact | None:
    if report.selected_source_artifact:
        for artifact in report.source_artifacts:
            if artifact.skill_path == report.selected_source_artifact:
                return artifact
    return report.source_artifacts[0] if report.source_artifacts else None


def _current_permissions(report: AdmissionPlanReport) -> dict[str, bool]:
    collision = report.durable_registry.name_collision or {}
    permissions = collision.get("permissions")
    if isinstance(permissions, dict):
        return {str(key): bool(value) for key, value in permissions.items()}
    return {}


def _current_tools(report: AdmissionPlanReport) -> list[str]:
    collision = report.durable_registry.name_collision or {}
    tools = collision.get("allowed_tools")
    if isinstance(tools, list):
        return [str(tool) for tool in tools]
    return []


@dataclass(frozen=True)
class _PlanApprovalEvidence:
    verified: bool
    blocker: str
    resolution_id: str | None = None
    digest: str | None = None
    expires_at: str | None = None


def _find_plan_approval_resolution(
    *,
    plan_digest: str | None,
    candidate_id: str,
    runs_dir: Path,
    plan_approval_id: str | None,
) -> _PlanApprovalEvidence:
    if plan_digest is None:
        return _PlanApprovalEvidence(False, "plan_digest_missing")
    try:
        ledger = load_input_request_resolution_ledger(runs_dir)
    except InputResolutionLedgerError:
        return _PlanApprovalEvidence(False, "plan_digest_approval_missing")

    matches = [
        record
        for record in ledger.resolutions
        if (
            (plan_approval_id is None or record.id == plan_approval_id or record.input_request_id == plan_approval_id)
            and record.decision == "approve_review"
            and record.status == "resolved"
            and record.source_request.kind == "durable_admission_review"
            and record.source_request.related_candidate_id == candidate_id
        )
    ]
    if not matches:
        return _PlanApprovalEvidence(
            False,
            "plan_digest_approval_invalid" if plan_approval_id else "plan_digest_approval_missing",
            resolution_id=plan_approval_id,
        )

    mismatch_seen: _PlanApprovalEvidence | None = None
    expired_seen: _PlanApprovalEvidence | None = None
    missing_expiry_seen: _PlanApprovalEvidence | None = None
    for record in reversed(matches):
        digest = _note_token(record.notes, "plan_digest")
        expires_at = _note_token(record.notes, "expires_at")
        resolution_id = record.id
        if digest != plan_digest:
            mismatch_seen = _PlanApprovalEvidence(
                False,
                "plan_digest_approval_mismatch",
                resolution_id=resolution_id,
                digest=digest,
                expires_at=expires_at,
            )
            continue
        if not expires_at:
            missing_expiry_seen = _PlanApprovalEvidence(
                False,
                "plan_digest_approval_expiry_missing",
                resolution_id=resolution_id,
                digest=digest,
            )
            continue
        if _approval_expired(expires_at):
            expired_seen = _PlanApprovalEvidence(
                False,
                "plan_digest_approval_expired",
                resolution_id=resolution_id,
                digest=digest,
                expires_at=expires_at,
            )
            continue
        return _PlanApprovalEvidence(
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
        or _PlanApprovalEvidence(False, "plan_digest_approval_invalid", resolution_id=plan_approval_id)
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


def _plan_digest(
    *,
    candidate_id: str,
    operation: str,
    source_path: Path | None,
    source_sha256: str | None,
    target_dir: Path | None,
    target_path: Path | None,
    snapshot_dir: Path | None,
    snapshot_path: Path | None,
    destination_stage_dir: Path | None,
    destination_stage_path: Path | None,
    collision_policy: str,
    permission_approval_id: str | None,
    permission_dependency_diff: AdmissionPermissionDependencyDiff,
    permission_widening: list[str],
    dependency_install_contract: AdmissionDependencyInstallContract,
    prepare_write_evidence: bool,
    expected_source_sha256: str | None,
    prepare_dependency_evidence: bool,
    expected_dependency_plan_digest: str | None,
    dependency_approval_id: str | None,
) -> str:
    payload: dict[str, Any] = {
        "candidate_id": candidate_id,
        "operation": operation,
        "source_skill_path": str(source_path) if source_path is not None else None,
        "source_sha256": source_sha256,
        "target_skill_dir": str(target_dir) if target_dir is not None else None,
        "target_skill_path": str(target_path) if target_path is not None else None,
        "snapshot_dir": str(snapshot_dir) if snapshot_dir is not None else None,
        "snapshot_skill_path": str(snapshot_path) if snapshot_path is not None else None,
        "snapshot_sha256": source_sha256,
        "destination_stage_dir": (
            str(destination_stage_dir) if destination_stage_dir is not None else None
        ),
        "destination_stage_skill_path": (
            str(destination_stage_path) if destination_stage_path is not None else None
        ),
        "collision_policy": collision_policy,
        "permission_policy": "block_widening_without_approval",
        "permission_approval_id": permission_approval_id,
        "permission_dependency_diff": permission_dependency_diff.model_dump(mode="json"),
        "permission_widening": sorted(permission_widening),
        "dependency_install_contract": {
            "policy": dependency_install_contract.policy,
            "schema_version": dependency_install_contract.schema_version,
            "dependency_plan_digest": dependency_install_contract.dependency_plan_digest,
            "evidence_manifest_path": dependency_install_contract.evidence_manifest_path,
            "normalized_dependencies": [
                item.model_dump(mode="json")
                for item in dependency_install_contract.normalized_dependencies
            ],
            "install_supported": dependency_install_contract.install_supported,
            "install_attempted": dependency_install_contract.install_attempted,
            "dependencies_installed": dependency_install_contract.dependencies_installed,
        },
        "prepare_write_evidence": prepare_write_evidence,
        "expected_source_sha256": expected_source_sha256,
        "prepare_dependency_evidence": prepare_dependency_evidence,
        "expected_dependency_plan_digest": expected_dependency_plan_digest,
        "dependency_approval_id": dependency_approval_id,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _snapshot_paths(
    candidate_id: str,
    source_sha256: str | None,
    runs_dir: Path,
) -> tuple[Path | None, Path | None]:
    if source_sha256 is None:
        return None, None
    snapshot_dir = runs_dir / "admission_snapshots" / candidate_id / source_sha256
    return snapshot_dir, snapshot_dir / "SKILL.md"


def _destination_stage_paths(
    candidate_id: str,
    source_sha256: str | None,
    target_dir: Path | None,
    runs_dir: Path,
) -> tuple[Path | None, Path | None]:
    if source_sha256 is None or target_dir is None:
        return None, None
    stage_dir = (
        runs_dir
        / "admission_staging"
        / candidate_id
        / source_sha256
        / "skills"
        / target_dir.name
    )
    return stage_dir, stage_dir / "SKILL.md"


@dataclass
class _WriteEvidenceState:
    prepare_write_evidence: bool
    expected_source_sha256: str | None
    source_hash_verified: bool
    source_snapshot_created: bool = False
    source_snapshot_retained: bool = False
    destination_stage_dir: str | None = None
    destination_stage_skill_path: str | None = None
    destination_stage_sha256: str | None = None
    destination_stage_created: bool = False


def _empty_evidence_state(
    *,
    prepare_write_evidence: bool,
    expected_source_sha256: str | None,
    source_hash_verified: bool,
    destination_stage_dir: Path | None,
    destination_stage_path: Path | None,
) -> _WriteEvidenceState:
    return _WriteEvidenceState(
        prepare_write_evidence=prepare_write_evidence,
        expected_source_sha256=expected_source_sha256,
        source_hash_verified=source_hash_verified,
        destination_stage_dir=(
            str(destination_stage_dir) if destination_stage_dir is not None else None
        ),
        destination_stage_skill_path=(
            str(destination_stage_path) if destination_stage_path is not None else None
        ),
    )


def _prepare_write_evidence(
    *,
    source_path: Path | None,
    source_sha256: str | None,
    snapshot_path: Path | None,
    destination_stage_path: Path | None,
    state: _WriteEvidenceState,
) -> tuple[list[str], _WriteEvidenceState]:
    if source_path is None or source_sha256 is None:
        return ["source_skill_missing"], state
    if snapshot_path is None or destination_stage_path is None:
        return ["destination_stage_path_missing"], state

    try:
        source_bytes = source_path.read_bytes()
    except OSError:
        return ["source_skill_unreadable"], state

    snapshot_created, snapshot_blocker = _retain_matching_file(
        snapshot_path,
        source_bytes,
        source_sha256,
        mismatch_blocker="retained_snapshot_hash_mismatch",
        write_blocker="source_snapshot_retention_failed",
    )
    if snapshot_blocker is not None:
        return [snapshot_blocker], state
    state.source_snapshot_created = snapshot_created
    state.source_snapshot_retained = True

    staged_created, staged_blocker = _retain_matching_file(
        destination_stage_path,
        source_bytes,
        source_sha256,
        mismatch_blocker="destination_stage_hash_mismatch",
        write_blocker="destination_stage_write_failed",
    )
    if staged_blocker is not None:
        return [staged_blocker], state
    state.destination_stage_created = staged_created
    state.destination_stage_sha256 = source_sha256
    return [], state


def _retain_matching_file(
    path: Path,
    content: bytes,
    expected_sha256: str,
    *,
    mismatch_blocker: str,
    write_blocker: str,
) -> tuple[bool, str | None]:
    if path.exists():
        return (False, None) if _sha256(path) == expected_sha256 else (False, mismatch_blocker)
    try:
        _atomic_write_bytes(path, content)
    except OSError:
        return False, write_blocker
    return True, None


def _atomic_write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    replaced = False
    try:
        with NamedTemporaryFile(dir=path.parent, delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
        temp_path.replace(path)
        replaced = True
    finally:
        if temp_path is not None and not replaced and temp_path.exists():
            temp_path.unlink()


def _only_replaceable_collision(
    blockers: list[str],
    *,
    name_collision: bool,
    collision_policy: str,
) -> bool:
    return (
        name_collision
        and collision_policy == "allow_replace_with_approval"
        and set(blockers) == {"durable_name_collision"}
    )


def _write_operation(
    *,
    blockers: list[str],
    name_collision: bool,
    collision_policy: str,
) -> DurableAdmissionWriteOperation:
    if blockers:
        return "blocked"
    if name_collision and collision_policy == "allow_replace_with_approval":
        return "replace_existing_skill"
    return "copy_new_skill"


def _blocked_outcome(blockers: list[str]) -> DurableAdmissionPreviewOutcome:
    if any(blocker in APPROVAL_BLOCKERS for blocker in blockers):
        return "approval_required"
    return "blocked"


def _plan_blockers_for_digest(
    blockers: list[str],
    *,
    name_collision: bool,
    collision_policy: str,
) -> list[str]:
    plan_blockers = [blocker for blocker in blockers if blocker not in APPROVAL_BLOCKERS]
    if name_collision and collision_policy == "allow_replace_with_approval":
        plan_blockers = [
            blocker for blocker in plan_blockers if blocker != "durable_name_collision"
        ]
    return plan_blockers


def _next_steps(ready: bool) -> list[str]:
    if ready:
        return [
            "Review the target path and source fingerprint.",
            "Future install/copy remains disabled until a separate write-mode slice exists.",
        ]
    return [
        "Resolve admission blockers and record required human review evidence.",
        "Record approve_review notes with plan_digest=<digest> and expires_at=<timestamp> before any future write-mode work.",
        "Rerun admit-candidate --dry-run before any future write-mode work.",
    ]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
