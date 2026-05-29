from __future__ import annotations

from app.models import CapabilityRequest, RouteDecision
from app.registry import SkillRegistry
from app.skill_router import route_capability


def check_capabilities(
    capabilities: list[CapabilityRequest], registry: SkillRegistry
) -> list[RouteDecision]:
    return [route_capability(capability.capability, registry) for capability in capabilities]

