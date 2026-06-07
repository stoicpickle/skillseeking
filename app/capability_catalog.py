from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

from app.models import RiskLevel

SafetyAction = Literal["ASK_HUMAN", "ABORT_UNSAFE"]
ComplexityLevel = Literal["low", "medium", "high"]
SafetyPattern = tuple[tuple[str, ...], str, str]


@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    trigger_terms: tuple[str, ...]
    desired_skill_name: str
    risk_level: RiskLevel = "low"
    complexity_level: ComplexityLevel = "low"
    safety_action: SafetyAction | None = None
    safety_reason: str = ""
    input_schema: dict[str, str] = field(default_factory=dict)
    output_schema: dict[str, str] = field(default_factory=dict)
    success_criteria: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()
    approval_required: bool = False


@dataclass(frozen=True)
class SafetyClassification:
    decision: SafetyAction
    capability: str
    reason: str
    matched_terms: tuple[str, ...]
    risk_level: RiskLevel


_CAPABILITIES: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition(
        name="extract atomic factual claims",
        trigger_terms=("extract claims", "claims from", "claim extraction"),
        desired_skill_name="extract-claims",
        input_schema={"text": "string", "source_id": "string"},
        output_schema={"claims": "array"},
        success_criteria=(
            "Extracts short atomic factual claims",
            "Preserves source identifiers",
            "Avoids merging unrelated claims",
        ),
        failure_modes=("If text has no factual claims, return an empty claims list",),
    ),
    CapabilityDefinition(
        name="compare claims",
        trigger_terms=("compare", "differences", "similarities"),
        desired_skill_name="compare-claims",
        input_schema={"claims": "array"},
        output_schema={"comparisons": "array"},
        success_criteria=(
            "Compares claims for overlap, differences, similarities, or tension",
            "Separates scope differences from direct conflict",
        ),
        failure_modes=("If claims are unrelated, say so explicitly",),
    ),
    CapabilityDefinition(
        name="score source quality",
        trigger_terms=("source quality", "credible", "reliable", "quality notes"),
        desired_skill_name="source-quality-check",
        input_schema={"source_text": "string", "source_metadata": "object"},
        output_schema={"source_quality": "object"},
        success_criteria=(
            "Assesses credibility, relevance, specificity, and usefulness",
            "Preserves uncertainty when source metadata is incomplete",
        ),
        failure_modes=("If source metadata is missing, state the limitation",),
    ),
    CapabilityDefinition(
        name="write structured answer",
        trigger_terms=("summary", "answer", "write", "structured summary"),
        desired_skill_name="write-structured-answer",
        input_schema={"notes": "array", "task": "string"},
        output_schema={"answer": "string"},
        success_criteria=(
            "Writes a concise structured answer from prepared notes",
            "Preserves uncertainty and avoids unsupported claims",
        ),
        failure_modes=("If notes are insufficient, identify what is missing",),
    ),
    CapabilityDefinition(
        name="validate skill markdown",
        trigger_terms=("validate skill", "check skill.md", "skill.md"),
        desired_skill_name="validate-skill-md",
        input_schema={"skill_markdown": "string"},
        output_schema={"validation_result": "object"},
        success_criteria=(
            "Checks required metadata and safety constraints",
            "Returns actionable validation findings",
        ),
        failure_modes=("If Markdown cannot be parsed, return a parse failure",),
    ),
    CapabilityDefinition(
        name="count words",
        trigger_terms=("count words", "word count", "words in"),
        desired_skill_name="count-words",
        input_schema={"text": "string"},
        output_schema={"word_count": "integer"},
        success_criteria=("Counts words in provided text",),
        failure_modes=("If no text is provided, return a zero count",),
    ),
    CapabilityDefinition(
        name="argument clustering",
        trigger_terms=("cluster arguments", "argument clustering", "group arguments"),
        desired_skill_name="argument-clustering",
        input_schema={"arguments": "array"},
        output_schema={"clusters": "array", "confidence": "number"},
        success_criteria=(
            "Groups similar arguments together",
            "Labels clusters with concise themes",
            "Keeps minority or outlier arguments visible",
        ),
        failure_modes=(
            "If arguments are too sparse, return singleton clusters",
            "If the task asks for persuasion, preserve neutrality",
        ),
    ),
    CapabilityDefinition(
        name="detect contradictions",
        trigger_terms=(
            "contradiction",
            "contradictions",
            "disagree",
            "factual conflict",
            "factual conflicts",
            "conflicting claims",
            "incompatible claims",
        ),
        desired_skill_name="detect-contradictions",
        risk_level="low",
        complexity_level="medium",
        input_schema={"claims": "array"},
        output_schema={
            "contradictions": "array",
            "confidence": "number",
            "explanation": "string",
            "source_ids": "array",
        },
        success_criteria=(
            "Finds direct contradiction between two claims",
            "Distinguishes contradiction from nuance or scope difference",
            "Preserves source IDs",
            "Returns confidence for each contradiction",
        ),
        failure_modes=(
            "If claims are unrelated, return no contradiction",
            "If scope or timing differs, mark as nuance instead of contradiction",
        ),
    ),
    CapabilityDefinition(
        name="run local python analysis",
        trigger_terms=("run local python", "python analysis", "local code analysis"),
        desired_skill_name="local-python-analysis",
        risk_level="medium",
        complexity_level="medium",
        input_schema={"text": "string", "task": "string"},
        output_schema={"analysis": "object"},
        success_criteria=(
            "Describes a local Python analysis workflow",
            "Does not execute code unless explicitly enabled through scripted-skill controls",
        ),
        failure_modes=(
            "If code execution is needed, remain blocked until an explicit scripted skill is reviewed",
        ),
    ),
)

_ABORT_PATTERNS: tuple[SafetyPattern, ...] = (
    (
        ("api key", "api keys", "secret", "secrets", "password", "token"),
        "unsafe secrets request",
        "Requests involving secrets, API keys, passwords, or tokens are unsafe for autonomous execution.",
    ),
    (
        ("payment", "credit card"),
        "unsafe payment request",
        "Payment or credit-card actions are unsafe for autonomous execution.",
    ),
    (
        ("send email", "email this", "mail this"),
        "unsafe outbound message request",
        "Sending email or outbound messages requires a human-controlled workflow.",
    ),
    (
        (
            "delete files",
            "delete file",
            "delete this file",
            "delete the file",
            "remove files",
            "remove file",
            "remove this file",
            "remove the file",
            "rm -rf",
        ),
        "unsafe file deletion request",
        "Deleting files is unsafe for autonomous execution.",
    ),
)

_ASK_PATTERNS: tuple[SafetyPattern, ...] = (
    (
        (
            "read file",
            "read files",
            "read local file",
            "read local files",
            "read this file",
            "read the file",
            "file read",
            "file reads",
            "open file",
            "open local file",
            "open this file",
            "open the file",
            "summarize files",
            "summarize file",
            "summarize these files",
            "summarize this file",
            "summarize the files",
            "summarize the file",
            "summarize a local file",
            "summarize local file",
            "summarize local files",
        ),
        "human approval required for file access",
        "Reading local files requires explicit human approval.",
    ),
    (
        ("external api", "call api", "web request"),
        "human approval required for external API access",
        "External API or web-request access requires explicit human approval.",
    ),
    (
        (
            "install dependency",
            "install dependencies",
            "dependency install",
            "dependency installs",
            "pip install",
            "npm install",
        ),
        "human approval required for dependency installation",
        "Installing dependencies requires explicit human approval.",
    ),
    (
        ("write to disk", "modify local files", "edit files", "broad local mutation"),
        "human approval required for local mutation",
        "Writing or broadly modifying local files requires explicit human approval.",
    ),
)


def capability_definitions() -> tuple[CapabilityDefinition, ...]:
    return _CAPABILITIES


def get_capability_definition(name: str) -> CapabilityDefinition | None:
    normalized = name.lower()
    for definition in _CAPABILITIES:
        if definition.name == normalized:
            return definition
    return None


def _normalize_safety_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def _contains_safety_term(text: str, term: str) -> bool:
    normalized_text = _normalize_safety_text(text)
    normalized_term = _normalize_safety_text(term)
    if not normalized_term:
        return False
    if " " in normalized_term:
        compact_text = normalized_text.replace(" ", "")
        compact_term = normalized_term.replace(" ", "")
        return normalized_term in normalized_text or compact_term in compact_text
    return re.search(rf"\b{re.escape(normalized_term)}\b", normalized_text) is not None


def classify_task_safety(task_text: str) -> SafetyClassification | None:
    lowered = task_text.lower()
    abort = _match_safety_patterns(lowered, _ABORT_PATTERNS, "ABORT_UNSAFE", "high")
    if abort is not None:
        return abort
    return _match_safety_patterns(lowered, _ASK_PATTERNS, "ASK_HUMAN", "medium")


def safety_decision_for_capability(capability: str) -> SafetyClassification | None:
    definition = get_capability_definition(capability)
    if definition is None or definition.safety_action is None:
        return None
    return SafetyClassification(
        decision=definition.safety_action,
        capability=definition.name,
        reason=definition.safety_reason or f"Capability '{definition.name}' requires safety handling.",
        matched_terms=(),
        risk_level=definition.risk_level,
    )


def _match_safety_patterns(
    lowered: str,
    patterns: tuple[SafetyPattern, ...],
    decision: SafetyAction,
    risk_level: RiskLevel,
) -> SafetyClassification | None:
    for terms, capability, reason in patterns:
        matched = tuple(term for term in terms if _contains_safety_term(lowered, term))
        if matched:
            return SafetyClassification(
                decision=decision,
                capability=capability,
                reason=reason,
                matched_terms=matched,
                risk_level=risk_level,
            )
    return None
