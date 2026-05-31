from __future__ import annotations

from typing import Any

from app.models import SkillRequest


DIMENSIONS = (
    "specificity",
    "input_contract",
    "output_contract",
    "success_criteria",
    "failure_modes",
    "risk_level_correctness",
    "reuse_potential",
)


def score_skill_request(request: SkillRequest | dict[str, Any]) -> dict[str, Any]:
    data = request.model_dump(mode="json") if isinstance(request, SkillRequest) else request
    dimensions = {
        "specificity": _specificity(data),
        "input_contract": _contract_score(data.get("input_schema")),
        "output_contract": _contract_score(data.get("output_schema")),
        "success_criteria": _list_score(data.get("success_criteria")),
        "failure_modes": _list_score(data.get("failure_modes")),
        "risk_level_correctness": _risk_score(data),
        "reuse_potential": _reuse_score(data),
    }
    raw_score = sum(dimensions.values())
    score = round((raw_score / (len(DIMENSIONS) * 2)) * 5, 1)
    return {
        "score": score,
        "max_score": 5,
        "dimensions": dimensions,
        "notes": _notes(dimensions),
    }


def _specificity(data: dict[str, Any]) -> int:
    capability = str(data.get("missing_capability") or "")
    desired_name = str(data.get("desired_skill_name") or "")
    reason = str(data.get("reason") or "")
    if capability and desired_name and len(reason) >= 24:
        return 2
    if capability or desired_name:
        return 1
    return 0


def _contract_score(value: Any) -> int:
    if not isinstance(value, dict) or not value:
        return 0
    if len(value) >= 2 and all(str(key).strip() and str(kind).strip() for key, kind in value.items()):
        return 2
    return 1


def _list_score(value: Any) -> int:
    if not isinstance(value, list) or not value:
        return 0
    useful_items = [item for item in value if isinstance(item, str) and len(item.strip()) >= 12]
    if len(useful_items) >= 2:
        return 2
    return 1 if useful_items else 0


def _risk_score(data: dict[str, Any]) -> int:
    risk = data.get("risk_level")
    if risk not in {"low", "medium", "high"}:
        return 0
    if risk in {"medium", "high"} and not data.get("approval_required"):
        return 1
    return 2


def _reuse_score(data: dict[str, Any]) -> int:
    name = str(data.get("desired_skill_name") or "")
    criteria = " ".join(data.get("success_criteria") or []).lower()
    if name and not any(word in name for word in {"one-off", "temporary", "misc"}):
        return 2 if "repeat" in criteria or "schema" in criteria or data.get("input_schema") else 1
    return 0


def _notes(dimensions: dict[str, int]) -> list[str]:
    notes: list[str] = []
    for dimension, score in dimensions.items():
        if score == 0:
            notes.append(f"Missing {dimension.replace('_', ' ')}.")
        elif score == 1:
            notes.append(f"Weak {dimension.replace('_', ' ')}.")
    if not notes:
        notes.append("Request is specific, testable, and reusable.")
    return notes
