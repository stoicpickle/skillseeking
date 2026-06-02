from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.models import LibraryHealthReport, SkillHealthIssue, SkillUsageMetrics
from app.registry import SkillRegistry
from app.skill_candidate_ledger import SkillCandidateLedgerError, ledger_path, load_candidate_ledger


def analyze_library(
    skills_dir: Path,
    runs_dir: Path,
    allow_scripts: bool = False,
) -> LibraryHealthReport:
    registry = SkillRegistry.load(skills_dir, allow_scripts=allow_scripts)
    metrics_by_name: dict[str, SkillUsageMetrics] = {
        record.name: SkillUsageMetrics(name=record.name) for record in registry.list_records()
    }
    issues: list[SkillHealthIssue] = []
    result_categories: dict[str, int] = defaultdict(int)
    temporary_outcomes: dict[str, int] = defaultdict(int)
    script_failure_categories: dict[str, int] = defaultdict(int)
    repair_requests = 0
    safety_stops = 0
    human_approval_waits = 0
    route_load_failures = 0
    candidate_count = 0
    candidate_status_counts: dict[str, int] = defaultdict(int)
    blocked_candidate_count = 0
    duplicate_candidate_count = 0
    human_gated_candidate_count = 0

    try:
        ledger = load_candidate_ledger(runs_dir)
    except SkillCandidateLedgerError as exc:
        ledger = None
        issues.append(
            SkillHealthIssue(
                severity="warning",
                code="candidate_ledger_unreadable",
                skill_name=None,
                message=str(exc),
            )
        )

    if ledger is not None:
        candidate_count = len(ledger.entries)
        for entry in ledger.entries:
            candidate_status_counts[entry.status] += 1
            if entry.status == "blocked":
                blocked_candidate_count += 1
                issues.append(
                    SkillHealthIssue(
                        severity="warning",
                        code="candidate_blocked",
                        skill_name=entry.skill_name,
                        message=entry.block_reason or entry.quarantine_reason or "Candidate is blocked.",
                    )
                )
            if entry.duplicate_of:
                duplicate_candidate_count += 1
                issues.append(
                    SkillHealthIssue(
                        severity="warning",
                        code="candidate_duplicate",
                        skill_name=entry.skill_name,
                        message=f"Candidate duplicates {entry.duplicate_of}: {'; '.join(entry.duplicate_evidence) or 'matching contract'}",
                    )
                )
            if entry.human_approval_required:
                human_gated_candidate_count += 1
            if entry.validation_failure_count:
                issues.append(
                    SkillHealthIssue(
                        severity="warning",
                        code="candidate_validation_failed",
                        skill_name=entry.skill_name,
                        message=f"Candidate has {entry.validation_failure_count} validation failure(s) in {ledger_path(runs_dir)}.",
                    )
                )

    for rejection in registry.rejections():
        issues.append(
            SkillHealthIssue(
                severity="warning",
                code="rejected_skill",
                skill_name=rejection.name,
                message=f"{rejection.path}: {'; '.join(rejection.reasons)}",
            )
        )

    duplicate_groups = _duplicate_contract_groups(registry)
    for names in duplicate_groups:
        issues.append(
            SkillHealthIssue(
                severity="warning",
                code="duplicate_contract",
                skill_name=None,
                message=f"Skills share the same input/output contract: {', '.join(names)}",
            )
        )

    logs = _load_run_logs(runs_dir)
    for log in logs:
        created_at = str(log.get("created_at", ""))
        exit_code = _safe_int(log.get("exit_code", 0))
        result_category = _result_category(log, exit_code)
        result_categories[result_category] += 1
        if result_category == "awaiting_human_approval":
            human_approval_waits += 1
        elif result_category == "unsafe_aborted":
            safety_stops += 1
        elif result_category == "route_load_failed":
            route_load_failures += 1

        repairs = log.get("skill_repair_requests", [])
        if isinstance(repairs, list):
            repair_requests += len(repairs)

        for loaded in log.get("skills_loaded", []):
            name = loaded.get("name")
            if not name:
                continue
            metrics = metrics_by_name.setdefault(name, SkillUsageMetrics(name=name))
            metrics.uses += 1
            metrics.last_used = max(filter(None, [metrics.last_used, created_at]), default=None)
            if loaded.get("temporary"):
                metrics.temporary_uses += 1
                temporary_outcomes["loaded"] += 1
            if exit_code:
                issues.append(
                    SkillHealthIssue(
                        severity="warning",
                        code="used_in_failed_run",
                        skill_name=name,
                        message=f"Skill was loaded in failed run {log.get('task_id', 'unknown')}",
                    )
                )

        for request in log.get("skill_requests", []):
            requested_name = request.get("desired_skill_name")
            if requested_name:
                metrics = metrics_by_name.setdefault(
                    requested_name, SkillUsageMetrics(name=requested_name)
                )
                metrics.requests += 1
            temporary = request.get("temporary_skill") or {}
            if temporary:
                if temporary.get("validation_passed", False):
                    temporary_outcomes["validation_passed"] += 1
                else:
                    temporary_outcomes["validation_failed"] += 1
                    issues.append(
                        SkillHealthIssue(
                            severity="warning",
                            code="temporary_validation_failed",
                            skill_name=temporary.get("skill_name") or requested_name,
                            message=f"Temporary skill failed validation for request {request.get('id', 'unknown')}",
                        )
                    )
                if temporary.get("loaded"):
                    temporary_outcomes["request_loaded"] += 1
                else:
                    temporary_outcomes["request_not_loaded"] += 1

        for execution in log.get("script_executions", []):
            name = execution.get("skill_name")
            if not name:
                continue
            returncode = _safe_int(execution.get("returncode", 0), default=1)
            failure_category = execution.get("failure_category")
            failed = bool(execution.get("timed_out") or returncode != 0 or failure_category)
            if failed:
                category = str(failure_category or ("timeout" if execution.get("timed_out") else "nonzero_exit"))
                metrics = metrics_by_name.setdefault(name, SkillUsageMetrics(name=name))
                metrics.script_failures += 1
                metrics.script_failure_categories[category] = metrics.script_failure_categories.get(category, 0) + 1
                script_failure_categories[category] += 1
                issues.append(
                    SkillHealthIssue(
                        severity="critical",
                        code="script_execution_failed",
                        skill_name=name,
                        message=f"Script failed ({category}) in run {log.get('run_id') or log.get('task_id', 'unknown')}",
                    )
                )

    for name, metrics in sorted(metrics_by_name.items()):
        if metrics.uses == 0 and metrics.requests == 0:
            issues.append(
                SkillHealthIssue(
                    severity="info",
                    code="unused_skill",
                    skill_name=name,
                    message="Skill has no observed uses or requests in available run logs.",
                )
            )

    return LibraryHealthReport(
        accepted_skills=len(registry.list_records()),
        rejected_skills=len(registry.rejections()),
        run_logs_read=len(logs),
        metrics=sorted(metrics_by_name.values(), key=lambda metric: metric.name),
        issues=issues,
        result_categories=dict(sorted(result_categories.items())),
        temporary_outcomes=dict(sorted(temporary_outcomes.items())),
        repair_requests=repair_requests,
        safety_stops=safety_stops,
        human_approval_waits=human_approval_waits,
        route_load_failures=route_load_failures,
        script_failure_categories=dict(sorted(script_failure_categories.items())),
        candidate_count=candidate_count,
        candidate_status_counts=dict(sorted(candidate_status_counts.items())),
        blocked_candidate_count=blocked_candidate_count,
        duplicate_candidate_count=duplicate_candidate_count,
        human_gated_candidate_count=human_gated_candidate_count,
    )


def _load_run_logs(runs_dir: Path) -> list[dict[str, Any]]:
    logs: list[dict[str, Any]] = []
    if not runs_dir.exists():
        return logs
    for path in sorted(runs_dir.glob("run_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            logs.append(_normalize_run_log(data))
    return logs


def _normalize_run_log(data: dict[str, Any]) -> dict[str, Any]:
    if "schema_version" not in data:
        data["schema_version"] = 1
    if "run_id" not in data:
        data["run_id"] = None
    return data


def _result_category(log: dict[str, Any], exit_code: int) -> str:
    explicit = log.get("result_category")
    if explicit:
        return str(explicit)
    decisions = {decision.get("decision") for decision in log.get("capability_decisions", [])}
    if "ABORT_UNSAFE" in decisions:
        return "unsafe_aborted"
    if "ASK_HUMAN" in decisions:
        return "awaiting_human_approval"
    if log.get("skill_repair_requests"):
        return "repair_requested"
    if any(_script_log_failed(execution) for execution in log.get("script_executions", [])):
        return "script_failed"
    if exit_code and log.get("skill_requests"):
        return "blocked_missing_skill"
    if exit_code:
        return "route_load_failed"
    return "success"


def _script_log_failed(execution: dict[str, Any]) -> bool:
    return bool(
        execution.get("timed_out")
        or _safe_int(execution.get("returncode", 0), default=1) != 0
        or execution.get("failure_category")
    )


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _duplicate_contract_groups(registry: SkillRegistry) -> list[list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for record in registry.list_records():
        key = json.dumps(
            {"input": record.input_schema, "output": record.output_schema},
            sort_keys=True,
        )
        grouped[key].append(record.name)
    return [sorted(names) for names in grouped.values() if len(names) > 1]
