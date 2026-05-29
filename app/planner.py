from __future__ import annotations

import hashlib

from app.models import CapabilityRequest, TaskPlan


RULES: list[tuple[tuple[str, ...], str]] = [
    (("extract claims", "claims from", "claim extraction"), "extract atomic factual claims"),
    (("compare", "differences", "similarities"), "compare claims"),
    (("source quality", "credible", "reliable", "quality notes"), "score source quality"),
    (("summary", "answer", "write", "structured summary"), "write structured answer"),
    (("validate skill", "check skill.md", "skill.md"), "validate skill markdown"),
    (("contradiction", "contradictions", "disagree"), "detect contradictions"),
]


def plan_task(task_text: str) -> TaskPlan:
    lowered = task_text.lower()
    capabilities: list[CapabilityRequest] = []
    seen: set[str] = set()

    for terms, capability in RULES:
        matched = [term for term in terms if term in lowered]
        if matched and capability not in seen:
            capabilities.append(CapabilityRequest(capability=capability, source_terms=matched))
            seen.add(capability)

    if not capabilities:
        capabilities.append(
            CapabilityRequest(capability="write structured answer", source_terms=["fallback"])
        )

    digest = hashlib.sha1(task_text.encode("utf-8")).hexdigest()[:10]
    return TaskPlan(task_id=f"task_{digest}", task=task_text, capabilities=capabilities)

