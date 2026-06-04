from __future__ import annotations

from pathlib import Path

from app.models import (
    NegativeEvidenceReport,
    SkillCandidateLedgerEntry,
    SkillReceiptReport,
    StableReadinessCheck,
    StableReadinessOutcome,
    StableReadinessReport,
)
from app.input_resolution_ledger import (
    InputResolutionLedgerError,
    load_input_request_resolution_ledger,
)
from app.negative_evidence import build_negative_evidence_report
from app.registry import SkillRegistry
from app.skill_candidate_ledger import SkillCandidateLedgerError, load_candidate_ledger
from app.skill_receipt import SkillReceiptError, build_skill_receipt_report


class StableReadinessError(RuntimeError):
    pass


DEFAULT_STABLE_SUCCESS_THRESHOLD = 10
_HARD_BLOCKERS = {
    "candidate_blocked",
    "candidate_duplicate",
    "negative_evidence_present",
    "negative_evidence_unavailable",
    "durable_skill_name_conflict",
    "receipt_blocked",
    "skill_receipt_unavailable",
}


def build_stable_readiness_report(
    candidate_id: str,
    *,
    runs_dir: Path,
    skills_dir: Path,
    baseline_run_id: str | None = None,
    treatment_run_id: str | None = None,
    required_successful_temporary_uses: int = DEFAULT_STABLE_SUCCESS_THRESHOLD,
) -> StableReadinessReport:
    if required_successful_temporary_uses < 1:
        raise StableReadinessError("required successful temporary uses must be at least 1")

    try:
        ledger = load_candidate_ledger(runs_dir)
    except SkillCandidateLedgerError as exc:
        raise StableReadinessError(str(exc)) from exc

    entry = next((item for item in ledger.entries if item.candidate_id == candidate_id), None)
    if entry is None:
        raise StableReadinessError(f"candidate not found: {candidate_id}")

    warnings: list[str] = []
    receipt = _skill_receipt(
        entry,
        runs_dir=runs_dir,
        skills_dir=skills_dir,
        baseline_run_id=baseline_run_id,
        treatment_run_id=treatment_run_id,
        warnings=warnings,
    )
    negative = build_negative_evidence_report(runs_dir=runs_dir, candidate_id=candidate_id)
    negative_source_blockers = _negative_source_blockers(runs_dir)
    checks = _checks(
        entry,
        skills_dir=skills_dir,
        receipt=receipt,
        negative=negative,
        negative_source_blockers=negative_source_blockers,
        required_successful_temporary_uses=required_successful_temporary_uses,
    )
    blockers = _unique([blocker for check in checks for blocker in check.blockers])
    warnings = _unique(warnings + [warning for check in checks for warning in check.warnings])
    outcome = _outcome(entry, blockers)

    return StableReadinessReport(
        candidate_id=entry.candidate_id,
        skill_name=entry.skill_name,
        capability=entry.capability,
        candidate_status=entry.status,
        outcome=outcome,
        ready_for_stable_review=outcome == "ready_for_stable_review",
        required_successful_temporary_uses=required_successful_temporary_uses,
        successful_temporary_uses=entry.successful_temporary_uses,
        validation_pass_count=entry.validation_pass_count,
        validation_failure_count=entry.validation_failure_count,
        checks=checks,
        skill_receipt=receipt,
        negative_evidence=negative,
        blockers=blockers,
        warnings=warnings,
        next_steps=_next_steps(outcome, blockers, required_successful_temporary_uses),
    )


def _skill_receipt(
    entry: SkillCandidateLedgerEntry,
    *,
    runs_dir: Path,
    skills_dir: Path,
    baseline_run_id: str | None,
    treatment_run_id: str | None,
    warnings: list[str],
) -> SkillReceiptReport | None:
    try:
        return build_skill_receipt_report(
            entry.candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            baseline_run_id=baseline_run_id,
            treatment_run_id=treatment_run_id,
        )
    except SkillReceiptError as exc:
        warnings.append(f"skill_receipt_unavailable:{exc}")
        return None


def _negative_source_blockers(runs_dir: Path) -> list[str]:
    try:
        load_input_request_resolution_ledger(runs_dir)
    except InputResolutionLedgerError as exc:
        return [str(exc)]
    return []


def _checks(
    entry: SkillCandidateLedgerEntry,
    *,
    skills_dir: Path,
    receipt: SkillReceiptReport | None,
    negative: NegativeEvidenceReport,
    negative_source_blockers: list[str],
    required_successful_temporary_uses: int,
) -> list[StableReadinessCheck]:
    return [
        _lifecycle_check(entry),
        _successful_use_check(entry, required_successful_temporary_uses),
        _validation_check(entry),
        _duplicate_check(entry),
        _negative_evidence_check(negative, negative_source_blockers),
        _durable_name_conflict_check(entry, skills_dir),
        _receipt_check(receipt),
    ]


def _lifecycle_check(entry: SkillCandidateLedgerEntry) -> StableReadinessCheck:
    if entry.status == "stable":
        return StableReadinessCheck(
            category="lifecycle",
            status="pass",
            summary="Candidate is already marked stable evidence in the ledger.",
        )
    if entry.status == "candidate" and _candidate_promotion_evidence_recorded(entry):
        return StableReadinessCheck(
            category="lifecycle",
            status="pass",
            summary="Candidate promotion evidence is recorded before stable review.",
            evidence_refs=[entry.promotion_approved_by or "candidate promotion recorded"],
        )
    if entry.status == "candidate":
        return StableReadinessCheck(
            category="lifecycle",
            status="missing",
            summary="Candidate status is present but promotion approval evidence is incomplete.",
            blockers=["candidate_promotion_evidence_missing"],
        )
    if entry.status == "blocked" or entry.block_reason or entry.quarantine_reason:
        return StableReadinessCheck(
            category="lifecycle",
            status="blocker",
            summary="Blocked or quarantined candidates cannot enter stable review.",
            blockers=["candidate_blocked"],
            warnings=[item for item in [entry.block_reason, entry.quarantine_reason] if item],
        )
    return StableReadinessCheck(
        category="lifecycle",
        status="missing",
        summary="Candidate must be human-promoted to candidate before stable review.",
        blockers=["candidate_not_promoted"],
    )


def _candidate_promotion_evidence_recorded(entry: SkillCandidateLedgerEntry) -> bool:
    return bool(
        entry.promotion_approved_by
        and entry.promotion_approved_at
        and entry.human_approval_required is False
    )


def _successful_use_check(
    entry: SkillCandidateLedgerEntry,
    required_successful_temporary_uses: int,
) -> StableReadinessCheck:
    evidence_refs = list(entry.evidence_run_ids)
    if entry.successful_temporary_uses >= required_successful_temporary_uses:
        return StableReadinessCheck(
            category="stable_use_threshold",
            status="pass",
            summary=(
                f"Successful temporary uses meet the stable-review threshold "
                f"({entry.successful_temporary_uses}/{required_successful_temporary_uses})."
            ),
            evidence_refs=evidence_refs,
        )
    return StableReadinessCheck(
        category="stable_use_threshold",
        status="missing",
        summary=(
            f"Stable review needs more successful temporary-use evidence "
            f"({entry.successful_temporary_uses}/{required_successful_temporary_uses})."
        ),
        evidence_refs=evidence_refs,
        blockers=["successful_temporary_uses_below_stable_threshold"],
    )


def _validation_check(entry: SkillCandidateLedgerEntry) -> StableReadinessCheck:
    blockers: list[str] = []
    warnings: list[str] = []
    if entry.validation_failure_count > 0:
        blockers.append("validation_failures_present")
    if entry.repair_requirements:
        blockers.append("candidate_repair_required")
        warnings.extend(entry.repair_requirements)
    if blockers:
        return StableReadinessCheck(
            category="validation_and_repair",
            status="blocker",
            summary="Validation failures or repair requirements block stable review.",
            blockers=blockers,
            warnings=_unique(warnings),
        )
    return StableReadinessCheck(
        category="validation_and_repair",
        status="pass",
        summary="No validation failures or repair requirements are recorded.",
        evidence_refs=[f"validation_pass_count:{entry.validation_pass_count}"],
    )


def _duplicate_check(entry: SkillCandidateLedgerEntry) -> StableReadinessCheck:
    if entry.duplicate_of or entry.duplicate_evidence:
        return StableReadinessCheck(
            category="candidate_duplicate",
            status="blocker",
            summary="Duplicate candidate evidence must be merged or resolved before stable review.",
            evidence_refs=list(entry.duplicate_evidence),
            blockers=["candidate_duplicate"],
            warnings=[entry.duplicate_of] if entry.duplicate_of else [],
        )
    return StableReadinessCheck(
        category="candidate_duplicate",
        status="pass",
        summary="No duplicate candidate evidence is recorded.",
    )


def _negative_evidence_check(
    report: NegativeEvidenceReport,
    source_blockers: list[str],
) -> StableReadinessCheck:
    if source_blockers:
        return StableReadinessCheck(
            category="negative_evidence",
            status="blocker",
            summary="Negative evidence sources could not be fully inspected.",
            blockers=["negative_evidence_unavailable"],
            warnings=source_blockers,
        )
    if report.evidence_count:
        return StableReadinessCheck(
            category="negative_evidence",
            status="blocker",
            summary="Unfavorable candidate or resolution evidence is still visible.",
            evidence_refs=[item.id for item in report.items],
            blockers=["negative_evidence_present"],
            warnings=list(report.counts_by_type),
        )
    return StableReadinessCheck(
        category="negative_evidence",
        status="pass",
        summary="No negative evidence is recorded for this candidate.",
    )


def _durable_name_conflict_check(
    entry: SkillCandidateLedgerEntry,
    skills_dir: Path,
) -> StableReadinessCheck:
    registry = SkillRegistry.load(skills_dir)
    existing = registry.get(entry.skill_name)
    rejected_paths = [
        str(rejection.path)
        for rejection in registry.rejections()
        if rejection.name == entry.skill_name or Path(rejection.path).parent.name == entry.skill_name
    ]
    if existing is not None or rejected_paths:
        return StableReadinessCheck(
            category="durable_registry_conflict",
            status="blocker",
            summary="Durable registry already contains a same-name accepted or rejected skill path.",
            evidence_refs=[
                *([str(existing.path)] if existing is not None else []),
                *rejected_paths,
            ],
            blockers=["durable_skill_name_conflict"],
        )
    return StableReadinessCheck(
        category="durable_registry_conflict",
        status="pass",
        summary="No same-name durable skill is present in the registry.",
    )


def _receipt_check(receipt: SkillReceiptReport | None) -> StableReadinessCheck:
    if receipt is None:
        return StableReadinessCheck(
            category="proof_receipt",
            status="missing",
            summary="Skill receipt could not be built from existing evidence.",
            blockers=["skill_receipt_unavailable"],
        )
    blocked = [proof.category for proof in receipt.proofs if proof.status == "blocked"]
    partial_or_missing = [
        proof.category for proof in receipt.proofs if proof.status in {"missing", "partial"}
    ]
    if blocked:
        return StableReadinessCheck(
            category="proof_receipt",
            status="blocker",
            summary="One or more receipt proof categories are blocked.",
            evidence_refs=blocked,
            blockers=["receipt_blocked"],
            warnings=partial_or_missing,
        )
    return StableReadinessCheck(
        category="proof_receipt",
        status="pass" if not partial_or_missing else "warning",
        summary=(
            "No receipt proof category is blocked; missing or partial categories remain "
            "review evidence, not stable-routing authority."
        ),
        warnings=partial_or_missing,
    )


def _outcome(
    entry: SkillCandidateLedgerEntry,
    blockers: list[str],
) -> StableReadinessOutcome:
    if entry.status == "stable":
        return "already_stable"
    if any(blocker in _HARD_BLOCKERS for blocker in blockers):
        return "blocked"
    if blockers:
        return "needs_more_evidence"
    return "ready_for_stable_review"


def _next_steps(
    outcome: StableReadinessOutcome,
    blockers: list[str],
    required_successful_temporary_uses: int,
) -> list[str]:
    if outcome == "ready_for_stable_review":
        return [
            "Use this report as advisory stable-review evidence only.",
            "Record maintainer approval before any future candidate-to-stable workflow.",
            "Keep stable routing disabled until a separate human-approved stable workflow exists.",
        ]
    if outcome == "already_stable":
        return ["Inspect monitoring, repair, or deprecation evidence before changing routing."]
    if outcome == "blocked":
        return [
            "Resolve blocked checks before stable review.",
            "Use negative-evidence and skill-receipt for the blocking proof details.",
        ]
    if "successful_temporary_uses_below_stable_threshold" in blockers:
        return [
            f"Gather at least {required_successful_temporary_uses} successful temporary-use evidence records before stable review.",
            "Rerun stable-readiness after candidate evidence changes.",
        ]
    if "candidate_not_promoted" in blockers:
        return [
            "Complete human candidate promotion before stable review.",
            "Use candidate-usefulness and skill-receipt to inspect promotion evidence.",
        ]
    return ["Resolve missing evidence before stable review."]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
