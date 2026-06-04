from __future__ import annotations

from app.models import GovernorDecision, Reversibility, RouteDecision


def evaluate_governor(decision: RouteDecision) -> GovernorDecision:
    confidence = _confidence(decision)
    reversibility = _reversibility(decision)

    if decision.decision == "USE_SKILL":
        return GovernorDecision(
            capability=decision.capability,
            decision=decision.decision,
            confidence=confidence,
            risk_level=decision.risk_level,
            reversibility=reversibility,
            approval_required=False,
            dominant_signal="skill_match",
            reason=decision.reason,
        )
    if decision.decision == "REQUEST_SKILL":
        return GovernorDecision(
            capability=decision.capability,
            decision=decision.decision,
            confidence=confidence,
            risk_level=decision.risk_level,
            reversibility=reversibility,
            approval_required=decision.requires_human_approval,
            dominant_signal="missing_skill",
            reason=decision.reason,
        )
    if decision.decision == "ASK_HUMAN":
        return GovernorDecision(
            capability=decision.capability,
            decision=decision.decision,
            confidence=1.0,
            risk_level=decision.risk_level,
            reversibility="unknown",
            approval_required=True,
            dominant_signal="approval_required",
            reason=decision.reason,
        )
    return GovernorDecision(
        capability=decision.capability,
        decision=decision.decision,
        confidence=1.0,
        risk_level=decision.risk_level,
        reversibility="unknown",
        approval_required=False,
        dominant_signal="safety_risk",
        reason=(
            f"{decision.reason} Approval is not requested because this path is blocked, "
            "not reviewable."
        ),
    )


def _confidence(decision: RouteDecision) -> float:
    if decision.route_reason is not None:
        return decision.route_reason.score
    if decision.best_match is not None:
        return decision.best_match.score
    return 0.0


def _reversibility(decision: RouteDecision) -> Reversibility:
    if decision.risk_level == "low":
        return "reversible"
    if decision.risk_level == "medium":
        return "partially_reversible"
    if decision.risk_level == "high":
        return "unknown"
    return "unknown"
