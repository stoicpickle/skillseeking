from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.capability_checker import check_capabilities, check_task_safety
from app.governor import evaluate_governor
from app.input_focus import repair_input_request, safety_input_request
from app.loader import SkillLoadError, load_skill
from app.models import (
    AgentRunResult,
    SCHEMA_VERSION,
    ExecutionSummary,
    LoadedSkillLog,
    RunLog,
    RunResultCategory,
    ScriptExecutionLog,
    TraceEvent,
)
from app.planner import plan_task
from app.registry import SkillRegistry
from app.run_log import new_run_id, rewrite_run_log, write_run_log
from app.skill_candidate_ledger import record_run_in_candidate_ledger
from app.skill_repairer import create_skill_repair_request
from app.script_executor import execute_scripted_skill
from app.skill_requester import create_skill_request
from app.skillsmith import SkillsmithError, draft_temporary_skill


def run_task(
    task_text: str,
    skills_dir: Path,
    runs_dir: Path,
    create_temporary_skills: bool = True,
    allow_scripted_skills: bool = False,
) -> AgentRunResult:
    run_id = new_run_id()
    temporary_skills_root = _temporary_skills_root(runs_dir, run_id)
    trace: list[str] = []
    trace_events: list[TraceEvent] = []

    _record_trace(trace, trace_events, "PLANNING", run_id=run_id)
    plan = plan_task(task_text)

    preflight_safety_decision = check_task_safety(plan.task)
    registry: SkillRegistry | None = None
    if preflight_safety_decision is not None:
        decisions = [preflight_safety_decision]
    else:
        _record_trace(trace, trace_events, "CHECKING_SKILLS", run_id=run_id)
        registry = SkillRegistry.load(skills_dir, allow_scripts=allow_scripted_skills)

        _record_trace(trace, trace_events, "ROUTING", run_id=run_id)
        decisions = check_capabilities(plan.capabilities, registry)

    governor_decisions = [evaluate_governor(decision) for decision in decisions]
    for governor_decision in governor_decisions:
        _record_trace(
            trace,
            trace_events,
            "GOVERNOR_DECIDED",
            capability=governor_decision.capability,
            decision=governor_decision.decision,
            dominant_signal=governor_decision.dominant_signal,
            approval_required=governor_decision.approval_required,
            risk_level=governor_decision.risk_level,
            confidence=governor_decision.confidence,
            reversibility=governor_decision.reversibility,
            run_id=run_id,
        )

    loaded_logs: list[LoadedSkillLog] = []
    script_execution_logs: list[ScriptExecutionLog] = []
    skill_requests: list[dict] = []
    skill_repair_requests: list[dict] = []
    route_load_failed = False
    exit_code = 0
    for decision in decisions:
        if decision.decision == "ABORT_UNSAFE":
            _record_trace(
                trace,
                trace_events,
                "UNSAFE_ABORTED",
                capability=decision.capability,
                reason=decision.reason,
                run_id=run_id,
            )
            exit_code = 1
            continue

        if decision.decision == "ASK_HUMAN":
            _record_trace(
                trace,
                trace_events,
                "SAFETY_REVIEW_REQUIRED",
                capability=decision.capability,
                reason=decision.reason,
                run_id=run_id,
            )
            exit_code = 1
            continue

        if decision.decision != "USE_SKILL" or decision.selected_skill is None:
            _record_trace(
                trace,
                trace_events,
                "BLOCKED_MISSING_SKILL",
                capability=decision.capability,
                decision=decision.decision,
                run_id=run_id,
            )
            _record_trace(
                trace,
                trace_events,
                "REQUESTING_SKILL",
                capability=decision.capability,
                run_id=run_id,
            )
            skill_request = create_skill_request(
                plan.task_id,
                decision,
                _matching_governor_decision(decision.capability, governor_decisions),
            )
            skill_requests.append(skill_request.model_dump(mode="json"))
            if not create_temporary_skills:
                exit_code = 1
                continue

            _record_trace(
                trace,
                trace_events,
                "DRAFTING_TEMP_SKILL",
                skill_name=skill_request.desired_skill_name,
                run_id=run_id,
            )
            try:
                temp_result = draft_temporary_skill(
                    skill_request,
                    temporary_skills_root,
                    run_id=run_id,
                )
            except SkillsmithError as exc:
                skill_requests[-1]["temporary_skill_error"] = str(exc)
                _record_trace(
                    trace,
                    trace_events,
                    "VALIDATION_FAILED",
                    skill_name=skill_request.desired_skill_name,
                    reason=str(exc),
                    run_id=run_id,
                )
                _record_trace(
                    trace,
                    trace_events,
                    "REQUESTING_REPAIR",
                    skill_name=skill_request.desired_skill_name,
                    run_id=run_id,
                )
                repair_request = create_skill_repair_request(skill_request, [str(exc)], None)
                skill_repair_requests.append(repair_request.model_dump(mode="json"))
                exit_code = 1
                continue
            skill_requests[-1]["temporary_skill"] = temp_result.model_dump(mode="json")
            if not temp_result.validation_passed:
                _record_trace(
                    trace,
                    trace_events,
                    "VALIDATION_FAILED",
                    skill_name=temp_result.skill_name,
                    reasons=temp_result.validation_reasons,
                    run_id=run_id,
                )
                _record_trace(
                    trace,
                    trace_events,
                    "REQUESTING_REPAIR",
                    skill_name=temp_result.skill_name,
                    run_id=run_id,
                )
                repair_request = create_skill_repair_request(
                    skill_request,
                    temp_result.validation_reasons,
                    str(temp_result.skill_path),
                )
                skill_repair_requests.append(repair_request.model_dump(mode="json"))
                exit_code = 1
                continue

            _record_trace(
                trace,
                trace_events,
                "VALIDATION_PASSED",
                skill_name=temp_result.skill_name,
                run_id=run_id,
            )
            _record_trace(
                trace,
                trace_events,
                "LOADING_TEMP_SKILL",
                skill_name=temp_result.skill_name,
                run_id=run_id,
            )
            registry = SkillRegistry.load(
                skills_dir,
                allow_scripts=allow_scripted_skills,
                temporary_skill_roots=[temporary_skills_root],
                run_id=run_id,
            )
            record = registry.get(temp_result.skill_name)
            if not _is_current_run_temporary_record(record, temporary_skills_root, run_id):
                _record_trace(
                    trace,
                    trace_events,
                    "VALIDATION_FAILED",
                    skill_name=temp_result.skill_name,
                    reason="validated temporary skill could not be loaded from current-run overlay",
                    run_id=run_id,
                )
                _record_trace(
                    trace,
                    trace_events,
                    "REQUESTING_REPAIR",
                    skill_name=temp_result.skill_name,
                    run_id=run_id,
                )
                repair_request = create_skill_repair_request(
                    skill_request,
                    ["validated temporary skill could not be loaded from current-run overlay"],
                    str(temp_result.skill_path),
                )
                skill_repair_requests.append(repair_request.model_dump(mode="json"))
                exit_code = 1
                continue

            try:
                loaded = load_skill(record, skills_dir, decision.capability, skill_request.reason)
            except SkillLoadError as exc:
                _record_trace(
                    trace,
                    trace_events,
                    "ROUTE_LOAD_FAILED",
                    skill_name=temp_result.skill_name,
                    reason=str(exc),
                    run_id=run_id,
                )
                route_load_failed = True
                exit_code = 1
                continue
            temp_result.loaded = True
            skill_requests[-1]["temporary_skill"] = temp_result.model_dump(mode="json")
            loaded_logs.append(
                LoadedSkillLog(
                    name=loaded.name,
                    version=loaded.version,
                    path=str(loaded.path),
                    loaded_for_capability=loaded.loaded_for_capability,
                    load_reason=loaded.load_reason,
                    temporary=True,
                    lifecycle=temp_result.lifecycle,
                )
            )
            continue

        record = registry.get(decision.selected_skill)
        if record is None:
            _record_trace(
                trace,
                trace_events,
                "BLOCKED_MISSING_SKILL",
                capability=decision.capability,
                selected_skill=decision.selected_skill,
                run_id=run_id,
            )
            _record_trace(
                trace,
                trace_events,
                "REQUESTING_SKILL",
                capability=decision.capability,
                run_id=run_id,
            )
            skill_request = create_skill_request(
                plan.task_id,
                decision,
                _matching_governor_decision(decision.capability, governor_decisions),
            )
            skill_requests.append(skill_request.model_dump(mode="json"))
            route_load_failed = True
            exit_code = 1
            continue

        _record_trace(
            trace,
            trace_events,
            "LOADING_SKILL",
            skill_name=record.name,
            capability=decision.capability,
            run_id=run_id,
        )
        try:
            loaded = load_skill(record, skills_dir, decision.capability, decision.reason)
        except SkillLoadError as exc:
            _record_trace(
                trace,
                trace_events,
                "ROUTE_LOAD_FAILED",
                skill_name=record.name,
                reason=str(exc),
                run_id=run_id,
            )
            route_load_failed = True
            exit_code = 1
            continue
        loaded_logs.append(
            LoadedSkillLog(
                name=loaded.name,
                version=loaded.version,
                path=str(loaded.path),
                loaded_for_capability=loaded.loaded_for_capability,
                load_reason=loaded.load_reason,
            )
        )
        if record.script is not None and allow_scripted_skills:
            _record_trace(
                trace,
                trace_events,
                "EXECUTING_SCRIPT",
                skill_name=record.name,
                run_id=run_id,
            )
            script_log = execute_scripted_skill(record, {"task": task_text, "text": task_text})
            script_execution_logs.append(script_log)
            if _script_failed(script_log):
                exit_code = 1

    if any(decision.decision in {"ASK_HUMAN", "ABORT_UNSAFE"} for decision in decisions):
        _record_trace(trace, trace_events, "SAFETY_STOP_COMPLETE", run_id=run_id)
    else:
        _record_trace(trace, trace_events, "ROUTE_COMPLETE", run_id=run_id)

    rejected_skills = [
        rejection.model_dump(mode="json")
        for rejection in (registry.rejections() if registry is not None else [])
    ]
    result_category = _result_category(
        exit_code,
        decisions=[decision.model_dump(mode="json") for decision in decisions],
        skill_requests=skill_requests,
        skill_repair_requests=skill_repair_requests,
        script_executions=script_execution_logs,
        route_load_failed=route_load_failed,
    )
    execution_summary = _build_execution_summary(
        loaded_logs=loaded_logs,
        skill_requests=skill_requests,
        skill_repair_requests=skill_repair_requests,
        rejected_skills=rejected_skills,
        script_executions=script_execution_logs,
        decisions=[decision.model_dump(mode="json") for decision in decisions],
        result_category=result_category,
    )
    input_requests = _build_input_requests(
        decisions=[decision.model_dump(mode="json") for decision in decisions],
        skill_repair_requests=skill_repair_requests,
        run_id=run_id,
    )

    _record_trace(trace, trace_events, "RUN_LOG_WRITTEN", run_id=run_id)
    run_log = RunLog(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        task_id=plan.task_id,
        task=plan.task,
        created_at=datetime.now(),
        exit_code=exit_code,
        result_category=result_category,
        plan=[capability.capability for capability in plan.capabilities],
        capability_decisions=[decision.model_dump(mode="json") for decision in decisions],
        governor_decisions=governor_decisions,
        skills_loaded=loaded_logs,
        script_executions=script_execution_logs,
        skill_requests=skill_requests,
        skill_repair_requests=skill_repair_requests,
        input_requests=input_requests,
        rejected_skills=rejected_skills,
        trace=trace,
        trace_events=trace_events,
        execution_summary=execution_summary,
    )
    path = write_run_log(run_log, runs_dir)
    try:
        record_run_in_candidate_ledger(run_log, runs_dir)
    except Exception as exc:
        _record_trace(
            trace,
            trace_events,
            "LEDGER_RECORD_FAILED",
            message="Skill Candidate Ledger update failed; run log remains source evidence.",
            error=str(exc),
        )
        run_log.trace = trace
        run_log.trace_events = trace_events
        path = rewrite_run_log(path, run_log)
    return AgentRunResult(run_log=run_log, run_log_path=path, exit_code=exit_code)


def _temporary_skills_root(runs_dir: Path, run_id: str) -> Path:
    return runs_dir / "artifacts" / run_id / "skills"


def _is_current_run_temporary_record(record: Any, temporary_root: Path, run_id: str) -> bool:
    if record is None:
        return False
    return bool(
        record.source_root.resolve() == temporary_root.resolve()
        and record.lifecycle.temporary
        and record.lifecycle.run_id == run_id
    )


def _matching_governor_decision(capability: str, governor_decisions: list[Any]) -> Any:
    for decision in governor_decisions:
        if decision.capability == capability:
            return decision
    raise RuntimeError(f"missing governor decision for requested capability: {capability}")


def _record_trace(
    trace: list[str],
    trace_events: list[TraceEvent],
    stage: str,
    message: str = "",
    **details: Any,
) -> None:
    trace.append(stage)
    trace_events.append(
        TraceEvent(
            sequence=len(trace_events) + 1,
            stage=stage,
            message=message,
            details={key: value for key, value in details.items() if value is not None},
        )
    )


def _result_category(
    exit_code: int,
    decisions: list[dict],
    skill_requests: list[dict],
    skill_repair_requests: list[dict],
    script_executions: list[ScriptExecutionLog],
    route_load_failed: bool = False,
) -> RunResultCategory:
    decision_types = {decision.get("decision") for decision in decisions}
    if "ABORT_UNSAFE" in decision_types:
        return "unsafe_aborted"
    if "ASK_HUMAN" in decision_types:
        return "awaiting_human_approval"
    if skill_repair_requests:
        return "repair_requested"
    if route_load_failed:
        return "route_load_failed"
    if any(_script_failed(execution) for execution in script_executions):
        return "script_failed"
    if exit_code and skill_requests:
        return "blocked_missing_skill"
    if exit_code:
        return "route_load_failed"
    return "success"


def _build_execution_summary(
    loaded_logs: list[LoadedSkillLog],
    skill_requests: list[dict],
    skill_repair_requests: list[dict],
    rejected_skills: list[dict],
    script_executions: list[ScriptExecutionLog],
    decisions: list[dict],
    result_category: RunResultCategory,
) -> ExecutionSummary:
    temporary_skill_names = _unique(
        [skill.name for skill in loaded_logs if skill.temporary]
        + [
            temporary["skill_name"]
            for request in skill_requests
            if isinstance((temporary := request.get("temporary_skill")), dict)
            and temporary.get("skill_name")
        ]
    )
    safety_decisions = [
        f"{decision.get('decision')}:{decision.get('capability')}"
        for decision in decisions
        if decision.get("decision") in {"ASK_HUMAN", "ABORT_UNSAFE"}
    ]
    failed_scripts = [
        execution.skill_name for execution in script_executions if _script_failed(execution)
    ]

    return ExecutionSummary(
        loaded_skills=_unique([skill.name for skill in loaded_logs]),
        temporary_skills=temporary_skill_names,
        requested_skills=_unique(
            [
                request["desired_skill_name"]
                for request in skill_requests
                if request.get("desired_skill_name")
            ]
        ),
        repair_requested_skills=_unique(
            [request["skill_name"] for request in skill_repair_requests if request.get("skill_name")]
        ),
        rejected_skills=_unique(
            [
                str(rejection.get("name") or rejection.get("path"))
                for rejection in rejected_skills
                if rejection.get("name") or rejection.get("path")
            ]
        ),
        script_executions=[execution.skill_name for execution in script_executions],
        failed_scripts=failed_scripts,
        safety_decisions=safety_decisions,
        skill_request_count=len(skill_requests),
        skill_repair_request_count=len(skill_repair_requests),
        rejected_skill_count=len(rejected_skills),
        script_execution_count=len(script_executions),
        failed_script_count=len(failed_scripts),
        safety_decision_count=len(safety_decisions),
        result_category=result_category,
    )


def _build_input_requests(
    decisions: list[dict],
    skill_repair_requests: list[dict],
    run_id: str,
) -> list[Any]:
    requests = [
        safety_input_request(decision, run_id)
        for decision in decisions
        if decision.get("decision") == "ASK_HUMAN"
    ]
    requests.extend(
        repair_input_request(repair_request, run_id)
        for repair_request in skill_repair_requests
    )
    return requests


def _script_failed(execution: ScriptExecutionLog) -> bool:
    return bool(execution.timed_out or execution.returncode != 0 or execution.failure_category)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
