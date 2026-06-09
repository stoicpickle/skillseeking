from __future__ import annotations

import hashlib
import re

from app.capability_catalog import get_capability_definition
from app.models import (
    ApprovalGate,
    GovernorDecision,
    RouteDecision,
    SkillRequest,
    SkillRequestControlSummary,
)

SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


PROMOTION_EVIDENCE = [
    "Metadata validation passes",
    "Input and output contracts are explicit",
    "Validation examples or tests pass",
    "Temporary use succeeds on the triggering task",
    "Human approval is recorded before durable promotion",
]


def create_skill_request(
    task_id: str, decision: RouteDecision, governor_decision: GovernorDecision | None = None
) -> SkillRequest:
    definition = get_capability_definition(decision.capability)
    desired_name = definition.desired_skill_name if definition else _desired_skill_name(decision.capability)
    request_id = _request_id(task_id, decision.capability)
    control_summary = (
        create_control_summary(decision, governor_decision)
        if governor_decision is not None
        else None
    )

    if definition is not None:
        return SkillRequest(
            id=request_id,
            task_id=task_id,
            missing_capability=decision.capability,
            reason=decision.reason,
            desired_skill_name=desired_name,
            input_schema=dict(definition.input_schema),
            output_schema=dict(definition.output_schema),
            success_criteria=list(definition.success_criteria),
            failure_modes=list(definition.failure_modes),
            risk_level=definition.risk_level,
            approval_required=definition.approval_required or decision.requires_human_approval,
            control_summary=control_summary,
        )

    return SkillRequest(
        id=request_id,
        task_id=task_id,
        missing_capability=decision.capability,
        reason=decision.reason,
        desired_skill_name=desired_name,
        input_schema={"input": "object"},
        output_schema={"result": "object", "confidence": "number"},
        success_criteria=[
            "Defines a repeatable procedure",
            "Accepts the declared input schema",
            "Returns the declared output schema",
            "Fails cleanly when input is insufficient",
        ],
        failure_modes=[
            "If the capability is too broad, request a narrower skill",
            "If an existing skill can be adapted, do not create a duplicate",
        ],
        risk_level=decision.risk_level,
        approval_required=decision.requires_human_approval,
        control_summary=control_summary,
    )


def create_control_summary(
    decision: RouteDecision, governor_decision: GovernorDecision
) -> SkillRequestControlSummary:
    if governor_decision.capability != decision.capability:
        raise ValueError(
            "governor decision capability does not match route decision capability: "
            f"{governor_decision.capability!r} != {decision.capability!r}"
        )
    return SkillRequestControlSummary(
        governor_decision=governor_decision.decision,
        dominant_signal=governor_decision.dominant_signal,
        confidence=governor_decision.confidence,
        risk_level=governor_decision.risk_level,
        reversibility=governor_decision.reversibility,
        approval_required=governor_decision.approval_required,
        approval_gate=_approval_gate(decision, governor_decision),
        blocked_reason=_blocked_reason(governor_decision),
        evidence_to_promote=list(PROMOTION_EVIDENCE),
    )


def _approval_gate(
    decision: RouteDecision, governor_decision: GovernorDecision
) -> ApprovalGate:
    if governor_decision.decision == "ABORT_UNSAFE":
        return "blocked"
    if decision.requires_human_approval or governor_decision.approval_required:
        return "sandbox"
    if decision.risk_level in {"medium", "high"}:
        return "sandbox"
    return "none"


def _blocked_reason(governor_decision: GovernorDecision) -> str | None:
    if governor_decision.decision == "ABORT_UNSAFE":
        return governor_decision.reason
    return None


def _request_id(task_id: str, capability: str) -> str:
    digest = hashlib.sha1(
        f"{task_id}:{capability}".encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()[:10]
    return f"skillreq_{digest}"


def _desired_skill_name(capability: str) -> str:
    words = re.findall(r"[a-z0-9]+", capability.lower())
    if words and words[0] in {"detect", "extract", "compare", "score", "write", "validate"}:
        candidate = "-".join(words[:4])
    else:
        candidate = "-".join(words[:4]) or "requested-skill"

    if not SKILL_NAME_RE.match(candidate):
        return "requested-skill"
    return candidate
