from __future__ import annotations

from app.capability_catalog import (
    SafetyClassification,
    classify_task_safety,
    get_capability_definition,
    safety_decision_for_capability,
)
from app.models import BestMatch, CapabilityRequest, RouteDecision
from app.registry import SkillRegistry
from app.skill_router import route_capability


def check_task_safety(task_text: str) -> RouteDecision | None:
    classification = classify_task_safety(task_text)
    if classification is None:
        return None
    return _safety_route_decision(classification)


def check_capabilities(
    capabilities: list[CapabilityRequest], registry: SkillRegistry, task_text: str | None = None
) -> list[RouteDecision]:
    preflight = check_task_safety(task_text) if task_text is not None else None
    if preflight is not None:
        return [preflight]

    decisions: list[RouteDecision] = []
    for capability in capabilities:
        safety = safety_decision_for_capability(capability.capability)
        if safety is not None:
            return [_safety_route_decision(safety)]
        decisions.append(_apply_capability_definition(route_capability(capability.capability, registry)))
    return decisions


def _safety_route_decision(classification: SafetyClassification) -> RouteDecision:
    return RouteDecision(
        capability=classification.capability,
        decision=classification.decision,
        selected_skill=None,
        reason=classification.reason,
        best_match=BestMatch(skill_name=None, score=0.0, coverage="safety"),
        risk_level=classification.risk_level,
        requires_human_approval=classification.decision == "ASK_HUMAN",
    )


def _apply_capability_definition(decision: RouteDecision) -> RouteDecision:
    definition = get_capability_definition(decision.capability)
    if definition is None or decision.decision != "REQUEST_SKILL":
        return decision
    return decision.model_copy(
        update={
            "risk_level": definition.risk_level,
            "requires_human_approval": (
                decision.requires_human_approval or definition.approval_required
            ),
        }
    )
