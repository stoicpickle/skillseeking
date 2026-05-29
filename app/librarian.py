from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.models import LibraryHealthReport, SkillHealthIssue, SkillUsageMetrics
from app.registry import SkillRegistry


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
        for loaded in log.get("skills_loaded", []):
            name = loaded.get("name")
            if not name:
                continue
            metrics = metrics_by_name.setdefault(name, SkillUsageMetrics(name=name))
            metrics.uses += 1
            metrics.last_used = max(filter(None, [metrics.last_used, created_at]), default=None)
            if loaded.get("temporary"):
                metrics.temporary_uses += 1
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
            if temporary and not temporary.get("validation_passed", False):
                issues.append(
                    SkillHealthIssue(
                        severity="warning",
                        code="temporary_validation_failed",
                        skill_name=temporary.get("skill_name") or requested_name,
                        message=f"Temporary skill failed validation for request {request.get('id', 'unknown')}",
                    )
                )

        for execution in log.get("script_executions", []):
            name = execution.get("skill_name")
            if not name:
                continue
            returncode = _safe_int(execution.get("returncode", 0), default=1)
            if execution.get("timed_out") or returncode != 0:
                metrics = metrics_by_name.setdefault(name, SkillUsageMetrics(name=name))
                metrics.script_failures += 1
                issues.append(
                    SkillHealthIssue(
                        severity="critical",
                        code="script_execution_failed",
                        skill_name=name,
                        message=f"Script failed or timed out in run {log.get('task_id', 'unknown')}",
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
            logs.append(data)
    return logs


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
