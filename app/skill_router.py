from __future__ import annotations

import re

from app.models import BestMatch, RouteDecision, RouteReason, SkillRecord
from app.registry import SkillRegistry


THRESHOLD = 0.55


def route_capability(capability: str, registry: SkillRegistry) -> RouteDecision:
    scored: list[tuple[float, SkillRecord, RouteReason]] = []
    capability_terms = _terms(capability)

    for record in registry.list_records():
        reason = _score_record(capability, capability_terms, record)
        scored.append((reason.score, record, reason))

    if not scored:
        return RouteDecision(
            capability=capability,
            decision="REQUEST_SKILL",
            reason="No accepted skills are available.",
            best_match=BestMatch(skill_name=None, score=0.0, coverage="none"),
        )

    scored.sort(key=lambda item: (-item[0], item[1].risk_level, item[1].validation_status, item[1].name))
    score, record, reason = scored[0]
    if score >= THRESHOLD:
        return RouteDecision(
            capability=capability,
            decision="USE_SKILL",
            selected_skill=record.name,
            reason=f"Selected {record.name} for capability '{capability}'.",
            best_match=BestMatch(skill_name=record.name, score=score, coverage="matched"),
            route_reason=reason,
            risk_level=record.risk_level,
        )

    return RouteDecision(
        capability=capability,
        decision="REQUEST_SKILL",
        reason=f"No existing skill met threshold for capability '{capability}'.",
        best_match=BestMatch(skill_name=record.name, score=score, coverage="partial"),
        route_reason=reason,
        risk_level=record.risk_level,
    )


def _score_record(capability: str, capability_terms: set[str], record: SkillRecord) -> RouteReason:
    metadata_text = " ".join([record.name, record.description, *record.tags]).lower()
    metadata_terms = _terms(metadata_text)
    matched_terms = sorted(capability_terms & metadata_terms)

    lexical = len(matched_terms) / max(len(capability_terms), 1)
    schema_terms = _schema_terms(record)
    schema_overlap = sorted(capability_terms & schema_terms)
    schema = min(len(schema_overlap) / max(len(capability_terms), 1), 1.0)
    status = 1.0 if record.status in {"candidate", "stable"} and record.validation_status else 0.0
    risk_permissions = 1.0 if record.risk_level == "low" and not any(record.permissions.model_dump().values()) else 0.0
    compatibility = 1.0 if record.compatibility else 0.5
    score = (lexical * 0.40) + (schema * 0.25) + (status * 0.15) + (risk_permissions * 0.10) + (compatibility * 0.10)

    return RouteReason(
        matched_terms=matched_terms,
        schema_overlap=schema_overlap,
        risk_result=f"risk={record.risk_level}",
        permission_result="all permissions false" if risk_permissions else "unsafe permissions",
        status_result=f"status={record.status}; validation={record.validation_status}",
        compatibility_result="declared" if record.compatibility else "not declared",
        score=round(score, 4),
        threshold=THRESHOLD,
    )


def _terms(text: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", text.lower())
        if token and token not in {"the", "a", "an", "and", "or", "to", "from", "with"}
    }


def _schema_terms(record: SkillRecord) -> set[str]:
    terms: set[str] = set()
    for key, value in {**record.input_schema, **record.output_schema}.items():
        terms |= _terms(key)
        terms |= _terms(str(value))
    return terms

