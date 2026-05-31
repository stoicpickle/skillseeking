from __future__ import annotations

import hashlib
import re

from app.capability_catalog import get_capability_definition
from app.models import RouteDecision, SkillRequest

SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def create_skill_request(task_id: str, decision: RouteDecision) -> SkillRequest:
    definition = get_capability_definition(decision.capability)
    desired_name = definition.desired_skill_name if definition else _desired_skill_name(decision.capability)
    request_id = _request_id(task_id, decision.capability)

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
    )


def _request_id(task_id: str, capability: str) -> str:
    digest = hashlib.sha1(f"{task_id}:{capability}".encode("utf-8")).hexdigest()[:10]
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
