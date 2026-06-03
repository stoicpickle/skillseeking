from __future__ import annotations

from pathlib import Path

from app.admission_plan import AdmissionPlanError
from app.candidate_usefulness import (
    CandidateUsefulnessError,
    build_candidate_usefulness_report,
)
from app.durable_admission import build_durable_admission_preview
from app.models import (
    CandidateUsefulnessReport,
    DurableAdmissionPreviewReport,
    SkillReceiptProof,
    SkillReceiptReport,
)


class SkillReceiptError(RuntimeError):
    pass


def build_skill_receipt_report(
    candidate_id: str,
    *,
    runs_dir: Path,
    skills_dir: Path,
    baseline_run_id: str | None = None,
    treatment_run_id: str | None = None,
    collision_policy: str = "block_existing",
    permission_approval_id: str | None = None,
    plan_approval_id: str | None = None,
) -> SkillReceiptReport:
    try:
        usefulness = build_candidate_usefulness_report(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            baseline_run_id=baseline_run_id,
            treatment_run_id=treatment_run_id,
        )
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
    except (CandidateUsefulnessError, AdmissionPlanError) as exc:
        raise SkillReceiptError(str(exc)) from exc

    proofs = [
        _origin_proof(preview),
        _utility_proof(usefulness),
        _containment_proof(preview),
        _compatibility_proof(preview),
        _approval_proof(preview),
        _reversibility_proof(preview),
    ]
    outcome = _receipt_outcome(proofs)
    return SkillReceiptReport(
        candidate_id=candidate_id,
        skill_name=usefulness.skill_name,
        capability=usefulness.capability,
        status=str(preview.admission_plan.candidate.get("status", "")),
        outcome=outcome,
        proofs=proofs,
        candidate_usefulness=usefulness,
        durable_admission_preview=preview,
        next_steps=_next_steps(outcome, preview),
    )


def _origin_proof(preview: DurableAdmissionPreviewReport) -> SkillReceiptProof:
    blockers: list[str] = []
    evidence_refs: list[str] = []
    if preview.source_skill_path:
        evidence_refs.append(preview.source_skill_path)
    if preview.source_sha256:
        evidence_refs.append(f"sha256:{preview.source_sha256}")
    if preview.write_plan.snapshot_skill_path:
        evidence_refs.append(preview.write_plan.snapshot_skill_path)
    if not preview.source_skill_path or not preview.source_sha256:
        blockers.append("source_fingerprint_missing")
    return SkillReceiptProof(
        category="origin",
        status="present" if not blockers else "missing",
        summary="Source artifact, source hash, and future snapshot path are inspectable."
        if not blockers
        else "Source artifact or fingerprint evidence is missing.",
        evidence_refs=evidence_refs,
        blockers=blockers,
    )


def _utility_proof(usefulness: CandidateUsefulnessReport) -> SkillReceiptProof:
    evidence_refs = list(usefulness.matching_successful_run_ids)
    blockers = list(usefulness.blockers)
    warnings = list(usefulness.warnings)
    if usefulness.baseline_comparison_available:
        status = "present"
        summary = "Pinned baseline/treatment evidence is available for this candidate."
    elif usefulness.usefulness_supported:
        status = "partial"
        summary = "Temporary-skill success evidence exists, but paired baseline proof is missing."
    else:
        status = "missing" if not blockers else "blocked"
        summary = "Temporary-skill usefulness evidence is not sufficient yet."
    return SkillReceiptProof(
        category="utility",
        status=status,
        summary=summary,
        evidence_refs=evidence_refs,
        blockers=blockers,
        warnings=warnings,
    )


def _containment_proof(preview: DurableAdmissionPreviewReport) -> SkillReceiptProof:
    diff = preview.write_plan.permission_dependency_diff
    blockers = list(diff.blockers)
    evidence_refs = [
        *[f"permission:{name}" for name in diff.added_permission_classes],
        *[f"tool:{name}" for name in diff.added_tools],
        *[f"dependency:{name}" for name in diff.dependency_diff.added],
    ]
    if blockers:
        status = "blocked"
        summary = "Permission, tool, or dependency changes need more proof before admission."
    elif evidence_refs:
        status = "partial"
        summary = "Containment-impacting declarations are visible and currently unblocked."
    else:
        status = "present"
        summary = "No permission, tool, or dependency widening is declared."
    return SkillReceiptProof(
        category="containment",
        status=status,
        summary=summary,
        evidence_refs=evidence_refs,
        blockers=blockers,
        warnings=list(diff.warnings),
    )


def _compatibility_proof(preview: DurableAdmissionPreviewReport) -> SkillReceiptProof:
    blockers = [
        blocker
        for blocker in preview.write_plan.blockers
        if blocker
        not in {
            "durable_review_resolution_missing",
            "plan_digest_approval_missing",
            "plan_digest_approval_invalid",
            "plan_digest_approval_mismatch",
            "plan_digest_approval_expiry_missing",
            "plan_digest_approval_expired",
        }
    ]
    evidence_refs = [
        ref
        for ref in [
            preview.target_skill_path,
            preview.write_plan.destination_stage_skill_path,
        ]
        if ref
    ]
    return SkillReceiptProof(
        category="compatibility",
        status="present" if not blockers else "blocked",
        summary="Destination plan, collision policy, and admission blockers are inspectable.",
        evidence_refs=evidence_refs,
        blockers=blockers,
        warnings=list(preview.warnings),
    )


def _approval_proof(preview: DurableAdmissionPreviewReport) -> SkillReceiptProof:
    blockers = [
        blocker
        for blocker in preview.write_plan.blockers
        if blocker.startswith("durable_review_resolution")
        or blocker.startswith("plan_digest_approval")
    ]
    evidence_refs = [
        ref
        for ref in [
            preview.write_plan.plan_digest,
            preview.write_plan.plan_approval_id,
            preview.write_plan.plan_approval_expires_at,
        ]
        if ref
    ]
    return SkillReceiptProof(
        category="approval",
        status="present" if not blockers else "missing",
        summary="Human review and exact plan-digest approval are verified."
        if not blockers
        else "Human review or exact plan-digest approval is still missing.",
        evidence_refs=evidence_refs,
        blockers=blockers,
    )


def _reversibility_proof(preview: DurableAdmissionPreviewReport) -> SkillReceiptProof:
    evidence_refs = [
        ref
        for ref in [
            preview.write_plan.destination_stage_skill_path,
            preview.write_plan.snapshot_skill_path,
        ]
        if ref
    ]
    return SkillReceiptProof(
        category="reversibility",
        status="partial",
        summary=(
            "Snapshot and destination staging paths are visible, and "
            "shadow-rollback-plan can verify existing managed-prefix rollback "
            "evidence, but write-mode activation and rollback execution remain absent."
        ),
        evidence_refs=evidence_refs,
        blockers=["write_mode_rollback_not_implemented"],
    )


def _receipt_outcome(proofs: list[SkillReceiptProof]) -> str:
    if any(proof.status == "blocked" for proof in proofs):
        return "blocked"
    if any(proof.status in {"missing", "partial"} for proof in proofs):
        return "incomplete"
    return "ready"


def _next_steps(
    outcome: str,
    preview: DurableAdmissionPreviewReport,
) -> list[str]:
    if outcome == "ready":
        return [
            "Use this receipt as review evidence only; durable copy/install remains unavailable.",
            "Design managed shadow activation before enabling write mode.",
        ]
    steps = [
        "Resolve missing or blocked proof categories before durable admission.",
        "Use admit-candidate --dry-run to refresh the exact plan digest.",
    ]
    if preview.write_plan.plan_digest:
        steps.append(
            "Record approve_review notes with plan_digest=<digest> and expires_at=<timestamp>."
        )
    return steps
