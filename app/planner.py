from __future__ import annotations

import hashlib

from app.capability_catalog import capability_definitions
from app.models import CapabilityRequest, TaskPlan


def plan_task(task_text: str) -> TaskPlan:
    lowered = task_text.lower()
    capabilities: list[CapabilityRequest] = []
    seen: set[str] = set()

    for definition in capability_definitions():
        matched = [term for term in definition.trigger_terms if term in lowered]
        if matched and definition.name not in seen:
            capabilities.append(CapabilityRequest(capability=definition.name, source_terms=matched))
            seen.add(definition.name)

    if not capabilities:
        capabilities.append(
            CapabilityRequest(capability="write structured answer", source_terms=["fallback"])
        )

    digest = hashlib.sha1(
        task_text.encode("utf-8"),
        usedforsecurity=False,
    ).hexdigest()[:10]
    return TaskPlan(task_id=f"task_{digest}", task=task_text, capabilities=capabilities)
