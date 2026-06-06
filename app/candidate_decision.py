from __future__ import annotations

from pathlib import Path

from app.models import (
    CandidateDecision,
    CandidateDecisionReport,
    CandidateDecisionWhy,
    SkillReceiptProof,
    StableReadinessCheck,
)
from app.stable_readiness import StableReadinessError, build_stable_readiness_report


class CandidateDecisionError(RuntimeError):
    pass


_DENY_BLOCKERS = {
    "candidate_blocked",
    "candidate_duplicate",
    "negative_evidence_present",
    "durable_skill_name_conflict",
}
_ASK_BLOCKERS = {
    "candidate_not_promoted",
    "candidate_promotion_evidence_missing",
    "durable_review_resolution_missing",
    "plan_digest_approval_missing",
    "plan_digest_approval_invalid",
    "plan_digest_approval_mismatch",
    "plan_digest_approval_expiry_missing",
    "plan_digest_approval_expired",
}
_DEFER_BLOCKERS = {
    "dependency_install_unsupported",
    "write_mode_rollback_not_implemented",
}


def build_candidate_decision_report(
    candidate_id: str,
    *,
    runs_dir: Path,
    skills_dir: Path,
    baseline_run_id: str | None = None,
    treatment_run_id: str | None = None,
    required_successful_temporary_uses: int = 10,
) -> CandidateDecisionReport:
    try:
        stable_readiness = build_stable_readiness_report(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            baseline_run_id=baseline_run_id,
            treatment_run_id=treatment_run_id,
            required_successful_temporary_uses=required_successful_temporary_uses,
        )
    except StableReadinessError as exc:
        raise CandidateDecisionError(str(exc)) from exc

    why = _why_items(stable_readiness)
    decision, reason = _decision(why, stable_readiness.ready_for_stable_review)
    blockers = _unique([blocker for item in why for blocker in item.blockers])
    warnings = _unique([warning for item in why for warning in item.warnings])
    next_command = f"skill-agent stable-readiness {candidate_id}"

    return CandidateDecisionReport(
        candidate_id=stable_readiness.candidate_id,
        skill_name=stable_readiness.skill_name,
        capability=stable_readiness.capability,
        decision=decision,
        decision_reason=reason,
        why=why,
        stable_readiness=stable_readiness,
        blockers=blockers,
        warnings=warnings,
        next_command=next_command,
        next_steps=_next_steps(decision, next_command),
        source_reports=_source_reports(stable_readiness),
    )


def _why_items(stable_readiness) -> list[CandidateDecisionWhy]:
    items = [
        _why_from_stable_check(check)
        for check in stable_readiness.checks
        if check.status != "pass"
    ]
    if stable_readiness.ready_for_stable_review:
        items.append(
            CandidateDecisionWhy(
                source_report="stable-readiness",
                signal="stable_readiness",
                status=stable_readiness.outcome,
                summary=(
                    "Candidate is ready for human stable review, but this report "
                    "does not authorize stable promotion or routing."
                ),
                blockers=[
                    "stable_review_authorization_unavailable",
                    "stable_routing_disabled",
                ],
            )
        )

    receipt = stable_readiness.skill_receipt
    if receipt is not None:
        items.extend(
            _why_from_receipt_proof(proof)
            for proof in receipt.proofs
            if proof.status != "present"
        )

    negative = stable_readiness.negative_evidence
    if negative is not None and negative.evidence_count:
        items.append(
            CandidateDecisionWhy(
                source_report="negative-evidence",
                signal="negative_evidence",
                status="present",
                summary="Negative or limiting evidence is visible for this candidate.",
                evidence_refs=[item.id for item in negative.items],
                blockers=[item.evidence_type for item in negative.items],
                warnings=list(negative.counts_by_type),
            )
        )

    return _dedupe_why(items)


def _why_from_stable_check(check: StableReadinessCheck) -> CandidateDecisionWhy:
    return CandidateDecisionWhy(
        source_report="stable-readiness",
        signal=check.category,
        status=check.status,
        summary=check.summary,
        evidence_refs=list(check.evidence_refs),
        blockers=list(check.blockers),
        warnings=list(check.warnings),
    )


def _why_from_receipt_proof(proof: SkillReceiptProof) -> CandidateDecisionWhy:
    return CandidateDecisionWhy(
        source_report="skill-receipt",
        signal=f"receipt:{proof.category}",
        status=proof.status,
        summary=proof.summary,
        evidence_refs=list(proof.evidence_refs),
        blockers=list(proof.blockers),
        warnings=list(proof.warnings),
    )


def _decision(
    why: list[CandidateDecisionWhy],
    ready_for_stable_review: bool,
) -> tuple[CandidateDecision, str]:
    blockers = {blocker for item in why for blocker in item.blockers}
    statuses = {item.status for item in why}

    if blockers & _DENY_BLOCKERS or any(
        blocker.startswith("resolution_reject")
        or blocker.startswith("resolution_block")
        for blocker in blockers
    ):
        return "deny", "Blocking or negative evidence should keep this candidate out of stable review."
    if "dependency_install_unsupported" in blockers:
        return "defer", "Dependency realization is visible, but dependency installation remains intentionally unsupported."
    if blockers & _ASK_BLOCKERS:
        return "ask_human", "Human review or exact digest-bound approval is missing."
    if blockers & _DEFER_BLOCKERS:
        return "defer", "The strongest current proof still depends on intentionally unavailable authority."
    if ready_for_stable_review:
        return "defer", "Stable-review evidence is ready, but stable promotion and routing remain unavailable."
    if "blocked" in statuses or "blocker" in statuses:
        return "test_more", "A proof category is blocked but does not authorize denial by itself."
    return "test_more", "More candidate evidence is needed before a human stable-review decision."


def _next_steps(decision: CandidateDecision, next_command: str) -> list[str]:
    if decision == "deny":
        return [
            "Resolve or explicitly reject the blocking evidence before revisiting this candidate.",
            f"Inspect source proof with `{next_command}`.",
        ]
    if decision == "ask_human":
        return [
            "Ask a human for the missing review or exact digest-bound approval.",
            f"Refresh the source proof with `{next_command}` after approval evidence changes.",
        ]
    if decision == "defer":
        return [
            "Do not promote, route, install, or widen permissions from this report.",
            f"Use `{next_command}` as the source stable-review rehearsal.",
        ]
    return [
        "Gather or repair the missing proof before requesting stable review.",
        f"Rerun `{next_command}` after candidate evidence changes.",
    ]


def _source_reports(stable_readiness) -> list[str]:
    reports = ["stable-readiness"]
    if stable_readiness.skill_receipt is not None:
        reports.extend(["skill-receipt", "candidate-usefulness", "admit-candidate"])
    if stable_readiness.negative_evidence is not None:
        reports.append("negative-evidence")
    return _unique(reports)


def _dedupe_why(items: list[CandidateDecisionWhy]) -> list[CandidateDecisionWhy]:
    seen: set[tuple[str, str, str, str]] = set()
    deduped: list[CandidateDecisionWhy] = []
    for item in items:
        key = (item.source_report, item.signal, item.status, item.summary)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
