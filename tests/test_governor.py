from __future__ import annotations

from app.governor import evaluate_governor
from app.models import BestMatch, RouteDecision, RouteReason


def test_governor_use_skill_maps_route_score_and_skill_match():
    decision = RouteDecision(
        capability="extract claims",
        decision="USE_SKILL",
        selected_skill="extract-claims",
        reason="Selected extract-claims.",
        best_match=BestMatch(skill_name="extract-claims", score=0.75, coverage="matched"),
        route_reason=RouteReason(
            risk_result="risk=low",
            permission_result="all permissions false",
            status_result="status=stable",
            compatibility_result="declared",
            score=0.82,
            threshold=0.55,
        ),
        risk_level="low",
    )

    governor = evaluate_governor(decision)

    assert governor.decision == "USE_SKILL"
    assert governor.confidence == 0.82
    assert governor.dominant_signal == "skill_match"
    assert governor.reversibility == "reversible"
    assert not governor.approval_required


def test_governor_request_skill_uses_best_match_fallback_and_missing_skill_signal():
    decision = RouteDecision(
        capability="detect contradictions",
        decision="REQUEST_SKILL",
        reason="No existing skill met threshold.",
        best_match=BestMatch(skill_name="compare-claims", score=0.32, coverage="partial"),
        risk_level="low",
    )

    governor = evaluate_governor(decision)

    assert governor.decision == "REQUEST_SKILL"
    assert governor.confidence == 0.32
    assert governor.dominant_signal == "missing_skill"
    assert governor.reversibility == "reversible"


def test_governor_ask_human_marks_approval_required():
    decision = RouteDecision(
        capability="human approval required for file access",
        decision="ASK_HUMAN",
        reason="Reading local files requires approval.",
        best_match=BestMatch(skill_name=None, score=0.0, coverage="safety"),
        risk_level="medium",
        requires_human_approval=True,
    )

    governor = evaluate_governor(decision)

    assert governor.decision == "ASK_HUMAN"
    assert governor.confidence == 1.0
    assert governor.approval_required
    assert governor.dominant_signal == "approval_required"
    assert governor.reversibility == "unknown"


def test_governor_abort_unsafe_marks_blocked_not_reviewable():
    decision = RouteDecision(
        capability="unsafe secrets request",
        decision="ABORT_UNSAFE",
        reason="Requests involving secrets are unsafe.",
        best_match=BestMatch(skill_name=None, score=0.0, coverage="safety"),
        risk_level="high",
    )

    governor = evaluate_governor(decision)

    assert governor.decision == "ABORT_UNSAFE"
    assert governor.confidence == 1.0
    assert not governor.approval_required
    assert governor.dominant_signal == "safety_risk"
    assert governor.reversibility == "unknown"
    assert "blocked, not reviewable" in governor.reason


def test_governor_missing_score_falls_back_to_zero():
    decision = RouteDecision(
        capability="unknown capability",
        decision="REQUEST_SKILL",
        reason="No accepted skills are available.",
        best_match=BestMatch(skill_name=None, score=0.0, coverage="none"),
    )

    governor = evaluate_governor(decision)

    assert governor.confidence == 0.0
