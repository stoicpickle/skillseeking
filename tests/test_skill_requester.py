from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import (
    BestMatch,
    GovernorDecision,
    RouteDecision,
    SkillRequest,
    SkillRequestControlSummary,
)
from app.skill_requester import create_control_summary, create_skill_request


def _governor_for(decision: RouteDecision, **overrides) -> GovernorDecision:
    payload = {
        "capability": decision.capability,
        "decision": decision.decision,
        "confidence": decision.best_match.score,
        "risk_level": decision.risk_level,
        "reversibility": "reversible" if decision.risk_level == "low" else "partially_reversible",
        "approval_required": decision.requires_human_approval,
        "dominant_signal": "missing_skill",
        "reason": decision.reason,
    }
    payload.update(overrides)
    return GovernorDecision(**payload)


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
    assert request.risk_level == "low"
    assert not request.approval_required
    assert request.control_summary is None
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


def test_create_skill_request_with_control_summary_snapshots_governor_context():
    decision = RouteDecision(
        capability="detect contradictions",
        decision="REQUEST_SKILL",
        reason="No existing skill met threshold for capability 'detect contradictions'.",
        best_match=BestMatch(skill_name="compare-claims", score=0.35, coverage="partial"),
        risk_level="low",
    )
    governor = _governor_for(decision, confidence=0.35)

    request = create_skill_request("task_test", decision, governor)

    assert request.control_summary is not None
    assert request.control_summary.governor_decision == "REQUEST_SKILL"
    assert request.control_summary.dominant_signal == "missing_skill"
    assert request.control_summary.confidence == 0.35
    assert request.control_summary.risk_level == "low"
    assert request.control_summary.reversibility == "reversible"
    assert not request.control_summary.approval_required
    assert request.control_summary.approval_gate == "none"
    assert request.control_summary.blocked_reason is None
    assert "Human approval is recorded before durable promotion" in request.control_summary.evidence_to_promote


def test_elevated_risk_request_control_summary_uses_sandbox_gate():
    decision = RouteDecision(
        capability="run local python analysis",
        decision="REQUEST_SKILL",
        reason="No existing skill met threshold for capability 'run local python analysis'.",
        best_match=BestMatch(skill_name=None, score=0.0, coverage="none"),
        risk_level="medium",
    )
    governor = _governor_for(
        decision,
        confidence=0.0,
        risk_level="medium",
        reversibility="partially_reversible",
    )

    summary = create_control_summary(decision, governor)

    assert summary.approval_gate == "sandbox"
    assert not summary.approval_required
    assert summary.blocked_reason is None


def test_control_summary_rejects_mismatched_governor_capability():
    decision = RouteDecision(
        capability="detect contradictions",
        decision="REQUEST_SKILL",
        reason="No existing skill met threshold.",
        best_match=BestMatch(skill_name="compare-claims", score=0.35, coverage="partial"),
        risk_level="low",
    )
    governor = _governor_for(decision, capability="other capability")

    with pytest.raises(ValueError, match="does not match"):
        create_control_summary(decision, governor)


def test_skill_request_with_control_summary_round_trips():
    request = SkillRequest.model_validate(
        {
            "id": "skillreq_test",
            "task_id": "task_test",
            "missing_capability": "detect contradictions",
            "reason": "Need a contradiction skill.",
            "desired_skill_name": "detect-contradictions",
            "input_schema": {"claims": "array"},
            "output_schema": {"contradictions": "array"},
            "success_criteria": ["Finds direct contradictions"],
            "risk_level": "low",
            "control_summary": {
                "governor_decision": "REQUEST_SKILL",
                "dominant_signal": "missing_skill",
                "confidence": 0.35,
                "risk_level": "low",
                "reversibility": "reversible",
                "approval_required": False,
                "approval_gate": "none",
                "evidence_to_promote": ["Validation passes"],
            },
        }
    )

    data = request.model_dump(mode="json")

    assert data["control_summary"]["governor_decision"] == "REQUEST_SKILL"
    assert SkillRequest.model_validate(data).control_summary is not None


def test_skill_request_without_control_summary_still_loads():
    request = SkillRequest.model_validate(
        {
            "id": "skillreq_test",
            "task_id": "task_test",
            "missing_capability": "detect contradictions",
            "reason": "Need a contradiction skill.",
            "desired_skill_name": "detect-contradictions",
            "input_schema": {"claims": "array"},
            "output_schema": {"contradictions": "array"},
            "success_criteria": ["Finds direct contradictions"],
            "risk_level": "low",
        }
    )

    assert request.control_summary is None


def test_control_summary_forbids_extra_fields():
    with pytest.raises(ValidationError):
        SkillRequestControlSummary.model_validate(
            {
                "governor_decision": "REQUEST_SKILL",
                "dominant_signal": "missing_skill",
                "confidence": 0.35,
                "risk_level": "low",
                "reversibility": "reversible",
                "approval_required": False,
                "mystery": "nope",
            }
        )
