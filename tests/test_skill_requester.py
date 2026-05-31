from __future__ import annotations

from app.models import BestMatch, RouteDecision
from app.skill_requester import create_skill_request


def test_create_contradiction_skill_request_contract():
    decision = RouteDecision(
        capability="detect contradictions",
        decision="REQUEST_SKILL",
        reason="No existing skill met threshold for capability 'detect contradictions'.",
        best_match=BestMatch(skill_name="compare-claims", score=0.35, coverage="partial"),
        risk_level="low",
    )

    request = create_skill_request("task_test", decision)

    assert request.id.startswith("skillreq_")
    assert request.task_id == "task_test"
    assert request.desired_skill_name == "detect-contradictions"
    assert request.input_schema == {"claims": "array"}
    assert "contradictions" in request.output_schema
    assert request.risk_level == "medium"
    assert not request.approval_required
    assert request.status == "requested"


def test_fallback_skill_request_name_preserves_registry_name_contract():
    decision = RouteDecision(
        capability="!!!",
        decision="REQUEST_SKILL",
        reason="No existing skill met threshold.",
        best_match=BestMatch(skill_name=None, score=0.0, coverage="none"),
        risk_level="low",
    )

    request = create_skill_request("task_test", decision)

    assert request.desired_skill_name == "requested-skill"
