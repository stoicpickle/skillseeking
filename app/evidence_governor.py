from __future__ import annotations

from pathlib import Path

from app.evidence_checkpoint import (
    EvidenceCheckpointError,
    build_evidence_checkpoint_report,
)
from app.models import (
    EvidenceGovernorRecommendation,
    EvidenceGovernorReport,
    EvidenceGovernorSignal,
)
from app.negative_evidence import build_negative_evidence_report
from app.skill_receipt import SkillReceiptError, build_skill_receipt_report


class EvidenceGovernorError(RuntimeError):
    pass


def build_evidence_governor_report(
    candidate_id: str,
    *,
    runs_dir: Path,
    skills_dir: Path,
    baseline_run_id: str | None = None,
    treatment_run_id: str | None = None,
    collision_policy: str = "block_existing",
    permission_approval_id: str | None = None,
    plan_approval_id: str | None = None,
) -> EvidenceGovernorReport:
    try:
        receipt = build_skill_receipt_report(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            baseline_run_id=baseline_run_id,
            treatment_run_id=treatment_run_id,
            collision_policy=collision_policy,
            permission_approval_id=permission_approval_id,
            plan_approval_id=plan_approval_id,
        )
        checkpoint = build_evidence_checkpoint_report(
            runs_dir=runs_dir,
            verify=True,
        )
    except (SkillReceiptError, EvidenceCheckpointError) as exc:
        raise EvidenceGovernorError(str(exc)) from exc

    negative = build_negative_evidence_report(
        runs_dir=runs_dir,
        candidate_id=candidate_id,
    )
    signals = _signals(receipt, negative, checkpoint)
    recommendation, reason = _recommendation(signals)
    blockers = _report_blockers(signals)
    warnings = _report_warnings(signals)
    return EvidenceGovernorReport(
        candidate_id=candidate_id,
        skill_name=receipt.skill_name,
        recommendation=recommendation,
        recommendation_reason=reason,
        signals=signals,
        skill_receipt=receipt,
        negative_evidence=negative,
        evidence_checkpoint=checkpoint,
        blockers=blockers,
        warnings=warnings,
        next_steps=_next_steps(recommendation),
    )


def _signals(
    receipt,
    negative,
    checkpoint,
) -> list[EvidenceGovernorSignal]:
    signals = [
        EvidenceGovernorSignal(
            name=f"receipt:{proof.category}",
            status=proof.status,
            summary=proof.summary,
            evidence_refs=list(proof.evidence_refs),
            blockers=list(proof.blockers),
            warnings=list(proof.warnings),
        )
        for proof in receipt.proofs
    ]
    negative_blockers = [
        item.evidence_type
        for item in negative.items
        if item.evidence_type in {
            "resolution_reject",
            "resolution_block",
            "candidate_blocked",
        }
    ]
    signals.append(
        EvidenceGovernorSignal(
            name="negative_evidence",
            status="blocked" if negative_blockers else "present",
            summary=(
                "Reject, block, or candidate-block evidence is present."
                if negative_blockers
                else "No reject, block, or candidate-block evidence is present for this candidate."
            ),
            evidence_refs=[item.id for item in negative.items],
            blockers=negative_blockers,
            warnings=[
                item.evidence_type
                for item in negative.items
                if item.evidence_type not in set(negative_blockers)
            ],
        )
    )
    signals.append(
        EvidenceGovernorSignal(
            name="evidence_checkpoint",
            status="present" if checkpoint.outcome == "verified" else "missing",
            summary=(
                "Current evidence matches the latest local checkpoint."
                if checkpoint.outcome == "verified"
                else "Current evidence is not verified against a local checkpoint."
            ),
            evidence_refs=[checkpoint.latest_checkpoint_hash]
            if checkpoint.latest_checkpoint_hash
            else [],
            blockers=list(checkpoint.blockers),
            warnings=list(checkpoint.warnings),
        )
    )
    return signals


def _recommendation(
    signals: list[EvidenceGovernorSignal],
) -> tuple[EvidenceGovernorRecommendation, str]:
    if _has_blocker(
        signals,
        names={"negative_evidence"},
        blocker_prefixes={
            "resolution_reject",
            "resolution_block",
            "candidate_blocked",
        },
    ):
        return "deny", "Negative reject or block evidence exists for this candidate."
    if _signal_status(signals, "receipt:utility") in {"missing", "blocked"}:
        return "test_more", "Utility proof is missing or blocked."
    if _signal_status(signals, "evidence_checkpoint") != "present":
        return "test_more", "Current evidence is not checkpoint-verified."
    if _signal_status(signals, "receipt:approval") == "missing":
        return "ask", "Human review or exact plan-digest approval is missing."
    if _has_blocker(
        signals,
        names={"receipt:reversibility"},
        blocker_prefixes={"write_mode_rollback_not_implemented"},
    ):
        return "defer", "Write-mode activation and rollback execution remain intentionally absent."
    if any(signal.status in {"missing", "partial", "blocked"} for signal in signals):
        return "test_more", "One or more proof categories remain incomplete."
    return "defer", "No active approval or install action is available from the evidence governor."


def _report_blockers(signals: list[EvidenceGovernorSignal]) -> list[str]:
    blockers: list[str] = []
    for signal in signals:
        blockers.extend(f"{signal.name}:{blocker}" for blocker in signal.blockers)
    return _unique(blockers)


def _report_warnings(signals: list[EvidenceGovernorSignal]) -> list[str]:
    warnings: list[str] = []
    for signal in signals:
        warnings.extend(f"{signal.name}:{warning}" for warning in signal.warnings)
    return _unique(warnings)


def _signal_status(signals: list[EvidenceGovernorSignal], name: str) -> str | None:
    for signal in signals:
        if signal.name == name:
            return signal.status
    return None


def _has_blocker(
    signals: list[EvidenceGovernorSignal],
    *,
    names: set[str],
    blocker_prefixes: set[str],
) -> bool:
    for signal in signals:
        if signal.name not in names:
            continue
        for blocker in signal.blockers:
            if blocker in blocker_prefixes or any(
                blocker.startswith(f"{prefix}:") for prefix in blocker_prefixes
            ):
                return True
    return False


def _next_steps(recommendation: EvidenceGovernorRecommendation) -> list[str]:
    if recommendation == "deny":
        return [
            "Keep this candidate out of durable admission until negative evidence is resolved by a human.",
            "Do not install, promote, or widen permissions from this report.",
        ]
    if recommendation == "test_more":
        return [
            "Gather or repair missing proof before requesting durable admission review.",
            "Checkpoint evidence after the new proof is present.",
        ]
    if recommendation == "ask":
        return [
            "Ask a human for the missing review or exact digest-bound approval.",
            "Keep this report advisory; it does not grant approval.",
        ]
    return [
        "Defer write-mode work until the missing infrastructure proof exists.",
        "Keep routing and durable admission unchanged.",
    ]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
