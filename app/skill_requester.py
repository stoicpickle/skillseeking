from __future__ import annotations

import hashlib
import re

from app.models import RouteDecision, SkillRequest


def create_skill_request(task_id: str, decision: RouteDecision) -> SkillRequest:
    desired_name = _desired_skill_name(decision.capability)
    request_id = _request_id(task_id, decision.capability)

    if "contradiction" in decision.capability:
        return SkillRequest(
            id=request_id,
            task_id=task_id,
            missing_capability=decision.capability,
            reason=decision.reason,
            desired_skill_name=desired_name,
            input_schema={"claims": "array"},
            output_schema={
                "contradictions": "array",
                "confidence": "number",
                "explanation": "string",
                "source_ids": "array",
            },
            success_criteria=[
                "Finds direct contradiction between two claims",
                "Distinguishes contradiction from nuance or scope difference",
                "Preserves source IDs",
                "Returns confidence for each contradiction",
            ],
            failure_modes=[
                "If claims are unrelated, return no contradiction",
                "If scope or timing differs, mark as nuance instead of contradiction",
            ],
            risk_level="medium",
            approval_required=False,
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
        return "-".join(words[:4])
    return "-".join(words[:4]) or "requested-skill"
