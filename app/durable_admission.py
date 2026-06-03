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
)


def build_durable_admission_preview(
    candidate_id: str,
    *,
    runs_dir: Path,
    skills_dir: Path,
    dry_run: bool = True,
) -> DurableAdmissionPreviewReport:
    if not dry_run:
        raise AdmissionPlanError(
            "durable admission mutation is not implemented; rerun with --dry-run"
        )

    admission_plan = build_admission_plan(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=skills_dir,
    )
    source_path = _selected_source_path(admission_plan)
    target_dir, target_path = _target_paths(admission_plan, skills_dir)
    blockers = list(admission_plan.blockers)
    required_human_records = [
        "promotion_approved_by",
        "promotion_approved_at",
        "durable_admission_review approve_review resolution",
    ]

    if not admission_plan.ready_for_durable_review:
        blockers.append(f"admission_plan_outcome:{admission_plan.outcome}")
    elif not _has_approve_review_resolution(admission_plan, runs_dir):
        blockers.append("durable_review_resolution_missing")

    ready = not blockers
    return DurableAdmissionPreviewReport(
        candidate_id=candidate_id,
        outcome="ready_for_mutation_preview" if ready else _blocked_outcome(blockers),
        ready_for_mutation_preview=ready,
        source_skill_path=str(source_path) if source_path is not None else None,
        source_sha256=_sha256(source_path) if source_path is not None else None,
        target_skill_dir=str(target_dir) if target_dir is not None else None,
        target_skill_path=str(target_path) if target_path is not None else None,
        required_human_records=required_human_records,
        blockers=_unique(blockers),
        warnings=list(admission_plan.warnings),
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
    if report.input_request is None:
        return False
    try:
        ledger = load_input_request_resolution_ledger(runs_dir)
    except InputResolutionLedgerError:
        return False
    resolution = latest_input_request_resolutions(ledger).get(report.input_request.id)
    return (
        resolution is not None
        and resolution.decision == "approve_review"
        and resolution.status == "resolved"
    )


def _sha256(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


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
