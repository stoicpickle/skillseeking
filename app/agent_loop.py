from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.capability_checker import check_capabilities
from app.loader import load_skill
from app.models import AgentRunResult, LoadedSkillLog, RunLog
from app.planner import plan_task
from app.registry import SkillRegistry
from app.run_log import write_run_log


def run_task(task_text: str, skills_dir: Path, runs_dir: Path) -> AgentRunResult:
    trace: list[str] = ["PLANNING"]
    plan = plan_task(task_text)

    trace.append("CHECKING_SKILLS")
    registry = SkillRegistry.load(skills_dir)

    trace.append("ROUTING")
    decisions = check_capabilities(plan.capabilities, registry)

    loaded_logs: list[LoadedSkillLog] = []
    exit_code = 0
    for decision in decisions:
        if decision.decision != "USE_SKILL" or decision.selected_skill is None:
            trace.append("BLOCKED_NO_EXISTING_SKILL")
            exit_code = 1
            continue

        record = registry.get(decision.selected_skill)
        if record is None:
            trace.append("BLOCKED_NO_EXISTING_SKILL")
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

    trace.append("ROUTE_COMPLETE")

    run_log = RunLog(
        task_id=plan.task_id,
        task=plan.task,
        created_at=datetime.now(),
        plan=[capability.capability for capability in plan.capabilities],
        capability_decisions=[decision.model_dump(mode="json") for decision in decisions],
        skills_loaded=loaded_logs,
        skill_requests=[],
        rejected_skills=[rejection.model_dump(mode="json") for rejection in registry.rejections()],
        trace=trace,
    )
    run_log.trace.append("RUN_LOG_WRITTEN")
    path = write_run_log(run_log, runs_dir)
    return AgentRunResult(run_log=run_log, run_log_path=path, exit_code=exit_code)
