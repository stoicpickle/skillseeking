from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


SkillStatus = Literal["draft", "temporary", "candidate", "stable", "deprecated", "blocked"]
SkillCandidateStatus = Literal[
    "requested",
    "draft",
    "temporary",
    "candidate",
    "stable",
    "deprecated",
    "blocked",
]
CandidateReviewQueueName = Literal[
    "promotion_ready",
    "repair_needed",
    "blocked_or_quarantined",
    "duplicate_merge_needed",
    "repeated_requested_gap",
]
AdmissionPlanOutcome = Literal[
    "ready_for_durable_review",
    "needs_promotion_approval",
    "evidence_incomplete",
    "blocked",
]
DurableAdmissionPreviewOutcome = Literal[
    "ready_for_mutation_preview",
    "approval_required",
    "blocked",
]
DurableAdmissionWriteOperation = Literal[
    "copy_new_skill",
    "replace_existing_skill",
    "blocked",
]
DurableAdmissionCollisionPolicy = Literal[
    "block_existing",
    "allow_replace_with_approval",
]
DurableAdmissionPermissionPolicy = Literal[
    "block_widening_without_approval",
]
CandidateUsefulnessOutcome = Literal[
    "usefulness_supported",
    "needs_successful_temporary_use",
    "repair_required",
    "blocked",
    "evidence_missing",
]
CandidateUsefulnessComparisonOutcome = Literal[
    "improved",
    "no_clear_improvement",
    "regressed",
    "invalid_comparison",
]
AdmissionCheckResult = Literal["pass", "warning", "blocker", "info"]
InputRequestKind = Literal[
    "safety_approval",
    "promotion_approval",
    "durable_admission_review",
    "repair_review",
    "ambiguity_resolution",
    "missing_evidence",
]
InputRequestStatus = Literal["open", "resolved", "blocked"]
InputRequestSourceType = Literal["run_log", "candidate_ledger", "resolution_ledger"]
InputRequestResolutionClass = Literal[
    "approve",
    "revise",
    "repair",
    "reject",
    "defer",
    "block",
    "recover",
    "merge",
    "keep_separate",
]
RiskLevel = Literal["low", "medium", "high"]
CapabilityDecisionType = Literal["USE_SKILL", "REQUEST_SKILL", "ASK_HUMAN", "ABORT_UNSAFE"]
Reversibility = Literal["reversible", "partially_reversible", "irreversible", "unknown"]
DominantSignal = Literal["skill_match", "missing_skill", "approval_required", "safety_risk"]
ApprovalGate = Literal["none", "draft", "sandbox", "load", "promote", "blocked"]
SkillRequestStatus = Literal["requested"]
SkillRepairRequestStatus = Literal["requested"]
HealthSeverity = Literal["info", "warning", "critical"]
SkillLifecycleStage = Literal["durable", "temporary", "generated", "requested"]
EvidenceGovernorRecommendation = Literal["ask", "test_more", "deny", "defer"]
StableReadinessOutcome = Literal[
    "ready_for_stable_review",
    "needs_more_evidence",
    "blocked",
    "already_stable",
]
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


SCHEMA_VERSION = 3


def new_default_run_id() -> str:
    return uuid.uuid4().hex[:8]


def new_default_input_request_resolution_id() -> str:
    return f"resolution_{uuid.uuid4().hex[:12]}"


def new_default_evidence_checkpoint_id() -> str:
    return f"checkpoint_{uuid.uuid4().hex[:12]}"


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


class DependencyRealization(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    version: str
    sha256: str
    source: str = "declared"


class SkillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str
    tags: list[str] = Field(default_factory=list)
    metadata: Metadata
    risk_level: RiskLevel
    compatibility: dict[str, str] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    dependency_realization: list[DependencyRealization] = Field(default_factory=list)
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


class GovernorDecision(BaseModel):
    """Trace-only governor control summary.

    For USE_SKILL and REQUEST_SKILL, confidence is the route or capability-match
    score. For ASK_HUMAN and blocked safety cases, confidence is certainty that
    the control action is required.
    """

    model_config = ConfigDict(extra="forbid")

    capability: str
    decision: CapabilityDecisionType
    confidence: float
    risk_level: RiskLevel
    reversibility: Reversibility
    approval_required: bool = False
    # Placeholder v1 signals: recorded for trace shape, not active scoring inputs yet.
    freshness_required: bool = False
    tool_failure_history: bool = False
    cost_or_latency_concern: bool = False
    dominant_signal: DominantSignal
    reason: str


class SkillRequestControlSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    governor_decision: CapabilityDecisionType
    dominant_signal: DominantSignal
    confidence: float
    risk_level: RiskLevel
    reversibility: Reversibility
    approval_required: bool
    approval_gate: ApprovalGate = "none"
    blocked_reason: str | None = None
    evidence_to_promote: list[str] = Field(default_factory=list)


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
    control_summary: SkillRequestControlSummary | None = None
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


class SkillCandidateLedgerEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    skill_name: str
    capability: str
    status: SkillCandidateStatus = "requested"
    first_seen_run_id: str | None = None
    last_seen_run_id: str | None = None
    request_count: int = 0
    successful_temporary_uses: int = 0
    validation_pass_count: int = 0
    validation_failure_count: int = 0
    safety_flags: list[str] = Field(default_factory=list)
    duplicate_of: str | None = None
    duplicate_evidence: list[str] = Field(default_factory=list)
    quarantine_reason: str | None = None
    block_reason: str | None = None
    repair_requirements: list[str] = Field(default_factory=list)
    promotion_requirements: list[str] = Field(default_factory=list)
    human_approval_required: bool = True
    promotion_approved_by: str | None = None
    promotion_approved_at: datetime | None = None
    promotion_approval_notes: str | None = None
    governor_summary: dict[str, Any] = Field(default_factory=dict)
    evidence_run_ids: list[str] = Field(default_factory=list)
    input_schema: dict[str, str] = Field(default_factory=dict)
    output_schema: dict[str, str] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class SkillCandidateLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    entries: list[SkillCandidateLedgerEntry] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.now)


class CandidateReviewQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    queue: CandidateReviewQueueName
    candidate_id: str
    skill_name: str
    capability: str
    status: SkillCandidateStatus
    reason: str
    evidence_run_ids: list[str] = Field(default_factory=list)


class AdmissionPlanCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    result: AdmissionCheckResult
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class AdmissionEvidenceRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    run_log_path: str | None = None
    found: bool = False
    result_category: str | None = None
    matching_request_ids: list[str] = Field(default_factory=list)
    temporary_skill_paths: list[str] = Field(default_factory=list)
    validation_passed: bool | None = None
    loaded: bool | None = None


class AdmissionSourceArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill_path: str
    exists: bool
    parsed: bool = False
    source_root: str | None = None
    validation_accepted: bool = False
    validation_reasons: list[str] = Field(default_factory=list)
    skill_name: str | None = None
    risk_level: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    permissions: dict[str, bool] = Field(default_factory=dict)
    compatibility: dict[str, str] = Field(default_factory=dict)
    dependency_declarations: dict[str, Any] = Field(default_factory=dict)
    input_schema: dict[str, str] = Field(default_factory=dict)
    output_schema: dict[str, str] = Field(default_factory=dict)
    scripted: bool = False


class AdmissionDurableRegistrySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    durable_registry_accepted_count: int
    durable_registry_rejected_count: int
    name_collision: dict[str, Any] | None = None
    rejected_name_collision: list[dict[str, Any]] = Field(default_factory=list)
    contract_overlaps: list[dict[str, Any]] = Field(default_factory=list)
    permission_widening: list[str] = Field(default_factory=list)
    risk_or_status_differences: list[str] = Field(default_factory=list)
    scripted_implications: list[str] = Field(default_factory=list)


class AdmissionPermissionDiffItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_name: str
    current_enabled: bool = False
    requested_enabled: bool = False
    change: str = "unchanged"
    approval_required: bool = False


class AdmissionDependencyDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dependencies_declared: bool = False
    declaration_keys: list[str] = Field(default_factory=list)
    exact_realization_available: bool = True
    added: list[str] = Field(default_factory=list)
    removed: list[str] = Field(default_factory=list)
    realized: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class AdmissionDependencyInstallItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    declaration_keys: list[str] = Field(default_factory=list)
    declaration_sources: list[str] = Field(default_factory=list)
    declared_spec: str | None = None
    declared_version: str | None = None
    declared_specs: list[str] = Field(default_factory=list)
    declared_versions: list[str] = Field(default_factory=list)
    realization_version: str | None = None
    realization_sha256: str | None = None
    realization_candidates: list[dict[str, str]] = Field(default_factory=list)
    status: str
    warnings: list[str] = Field(default_factory=list)


class AdmissionDependencyInstallContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy: str = "no_write_dependency_evidence_only"
    schema_version: int = 1
    digest_algorithm: str = "sha256"
    dependency_plan_digest: str | None = None
    expected_dependency_plan_digest: str | None = None
    dependency_plan_digest_verified: bool = False
    prepare_dependency_evidence: bool = False
    evidence_manifest_path: str | None = None
    evidence_manifest_sha256: str | None = None
    evidence_manifest_created: bool = False
    evidence_manifest_retained: bool = False
    dependency_approval_id: str | None = None
    dependency_approval_digest: str | None = None
    dependency_approval_expires_at: str | None = None
    dependency_approval_verified: bool = False
    normalized_dependencies: list[AdmissionDependencyInstallItem] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    install_supported: bool = False
    install_attempted: bool = False
    dependencies_installed: bool = False


class AdmissionPermissionDependencyDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permission_changes: list[AdmissionPermissionDiffItem] = Field(default_factory=list)
    added_permission_classes: list[str] = Field(default_factory=list)
    removed_permission_classes: list[str] = Field(default_factory=list)
    added_tools: list[str] = Field(default_factory=list)
    removed_tools: list[str] = Field(default_factory=list)
    permission_approval_required: bool = False
    dependency_diff: AdmissionDependencyDiff = Field(default_factory=AdmissionDependencyDiff)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class InputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    kind: InputRequestKind
    status: InputRequestStatus = "open"
    title: str
    reason: str
    blocked_scope: str
    requested_decision: str
    options: list[str] = Field(default_factory=list)
    recommended_option: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    next_commands: list[str] = Field(default_factory=list)
    related_run_id: str | None = None
    related_candidate_id: str | None = None
    related_skill_request_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)


class InputRequestSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: InputRequestSourceType
    source_path: str
    source_detail: str | None = None


class InputRequestQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: InputRequest
    sources: list[InputRequestSource] = Field(default_factory=list)


class InputRequestResolutionDryRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dry_run: bool = True
    input_request_id: str
    decision: str
    resolution_class: InputRequestResolutionClass
    proposed_status: InputRequestStatus
    reviewer: str
    notes: str
    request: InputRequest
    sources: list[InputRequestSource] = Field(default_factory=list)
    remaining_blocked_scope: str | None = None
    next_steps: list[str] = Field(default_factory=list)
    run_logs_mutated: bool = False
    candidate_ledger_mutated: bool = False
    resolution_ledger_mutated: bool = False
    durable_skills_mutated: bool = False
    governor_steering_enabled: bool = False


class InputRequestResolutionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_default_input_request_resolution_id)
    input_request_id: str
    decision: str
    resolution_class: InputRequestResolutionClass
    status: InputRequestStatus
    reviewer: str
    notes: str
    source_request: InputRequest
    sources: list[InputRequestSource] = Field(default_factory=list)
    remaining_blocked_scope: str | None = None
    next_steps: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class InputRequestResolutionLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    resolutions: list[InputRequestResolutionRecord] = Field(default_factory=list)


class AdmissionPlanReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    ledger_path: str
    skills_dir: str
    runs_dir: str
    dry_run: bool = True
    auto_promotion_enabled: bool = False
    durable_skill_installed: bool = False
    ledger_mutated: bool = False
    registry_mutated: bool = False
    governor_steering_enabled: bool = False
    ready_for_durable_review: bool
    outcome: AdmissionPlanOutcome
    candidate: dict[str, Any]
    promotion_requirements: list[str]
    evidence_runs: list[AdmissionEvidenceRun]
    source_artifacts: list[AdmissionSourceArtifact]
    selected_source_artifact: str | None = None
    durable_registry: AdmissionDurableRegistrySummary
    checks: list[AdmissionPlanCheck]
    blockers: list[str]
    warnings: list[str]
    next_steps: list[str]
    input_request: InputRequest | None = None


class DurableAdmissionWritePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: DurableAdmissionWriteOperation
    plan_digest_algorithm: str = "sha256"
    plan_digest: str | None = None
    plan_approval_id: str | None = None
    plan_approval_digest: str | None = None
    plan_approval_expires_at: str | None = None
    plan_approval_verified: bool = False
    source_skill_path: str | None = None
    source_sha256: str | None = None
    target_skill_dir: str | None = None
    target_skill_path: str | None = None
    snapshot_dir: str | None = None
    snapshot_skill_path: str | None = None
    snapshot_sha256: str | None = None
    prepare_write_evidence: bool = False
    expected_source_sha256: str | None = None
    source_hash_verified: bool = False
    source_snapshot_retained: bool = False
    destination_stage_dir: str | None = None
    destination_stage_skill_path: str | None = None
    destination_stage_sha256: str | None = None
    destination_stage_created: bool = False
    collision_policy: DurableAdmissionCollisionPolicy = "block_existing"
    permission_policy: DurableAdmissionPermissionPolicy = "block_widening_without_approval"
    permission_approval_id: str | None = None
    permission_dependency_diff: AdmissionPermissionDependencyDiff = Field(
        default_factory=AdmissionPermissionDependencyDiff
    )
    dependency_install_contract: AdmissionDependencyInstallContract = Field(
        default_factory=AdmissionDependencyInstallContract
    )
    replacement_approved: bool = False
    permission_widening_approved: bool = False
    durable_skill_installed: bool = False
    ledger_mutated: bool = False
    registry_mutated: bool = False
    resolution_ledger_mutated: bool = False
    source_snapshot_created: bool = False
    governor_steering_enabled: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class DurableAdmissionPreviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    dry_run: bool = True
    mutation_supported: bool = False
    durable_skill_installed: bool = False
    ledger_mutated: bool = False
    registry_mutated: bool = False
    resolution_ledger_mutated: bool = False
    governor_steering_enabled: bool = False
    outcome: DurableAdmissionPreviewOutcome
    ready_for_mutation_preview: bool
    source_skill_path: str | None = None
    source_sha256: str | None = None
    target_skill_dir: str | None = None
    target_skill_path: str | None = None
    write_plan: DurableAdmissionWritePlan
    required_human_records: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    admission_plan: AdmissionPlanReport


class CandidateUsefulnessEvidenceRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    run_log_path: str | None = None
    found: bool = False
    result_category: str | None = None
    matching_request_ids: list[str] = Field(default_factory=list)
    temporary_skill_paths: list[str] = Field(default_factory=list)
    validation_passed: bool | None = None
    loaded: bool | None = None
    successful: bool = False
    repair_requested: bool = False


class CandidateUsefulnessComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_run_id: str
    baseline_run_log_path: str | None = None
    baseline_result_category: str | None = None
    baseline_exit_code: int | None = None
    baseline_matches_candidate_request: bool = False
    baseline_temporary_skill_present: bool = False
    baseline_temporary_skill_loaded: bool = False
    treatment_run_id: str
    treatment_run_log_path: str | None = None
    treatment_result_category: str | None = None
    treatment_exit_code: int | None = None
    treatment_matches_candidate_request: bool = False
    treatment_temporary_skill_present: bool = False
    treatment_temporary_skill_loaded: bool = False
    outcome: CandidateUsefulnessComparisonOutcome
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    summary: str


class CandidateUsefulnessReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    skill_name: str
    capability: str
    outcome: CandidateUsefulnessOutcome
    usefulness_supported: bool = False
    baseline_comparison_available: bool = False
    successful_temporary_uses: int = 0
    validation_pass_count: int = 0
    validation_failure_count: int = 0
    matching_successful_run_ids: list[str] = Field(default_factory=list)
    evidence_runs: list[CandidateUsefulnessEvidenceRun] = Field(default_factory=list)
    comparison: CandidateUsefulnessComparison | None = None
    admission_plan_outcome: AdmissionPlanOutcome | None = None
    admission_plan_ready: bool = False
    dry_run: bool = True
    run_logs_mutated: bool = False
    candidate_ledger_mutated: bool = False
    durable_skills_mutated: bool = False
    registry_mutated: bool = False
    governor_steering_enabled: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)


class SkillReceiptProof(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    status: str
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SkillReceiptReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    skill_name: str
    capability: str
    status: str
    outcome: str
    proofs: list[SkillReceiptProof] = Field(default_factory=list)
    candidate_usefulness: CandidateUsefulnessReport
    durable_admission_preview: DurableAdmissionPreviewReport
    dry_run: bool = True
    run_logs_mutated: bool = False
    candidate_ledger_mutated: bool = False
    resolution_ledger_mutated: bool = False
    durable_skills_mutated: bool = False
    registry_mutated: bool = False
    governor_steering_enabled: bool = False
    next_steps: list[str] = Field(default_factory=list)


class StableReadinessCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    status: str
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class StableReadinessReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    skill_name: str
    capability: str
    candidate_status: SkillCandidateStatus
    outcome: StableReadinessOutcome
    ready_for_stable_review: bool = False
    required_successful_temporary_uses: int = 10
    successful_temporary_uses: int = 0
    validation_pass_count: int = 0
    validation_failure_count: int = 0
    stable_review_approval_required: bool = True
    dry_run: bool = True
    advisory_only: bool = True
    stable_promotion_authorized: bool = False
    stable_routing_enabled: bool = False
    checks: list[StableReadinessCheck] = Field(default_factory=list)
    skill_receipt: SkillReceiptReport | None = None
    negative_evidence: "NegativeEvidenceReport | None" = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    run_logs_mutated: bool = False
    candidate_ledger_mutated: bool = False
    resolution_ledger_mutated: bool = False
    durable_skills_mutated: bool = False
    registry_mutated: bool = False
    governor_steering_enabled: bool = False


class NegativeEvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    evidence_type: str
    candidate_id: str | None = None
    skill_name: str | None = None
    input_request_id: str | None = None
    decision: str | None = None
    resolution_class: str | None = None
    status: str | None = None
    reason: str
    notes: str | None = None
    source: str
    evidence_refs: list[str] = Field(default_factory=list)
    remaining_blocked_scope: str | None = None
    created_at: datetime | None = None


class NegativeEvidenceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs_dir: str
    candidate_id: str | None = None
    evidence_count: int = 0
    counts_by_type: dict[str, int] = Field(default_factory=dict)
    items: list[NegativeEvidenceItem] = Field(default_factory=list)
    dry_run: bool = True
    run_logs_mutated: bool = False
    candidate_ledger_mutated: bool = False
    resolution_ledger_mutated: bool = False
    durable_skills_mutated: bool = False
    registry_mutated: bool = False
    governor_steering_enabled: bool = False


class EvidenceCheckpointFile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str
    size_bytes: int


class EvidenceCheckpointRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=new_default_evidence_checkpoint_id)
    created_at: datetime = Field(default_factory=datetime.now)
    scope: str = "runs_core"
    previous_checkpoint_hash: str | None = None
    checkpoint_hash_algorithm: str = "sha256"
    checkpoint_hash: str
    evidence_file_count: int = 0
    evidence_files: list[EvidenceCheckpointFile] = Field(default_factory=list)


class EvidenceCheckpointLedger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = SCHEMA_VERSION
    checkpoints: list[EvidenceCheckpointRecord] = Field(default_factory=list)


class EvidenceCheckpointReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    runs_dir: str
    ledger_path: str
    mode: str
    outcome: str
    dry_run: bool = True
    scope: str = "runs_core"
    checkpoint_id: str | None = None
    checkpoint_hash_algorithm: str = "sha256"
    checkpoint_hash: str | None = None
    previous_checkpoint_hash: str | None = None
    latest_checkpoint_hash: str | None = None
    evidence_file_count: int = 0
    evidence_files: list[EvidenceCheckpointFile] = Field(default_factory=list)
    checkpoint_count: int = 0
    checkpoints_verified: int = 0
    chain_valid: bool = False
    current_evidence_matches_latest: bool = False
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    checkpoint_ledger_mutated: bool = False
    run_logs_mutated: bool = False
    candidate_ledger_mutated: bool = False
    resolution_ledger_mutated: bool = False
    durable_skills_mutated: bool = False
    registry_mutated: bool = False
    governor_steering_enabled: bool = False


class EvidenceGovernorSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    status: str
    summary: str
    evidence_refs: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EvidenceGovernorReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    skill_name: str | None = None
    recommendation: EvidenceGovernorRecommendation
    recommendation_reason: str
    allowed_recommendations: list[EvidenceGovernorRecommendation] = Field(
        default_factory=lambda: ["ask", "test_more", "deny", "defer"]
    )
    dry_run: bool = True
    advisory_only: bool = True
    approval_granted: bool = False
    install_authorized: bool = False
    promotion_authorized: bool = False
    permission_widening_authorized: bool = False
    route_steering_enabled: bool = False
    signals: list[EvidenceGovernorSignal] = Field(default_factory=list)
    skill_receipt: SkillReceiptReport
    negative_evidence: NegativeEvidenceReport
    evidence_checkpoint: EvidenceCheckpointReport
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    run_logs_mutated: bool = False
    candidate_ledger_mutated: bool = False
    resolution_ledger_mutated: bool = False
    checkpoint_ledger_mutated: bool = False
    durable_skills_mutated: bool = False
    registry_mutated: bool = False
    governor_steering_enabled: bool = False


class ShadowActivationPlanReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    skill_name: str | None = None
    outcome: str
    ready_for_shadow_activation_preview: bool = False
    dry_run: bool = True
    mutation_supported: bool = False
    managed_prefix: str
    managed_prefix_exists: bool = False
    store_dir: str | None = None
    store_skill_path: str | None = None
    profile_name: str = "default"
    profile_dir: str | None = None
    activation_pointer: str | None = None
    planned_generation: int | None = None
    generation_dir: str | None = None
    generation_skill_path: str | None = None
    previous_generation: int | None = None
    rollback_target: str | None = None
    source_sha256: str | None = None
    durable_plan_digest: str | None = None
    shadow_plan_digest_algorithm: str = "sha256"
    shadow_plan_digest: str | None = None
    collision_policy: str = "shadow_managed_prefix_only"
    activation_policy: str = "profile_pointer_switch"
    canary_scope: str = "manual"
    durable_admission_preview: DurableAdmissionPreviewReport
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    managed_prefix_mutated: bool = False
    profile_mutated: bool = False
    run_logs_mutated: bool = False
    candidate_ledger_mutated: bool = False
    resolution_ledger_mutated: bool = False
    durable_skills_mutated: bool = False
    registry_mutated: bool = False
    governor_steering_enabled: bool = False


class ShadowRollbackPlanReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    skill_name: str | None = None
    outcome: str
    rollback_verifiable: bool = False
    dry_run: bool = True
    mutation_supported: bool = False
    managed_prefix: str
    profile_name: str = "default"
    profile_dir: str | None = None
    activation_pointer: str | None = None
    activation_pointer_exists: bool = False
    activation_pointer_target: str | None = None
    current_generation: int | None = None
    planned_generation: int | None = None
    rollback_generation: int | None = None
    rollback_target: str | None = None
    rollback_target_exists: bool = False
    shadow_plan_digest: str | None = None
    rollback_plan_digest_algorithm: str = "sha256"
    rollback_plan_digest: str | None = None
    shadow_activation_plan: ShadowActivationPlanReport
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    managed_prefix_mutated: bool = False
    profile_mutated: bool = False
    run_logs_mutated: bool = False
    candidate_ledger_mutated: bool = False
    resolution_ledger_mutated: bool = False
    durable_skills_mutated: bool = False
    registry_mutated: bool = False
    governor_steering_enabled: bool = False


class ShadowActivationAcceptanceReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    skill_name: str | None = None
    outcome: str
    acceptance_prepared: bool = False
    activation_verified: bool = False
    rollback_verified: bool = False
    dry_run: bool = True
    mutation_supported: bool = False
    planned_managed_prefix: str
    acceptance_prefix: str
    acceptance_prefix_exists: bool = False
    profile_name: str = "default"
    source_skill_path: str | None = None
    source_sha256: str | None = None
    acceptance_store_skill_path: str | None = None
    acceptance_generation_skill_path: str | None = None
    acceptance_activation_pointer: str | None = None
    previous_generation: int | None = None
    planned_generation: int | None = None
    acceptance_rollback_target: str | None = None
    activation_pointer_before: str | None = None
    activation_pointer_after_activation: str | None = None
    activation_pointer_after_rollback: str | None = None
    interrupted_activation_recovered: bool = False
    acceptance_conflict_detected: bool = False
    shadow_plan_digest: str | None = None
    acceptance_plan_digest_algorithm: str = "sha256"
    acceptance_plan_digest: str | None = None
    shadow_activation_plan: ShadowActivationPlanReport
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    acceptance_prefix_mutated: bool = False
    managed_prefix_mutated: bool = False
    profile_mutated: bool = False
    run_logs_mutated: bool = False
    candidate_ledger_mutated: bool = False
    resolution_ledger_mutated: bool = False
    durable_skills_mutated: bool = False
    registry_mutated: bool = False
    governor_steering_enabled: bool = False


class ShadowWriteGateReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    skill_name: str | None = None
    outcome: str
    ready_for_human_managed_prefix_write: bool = False
    dry_run: bool = True
    mutation_supported: bool = False
    managed_prefix: str
    acceptance_prefix: str
    profile_name: str = "default"
    source_skill_path: str | None = None
    source_sha256: str | None = None
    source_hash_verified: bool = False
    acceptance_store_skill_path: str | None = None
    acceptance_store_verified: bool = False
    acceptance_generation_skill_path: str | None = None
    acceptance_generation_verified: bool = False
    acceptance_activation_pointer: str | None = None
    acceptance_pointer_restored: bool = False
    acceptance_pointer_target: str | None = None
    acceptance_rollback_target: str | None = None
    acceptance_rollback_marker_verified: bool = False
    durable_plan_digest: str | None = None
    shadow_plan_digest: str | None = None
    rollback_plan_digest: str | None = None
    acceptance_plan_digest_algorithm: str = "sha256"
    acceptance_plan_digest: str | None = None
    expected_acceptance_plan_digest: str | None = None
    acceptance_plan_digest_verified: bool = False
    shadow_activation_plan: ShadowActivationPlanReport
    shadow_rollback_plan: ShadowRollbackPlanReport
    shadow_activation_acceptance: ShadowActivationAcceptanceReport
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    acceptance_prefix_mutated: bool = False
    managed_prefix_mutated: bool = False
    profile_mutated: bool = False
    run_logs_mutated: bool = False
    candidate_ledger_mutated: bool = False
    resolution_ledger_mutated: bool = False
    durable_skills_mutated: bool = False
    registry_mutated: bool = False
    governor_steering_enabled: bool = False


ShadowManagedWriteOutcome = Literal[
    "approval_required",
    "blocked",
    "ready_for_managed_prefix_write",
    "managed_prefix_write_applied",
    "already_applied",
]


class ShadowManagedWriteReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    skill_name: str | None = None
    outcome: ShadowManagedWriteOutcome
    ready_for_managed_prefix_write: bool = False
    dry_run: bool = True
    mutation_supported: bool = False
    managed_prefix: str
    acceptance_prefix: str
    profile_name: str = "default"
    source_skill_path: str | None = None
    source_sha256: str | None = None
    source_hash_verified: bool = False
    store_skill_path: str | None = None
    generation_skill_path: str | None = None
    activation_pointer: str | None = None
    rollback_target: str | None = None
    durable_plan_digest: str | None = None
    shadow_plan_digest: str | None = None
    rollback_plan_digest: str | None = None
    acceptance_plan_digest: str | None = None
    managed_write_plan_digest_algorithm: str = "sha256"
    managed_write_plan_digest: str | None = None
    expected_source_sha256: str | None = None
    expected_durable_plan_digest: str | None = None
    expected_shadow_plan_digest: str | None = None
    expected_rollback_plan_digest: str | None = None
    expected_acceptance_plan_digest: str | None = None
    expected_managed_write_plan_digest: str | None = None
    expected_checkpoint_hash: str | None = None
    expected_source_sha256_verified: bool = False
    durable_plan_digest_verified: bool = False
    shadow_plan_digest_verified: bool = False
    rollback_plan_digest_verified: bool = False
    acceptance_plan_digest_verified: bool = False
    managed_write_plan_digest_verified: bool = False
    checkpoint_verified: bool = False
    checkpoint_hash_verified: bool = False
    latest_checkpoint_hash: str | None = None
    write_approval_id: str | None = None
    write_approval_digest: str | None = None
    write_approval_expires_at: str | None = None
    write_approval_present: bool = False
    write_approval_verified: bool = False
    exact_expected_values_verified: bool = False
    receipt_acceptable: bool = False
    receipt_reversibility_accepted: bool = False
    shadow_write_gate_ready: bool = False
    rollback_ready: bool = False
    write_receipt_path: str | None = None
    store_verified: bool = False
    generation_verified: bool = False
    activation_pointer_target: str | None = None
    activation_pointer_updated: bool = False
    activation_pointer_verified: bool = False
    rollback_target_verified: bool = False
    already_applied: bool = False
    interrupted_activation_recovered: bool = False
    managed_prefix_write_policy: str = "managed_prefix_only_write"
    profile_activation_policy: str = "profile_pointer_switch"
    rollback_policy: str = "profile_pointer_rollback"
    stable_routing_policy: str = "stable_routing_unchanged"
    governor_policy: str = "governor_advisory_only"
    skill_receipt: SkillReceiptReport
    evidence_checkpoint: EvidenceCheckpointReport
    shadow_write_gate: ShadowWriteGateReport
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    acceptance_prefix_mutated: bool = False
    managed_prefix_mutated: bool = False
    profile_mutated: bool = False
    run_logs_mutated: bool = False
    candidate_ledger_mutated: bool = False
    resolution_ledger_mutated: bool = False
    checkpoint_ledger_mutated: bool = False
    durable_skills_mutated: bool = False
    registry_mutated: bool = False
    governor_steering_enabled: bool = False


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
    governor_decisions: list[GovernorDecision] = Field(default_factory=list)
    skills_loaded: list[LoadedSkillLog]
    script_executions: list[ScriptExecutionLog] = Field(default_factory=list)
    skill_requests: list[dict] = Field(default_factory=list)
    skill_repair_requests: list[dict] = Field(default_factory=list)
    input_requests: list[InputRequest] = Field(default_factory=list)
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
    input_request_count: int = 0
    input_request_kind_counts: dict[str, int] = Field(default_factory=dict)
    candidate_count: int = 0
    candidate_status_counts: dict[str, int] = Field(default_factory=dict)
    blocked_candidate_count: int = 0
    duplicate_candidate_count: int = 0
    human_gated_candidate_count: int = 0
    candidate_review_queue_counts: dict[str, int] = Field(default_factory=dict)
