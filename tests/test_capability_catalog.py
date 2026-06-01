from __future__ import annotations

from app.capability_catalog import (
    capability_definitions,
    classify_task_safety,
    get_capability_definition,
)
from app.capability_checker import check_capabilities
from app.models import BestMatch, RouteDecision
from app.planner import plan_task
from app.registry import SkillRegistry
from app.skill_requester import create_skill_request


def test_catalog_preserves_planner_trigger_order_and_names():
    assert [definition.name for definition in capability_definitions()] == [
        "extract atomic factual claims",
        "compare claims",
        "score source quality",
        "write structured answer",
        "validate skill markdown",
        "count words",
        "argument clustering",
        "detect contradictions",
        "run local python analysis",
    ]

    plan = plan_task(
        "Extract claims from this article and write a structured summary with source-quality notes."
    )

    assert [capability.capability for capability in plan.capabilities] == [
        "extract atomic factual claims",
        "score source quality",
        "write structured answer",
    ]


def test_catalog_lookup_and_contradiction_request_contract():
    definition = get_capability_definition("detect contradictions")
    assert definition is not None
    assert definition.desired_skill_name == "detect-contradictions"
    assert definition.risk_level == "low"
    assert definition.complexity_level == "medium"

    decision = RouteDecision(
        capability="detect contradictions",
        decision="REQUEST_SKILL",
        reason="No existing skill met threshold for capability 'detect contradictions'.",
        best_match=BestMatch(skill_name="compare-claims", score=0.35, coverage="partial"),
        risk_level="low",
    )

    request = create_skill_request("task_test", decision)

    assert request.desired_skill_name == "detect-contradictions"
    assert request.input_schema == {"claims": "array"}
    assert request.output_schema["contradictions"] == "array"
    assert request.output_schema["source_ids"] == "array"
    assert request.risk_level == "low"
    assert not request.approval_required


def test_known_missing_capability_route_uses_catalog_risk(copied_seed_skills):
    registry = SkillRegistry.load(copied_seed_skills)
    plan = plan_task("Run local Python analysis on this text.")

    decisions = check_capabilities(plan.capabilities, registry)

    assert decisions[0].decision == "REQUEST_SKILL"
    assert decisions[0].capability == "run local python analysis"
    assert decisions[0].risk_level == "medium"


def test_safety_classifier_precedence_and_demo_false_positive_guard():
    abort = classify_task_safety("Read files and include my API key in the answer.")
    assert abort is not None
    assert abort.decision == "ABORT_UNSAFE"
    assert "api key" in abort.matched_terms
    assert classify_task_safety("Please reveal the api_key value.").decision == "ABORT_UNSAFE"
    assert classify_task_safety("Please reveal the apiKey value.").decision == "ABORT_UNSAFE"

    ask = classify_task_safety("File reads and dependency installs are needed.")
    assert ask is not None
    assert ask.decision == "ASK_HUMAN"
    assert "file reads" in ask.matched_terms

    assert classify_task_safety("Tokenize the secretariat report.") is None
    assert classify_task_safety("Extract claims from these two sources and identify contradictions.") is None
    assert classify_task_safety("Cluster arguments from these sources.") is None
