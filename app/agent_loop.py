from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.capability_checker import check_capabilities
from app.loader import load_skill
from app.models import AgentRunResult, LoadedSkillLog, RunLog
from app.planner import plan_task
from app.registry import SkillRegistry
from app.run_log import write_run_log
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
    trace: list[str] = ["PLANNING"]
    plan = plan_task(task_text)

    trace.append("CHECKING_SKILLS")
    registry = SkillRegistry.load(skills_dir, allow_scripts=allow_scripted_skills)

    trace.append("ROUTING")
    decisions = check_capabilities(plan.capabilities, registry)

    loaded_logs: list[LoadedSkillLog] = []
    script_execution_logs = []
    skill_requests: list[dict] = []
    skill_repair_requests: list[dict] = []
    exit_code = 0
    for decision in decisions:
        if decision.decision != "USE_SKILL" or decision.selected_skill is None:
            trace.append("BLOCKED_MISSING_SKILL")
            trace.append("REQUESTING_SKILL")
            skill_request = create_skill_request(plan.task_id, decision)
            skill_requests.append(skill_request.model_dump(mode="json"))
            if not create_temporary_skills:
                exit_code = 1
                continue

            trace.append("DRAFTING_TEMP_SKILL")
            try:
                temp_result = draft_temporary_skill(skill_request, skills_dir)
            except SkillsmithError as exc:
                skill_requests[-1]["temporary_skill_error"] = str(exc)
                trace.append("VALIDATION_FAILED")
                trace.append("REQUESTING_REPAIR")
                repair_request = create_skill_repair_request(skill_request, [str(exc)], None)
                skill_repair_requests.append(repair_request.model_dump(mode="json"))
                exit_code = 1
                continue
            skill_requests[-1]["temporary_skill"] = temp_result.model_dump(mode="json")
            if not temp_result.validation_passed:
                trace.append("VALIDATION_FAILED")
                trace.append("REQUESTING_REPAIR")
                repair_request = create_skill_repair_request(
                    skill_request,
                    temp_result.validation_reasons,
                    str(temp_result.skill_path),
                )
                skill_repair_requests.append(repair_request.model_dump(mode="json"))
                exit_code = 1
                continue

            trace.append("VALIDATION_PASSED")
            trace.append("LOADING_TEMP_SKILL")
            registry = SkillRegistry.load(skills_dir, allow_scripts=allow_scripted_skills)
            record = registry.get(temp_result.skill_name)
            if record is None:
                trace.append("VALIDATION_FAILED")
                trace.append("REQUESTING_REPAIR")
                repair_request = create_skill_repair_request(
                    skill_request,
                    ["validated temporary skill could not be loaded from registry"],
                    str(temp_result.skill_path),
                )
                skill_repair_requests.append(repair_request.model_dump(mode="json"))
                exit_code = 1
                continue

            loaded = load_skill(record, skills_dir, decision.capability, skill_request.reason)
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
                )
            )
            continue

        record = registry.get(decision.selected_skill)
        if record is None:
            trace.append("BLOCKED_MISSING_SKILL")
            trace.append("REQUESTING_SKILL")
            skill_request = create_skill_request(plan.task_id, decision)
            skill_requests.append(skill_request.model_dump(mode="json"))
            exit_code = 1
            continue

        trace.append("LOADING_SKILL")
        loaded = load_skill(record, skills_dir, decision.capability, decision.reason)
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
            trace.append("EXECUTING_SCRIPT")
            script_log = execute_scripted_skill(record, {"task": task_text, "text": task_text})
            script_execution_logs.append(script_log)
            if script_log.returncode != 0:
                exit_code = 1

    trace.append("ROUTE_COMPLETE")

    run_log = RunLog(
        task_id=plan.task_id,
        task=plan.task,
        created_at=datetime.now(),
        exit_code=exit_code,
        plan=[capability.capability for capability in plan.capabilities],
        capability_decisions=[decision.model_dump(mode="json") for decision in decisions],
        skills_loaded=loaded_logs,
        script_executions=script_execution_logs,
        skill_requests=skill_requests,
        skill_repair_requests=skill_repair_requests,
        rejected_skills=[rejection.model_dump(mode="json") for rejection in registry.rejections()],
        trace=trace,
    )
    run_log.trace.append("RUN_LOG_WRITTEN")
    path = write_run_log(run_log, runs_dir)
    return AgentRunResult(run_log=run_log, run_log_path=path, exit_code=exit_code)
