from __future__ import annotations

import hashlib
from pathlib import Path

from app.admission_plan import AdmissionPlanError, build_admission_plan
from app.input_resolution_ledger import (
    InputResolutionLedgerError,
    latest_input_request_resolutions,
    load_input_request_resolution_ledger,
)
from app.models import (
    AdmissionPlanReport,
    DurableAdmissionPreviewOutcome,
    DurableAdmissionPreviewReport,
    DurableAdmissionWriteOperation,
    DurableAdmissionWritePlan,
)


VALID_COLLISION_POLICIES: set[str] = {
    "block_existing",
    "allow_replace_with_approval",
}


def build_durable_admission_preview(
    candidate_id: str,
    *,
    runs_dir: Path,
    skills_dir: Path,
    dry_run: bool = True,
    collision_policy: str = "block_existing",
    permission_approval_id: str | None = None,
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
    source_sha256 = _sha256(source_path) if source_path is not None else None
    target_dir, target_path = _target_paths(admission_plan, skills_dir)
    snapshot_dir, snapshot_path = _snapshot_paths(candidate_id, source_sha256, runs_dir)
    blockers = list(admission_plan.blockers)
    write_blockers = list(blockers)
    warnings = list(admission_plan.warnings)
    required_human_records = [
        "promotion_approved_by",
        "promotion_approved_at",
        "durable_admission_review approve_review resolution",
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

    if replacement_approved:
        write_blockers = [
            blocker for blocker in write_blockers if blocker != "durable_name_collision"
        ]

    write_blockers = _unique(write_blockers)
    operation = _write_operation(
        blockers=write_blockers,
        name_collision=name_collision,
        collision_policy=collision_policy,
    )
    write_plan = DurableAdmissionWritePlan(
        operation=operation,
        source_skill_path=str(source_path) if source_path is not None else None,
        source_sha256=source_sha256,
        target_skill_dir=str(target_dir) if target_dir is not None else None,
        target_skill_path=str(target_path) if target_path is not None else None,
        snapshot_dir=str(snapshot_dir) if snapshot_dir is not None else None,
        snapshot_skill_path=str(snapshot_path) if snapshot_path is not None else None,
        snapshot_sha256=source_sha256,
        collision_policy=collision_policy,
        permission_approval_id=permission_approval_id,
        replacement_approved=replacement_approved,
        permission_widening_approved=permission_widening_approved,
        blockers=write_blockers,
        warnings=warnings,
    )

    blockers = _unique(blockers)
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
    if "durable_review_resolution_missing" in blockers:
        return "approval_required"
    return "blocked"


def _next_steps(ready: bool) -> list[str]:
    if ready:
        return [
            "Review the target path and source fingerprint.",
            "Future install/copy remains disabled until a separate write-mode slice exists.",
        ]
    return [
        "Resolve admission blockers and record required human review evidence.",
        "Rerun admit-candidate --dry-run before any future write-mode work.",
    ]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
