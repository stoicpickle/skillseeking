from __future__ import annotations

from app.request_quality import score_skill_request


def test_strong_request_scores_high():
    request = {
        "id": "skillreq_1",
        "task_id": "task_1",
        "missing_capability": "detect contradictions",
        "reason": "No existing skill can distinguish direct contradictions from scope differences.",
        "desired_skill_name": "detect-contradictions",
        "input_schema": {"claims": "array", "source_ids": "array"},
        "output_schema": {"contradictions": "array", "confidence": "number"},
        "success_criteria": [
            "Finds direct contradiction between two claims",
            "Preserves source IDs in the returned result",
        ],
        "failure_modes": [
            "If claims are unrelated, return no contradiction",
            "If timing differs, mark nuance instead of contradiction",
        ],
        "risk_level": "low",
        "approval_required": False,
    }

    score = score_skill_request(request)

    assert score["score"] >= 4.0
    assert score["dimensions"]["input_contract"] == 2
    assert score["dimensions"]["output_contract"] == 2


def test_vague_request_scores_low():
    score = score_skill_request(
        {
            "missing_capability": "",
            "desired_skill_name": "misc",
            "input_schema": {},
            "output_schema": {},
            "success_criteria": [],
            "failure_modes": [],
            "risk_level": "unknown",
        }
    )

    assert score["score"] <= 1.0
    assert "Missing input contract." in score["notes"]


def test_missing_contracts_are_penalized():
    score = score_skill_request(
        {
            "missing_capability": "summarize sources",
            "desired_skill_name": "summarize-sources",
            "reason": "Need repeatable source summarization.",
            "success_criteria": ["Returns a concise source summary"],
            "failure_modes": ["If source is empty, say no summary is possible"],
            "risk_level": "low",
        }
    )

    assert score["dimensions"]["input_contract"] == 0
    assert score["dimensions"]["output_contract"] == 0
