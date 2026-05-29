from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SkillStatus = Literal["draft", "temporary", "candidate", "stable", "deprecated", "blocked"]
RiskLevel = Literal["low", "medium", "high"]
CapabilityDecisionType = Literal["USE_SKILL", "REQUEST_SKILL"]
SkillRequestStatus = Literal["requested"]


class Permissions(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_files: bool = False
    write_files: bool = False
    network: bool = False
    secrets: bool = False
    execute_code: bool = False


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    owner: str = "local"
    status: SkillStatus


class ValidationMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    notes: str = ""


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    metadata: Metadata
    risk_level: RiskLevel
    compatibility: dict[str, str] = Field(default_factory=dict)
    allowed_tools: list[str] = Field(default_factory=list)
    permissions: Permissions = Field(default_factory=Permissions)
    input_schema: dict[str, str] = Field(default_factory=dict)
    output_schema: dict[str, str] = Field(default_factory=dict)
    validation: ValidationMetadata


class ParsedSkill(BaseModel):
    frontmatter: dict
    body_text_for_scan_only: str
    path: Path


class SkillRecord(BaseModel):
    name: str
    version: str
    description: str
    tags: list[str]
    status: SkillStatus
    owner: str
    risk_level: RiskLevel
    input_schema: dict[str, str]
    output_schema: dict[str, str]
    allowed_tools: list[str]
    permissions: Permissions
    compatibility: dict[str, str]
    validation_status: str
    path: Path


class RejectedSkill(BaseModel):
    name: str | None = None
    path: Path
    reasons: list[str]


class CapabilityRequest(BaseModel):
    capability: str
    source_terms: list[str] = Field(default_factory=list)


class BestMatch(BaseModel):
    skill_name: str | None
    score: float
    coverage: str


class RouteReason(BaseModel):
    matched_terms: list[str] = Field(default_factory=list)
    schema_overlap: list[str] = Field(default_factory=list)
    risk_result: str
    permission_result: str
    status_result: str
    compatibility_result: str
    score: float
    threshold: float


class RouteDecision(BaseModel):
    capability: str
    decision: CapabilityDecisionType
    selected_skill: str | None = None
    reason: str
    best_match: BestMatch
    route_reason: RouteReason | None = None
    risk_level: RiskLevel = "low"
    requires_human_approval: bool = False


class SkillRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    task_id: str
    missing_capability: str
    reason: str
    desired_skill_name: str
    input_schema: dict[str, str]
    output_schema: dict[str, str]
    success_criteria: list[str]
    failure_modes: list[str] = Field(default_factory=list)
    risk_level: RiskLevel
    approval_required: bool = False
    status: SkillRequestStatus = "requested"


class TaskPlan(BaseModel):
    task_id: str
    task: str
    capabilities: list[CapabilityRequest]


class LoadedSkill(BaseModel):
    name: str
    version: str
    path: Path
    markdown_body: str
    frontmatter: dict
    loaded_for_capability: str
    load_reason: str


class LoadedSkillLog(BaseModel):
    name: str
    version: str
    path: str
    loaded_for_capability: str
    load_reason: str


class RunLog(BaseModel):
    task_id: str
    task: str
    created_at: datetime
    plan: list[str]
    capability_decisions: list[dict]
    skills_loaded: list[LoadedSkillLog]
    skill_requests: list[dict] = Field(default_factory=list)
    rejected_skills: list[dict] = Field(default_factory=list)
    trace: list[str]
    result_quality: dict = Field(
        default_factory=lambda: {
            "score": None,
            "notes": "M1 route-only execution; quality scoring deferred.",
        }
    )


class AgentRunResult(BaseModel):
    run_log: RunLog
    run_log_path: Path
    exit_code: int
