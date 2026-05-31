from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


SkillStatus = Literal["draft", "temporary", "candidate", "stable", "deprecated", "blocked"]
RiskLevel = Literal["low", "medium", "high"]
CapabilityDecisionType = Literal["USE_SKILL", "REQUEST_SKILL", "ASK_HUMAN", "ABORT_UNSAFE"]
SkillRequestStatus = Literal["requested"]
SkillRepairRequestStatus = Literal["requested"]
HealthSeverity = Literal["info", "warning", "critical"]
SkillLifecycleStage = Literal["durable", "temporary", "generated", "requested"]
RunResultCategory = Literal[
    "success",
    "blocked_missing_skill",
    "repair_requested",
    "awaiting_human_approval",
    "unsafe_aborted",
    "script_failed",
    "route_load_failed",
]
ScriptFailureCategory = Literal[
    "timeout",
    "nonzero_exit",
    "invalid_json",
    "output_schema_mismatch",
    "output_too_large",
]


SCHEMA_VERSION = 2


def new_default_run_id() -> str:
    return uuid.uuid4().hex[:8]


class SkillLifecycle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: SkillLifecycleStage = "durable"
    source: str = "registry"
    run_id: str | None = None
    temporary: bool = False
    notes: str = ""


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


class ScriptSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entrypoint: str
    timeout_seconds: int = 5


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
    script: ScriptSpec | None = None


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
    source_root: Path
    script: ScriptSpec | None = None
    lifecycle: SkillLifecycle = Field(default_factory=SkillLifecycle)


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


class RouteCandidate(BaseModel):
    skill_name: str
    score: float
    coverage: str
    route_reason: RouteReason | None = None
    selected: bool = False


class RouteDecision(BaseModel):
    capability: str
    decision: CapabilityDecisionType
    selected_skill: str | None = None
    reason: str
    best_match: BestMatch
    route_reason: RouteReason | None = None
    ranked_candidates: list[RouteCandidate] = Field(default_factory=list)
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


class SkillRepairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    task_id: str
    skill_request_id: str
    skill_name: str
    failed_capability: str
    failed_skill_path: str | None = None
    failure_reasons: list[str]
    repair_objective: str
    constraints: list[str]
    status: SkillRepairRequestStatus = "requested"


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
    temporary: bool = False
    lifecycle: SkillLifecycle = Field(default_factory=SkillLifecycle)


class ScriptExecutionLog(BaseModel):
    skill_name: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    parsed_stdout: Any | None = None
    output_validated: bool = False
    failure_category: ScriptFailureCategory | None = None


class TemporarySkillResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_name: str
    skill_path: Path
    validation_passed: bool
    validation_reasons: list[str] = Field(default_factory=list)
    loaded: bool = False
    lifecycle: SkillLifecycle = Field(
        default_factory=lambda: SkillLifecycle(
            stage="temporary", source="skillsmith", temporary=True
        )
    )


class TraceEvent(BaseModel):
    sequence: int
    stage: str
    timestamp: datetime = Field(default_factory=datetime.now)
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class ExecutionSummary(BaseModel):
    loaded_skills: list[str] = Field(default_factory=list)
    temporary_skills: list[str] = Field(default_factory=list)
    requested_skills: list[str] = Field(default_factory=list)
    repair_requested_skills: list[str] = Field(default_factory=list)
    rejected_skills: list[str] = Field(default_factory=list)
    script_executions: list[str] = Field(default_factory=list)
    failed_scripts: list[str] = Field(default_factory=list)
    safety_decisions: list[str] = Field(default_factory=list)
    skill_request_count: int = 0
    skill_repair_request_count: int = 0
    rejected_skill_count: int = 0
    script_execution_count: int = 0
    failed_script_count: int = 0
    safety_decision_count: int = 0
    result_category: RunResultCategory = "success"


class RunLog(BaseModel):
    schema_version: int = SCHEMA_VERSION
    run_id: str = Field(default_factory=new_default_run_id)
    task_id: str
    task: str
    created_at: datetime
    exit_code: int = 0
    result_category: RunResultCategory = "success"
    plan: list[str]
    capability_decisions: list[dict]
    skills_loaded: list[LoadedSkillLog]
    script_executions: list[ScriptExecutionLog] = Field(default_factory=list)
    skill_requests: list[dict] = Field(default_factory=list)
    skill_repair_requests: list[dict] = Field(default_factory=list)
    rejected_skills: list[dict] = Field(default_factory=list)
    trace: list[str]
    trace_events: list[TraceEvent] = Field(default_factory=list)
    execution_summary: ExecutionSummary = Field(default_factory=ExecutionSummary)
    result_quality: dict = Field(
        default_factory=lambda: {
            "score": None,
            "notes": "Route/request execution; quality scoring deferred.",
        }
    )


class AgentRunResult(BaseModel):
    run_log: RunLog
    run_log_path: Path
    exit_code: int


class SkillUsageMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    uses: int = 0
    temporary_uses: int = 0
    script_failures: int = 0
    script_failure_categories: dict[str, int] = Field(default_factory=dict)
    requests: int = 0
    last_used: str | None = None


class SkillHealthIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: HealthSeverity
    code: str
    skill_name: str | None = None
    message: str


class LibraryHealthReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted_skills: int
    rejected_skills: int
    run_logs_read: int
    metrics: list[SkillUsageMetrics]
    issues: list[SkillHealthIssue] = Field(default_factory=list)
    result_categories: dict[str, int] = Field(default_factory=dict)
    temporary_outcomes: dict[str, int] = Field(default_factory=dict)
    repair_requests: int = 0
    safety_stops: int = 0
    human_approval_waits: int = 0
    route_load_failures: int = 0
    script_failure_categories: dict[str, int] = Field(default_factory=dict)
