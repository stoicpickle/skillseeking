from __future__ import annotations

from collections.abc import Iterable
import json

import typer

from app.models import (
    AgentRunResult,
    LoadedSkillLog,
    ScriptExecutionLog,
    SkillCandidateLedger,
    SkillCandidateLedgerEntry,
)
from app.registry import SkillRegistry
from app.skill_candidate_ledger import (
    candidate_review_queue_counts,
    candidate_review_queue_names,
    candidate_review_queues,
)


def emit_run_json(result: AgentRunResult) -> None:
    typer.echo(
        json.dumps(
            {
                "run_id": result.run_log.run_id,
                "task_id": result.run_log.task_id,
                "exit_code": result.exit_code,
                "result_category": result.run_log.result_category,
                "run_log_path": str(result.run_log_path),
                "execution_summary": result.run_log.execution_summary.model_dump(mode="json"),
                "decisions": result.run_log.capability_decisions,
                "governor_decisions": [
                    decision.model_dump(mode="json")
                    for decision in result.run_log.governor_decisions
                ],
                "skill_requests": result.run_log.skill_requests,
                "skill_repair_requests": result.run_log.skill_repair_requests,
                "script_executions": [execution.model_dump(mode="json") for execution in result.run_log.script_executions],
                "skills_loaded": [skill.model_dump(mode="json") for skill in result.run_log.skills_loaded],
                "rejected_skills": result.run_log.rejected_skills,
                "trace": result.run_log.trace,
                "trace_events": [event.model_dump(mode="json") for event in result.run_log.trace_events],
            },
            indent=2,
            sort_keys=True,
        )
    )


def emit_registry_json(registry: SkillRegistry) -> None:
    typer.echo(
        json.dumps(
            {
                "accepted": [record.model_dump(mode="json") for record in registry.list_records()],
                "rejected": [rejection.model_dump(mode="json") for rejection in registry.rejections()],
            },
            indent=2,
            sort_keys=True,
        )
    )


def emit_candidates_json(ledger: SkillCandidateLedger, ledger_path: str) -> None:
    entries = _sorted_candidate_entries(ledger.entries)
    review_queues = candidate_review_queues(ledger)
    typer.echo(
        json.dumps(
            {
                "ledger_path": ledger_path,
                "schema_version": ledger.schema_version,
                "candidate_count": len(entries),
                "status_counts": _candidate_status_counts(entries),
                "review_queue_counts": candidate_review_queue_counts(ledger),
                "review_queues": {
                    queue: [item.model_dump(mode="json") for item in items]
                    for queue, items in review_queues.items()
                    if items
                },
                "entries": [
                    {
                        **entry.model_dump(mode="json"),
                        "review_queues": candidate_review_queue_names(entry),
                    }
                    for entry in entries
                ],
                "auto_promotion_enabled": False,
            },
            indent=2,
            sort_keys=True,
        )
    )


def emit_candidates_output(ledger: SkillCandidateLedger, ledger_path: str) -> None:
    entries = _sorted_candidate_entries(ledger.entries)
    typer.echo("SKILL_CANDIDATES")
    typer.echo(f"Ledger: {ledger_path}")
    typer.echo(f"Schema version: {ledger.schema_version}")
    typer.echo(f"Candidate count: {len(entries)}")
    typer.echo(f"Status counts: {_candidate_status_counts(entries) or '-'}")
    typer.echo(f"Review queue counts: {candidate_review_queue_counts(ledger) or '-'}")
    typer.echo("Auto-promotion: disabled")
    if not entries:
        typer.echo("none")
        return
    for entry in entries:
        typer.echo("")
        typer.echo(f"Candidate: {entry.candidate_id}")
        typer.echo(f"Skill: {entry.skill_name}")
        typer.echo(f"Capability: {entry.capability}")
        typer.echo(f"Status: {entry.status}")
        typer.echo(f"Review queues: {_format_list(candidate_review_queue_names(entry))}")
        typer.echo(f"Requests: {entry.request_count}")
        typer.echo(
            "Validation: "
            f"passed={entry.validation_pass_count} failed={entry.validation_failure_count} "
            f"temporary_uses={entry.successful_temporary_uses}"
        )
        typer.echo(f"Safety flags: {_format_list(entry.safety_flags)}")
        typer.echo(f"Quarantine reason: {entry.quarantine_reason or '-'}")
        typer.echo(f"Block reason: {entry.block_reason or '-'}")
        typer.echo(f"Duplicate of: {entry.duplicate_of or '-'}")
        typer.echo(f"Repair requirements: {_format_list(entry.repair_requirements)}")
        typer.echo(f"Promotion requirements: {_format_list(entry.promotion_requirements)}")
        typer.echo(f"Promotion approval required: {entry.human_approval_required}")
        typer.echo(f"Promotion approved by: {entry.promotion_approved_by or '-'}")
        typer.echo(f"Promotion approved at: {entry.promotion_approved_at.isoformat() if entry.promotion_approved_at else '-'}")
        typer.echo(f"Promotion approval notes: {entry.promotion_approval_notes or '-'}")
        typer.echo(f"Evidence runs: {_format_list(entry.evidence_run_ids)}")


def emit_run_output(result: AgentRunResult) -> None:
    typer.echo("TRACE")
    for stage in result.run_log.trace:
        typer.echo(stage)

    typer.echo("")
    typer.echo("DECISIONS")
    for decision in result.run_log.capability_decisions:
        selected = decision.get("selected_skill") if decision["decision"] == "USE_SKILL" else None
        typer.echo(f"{decision['decision']} {selected or '-'} :: {decision['capability']}")

    _emit_safety_decisions(result.run_log.capability_decisions)
    _emit_skill_requests(result.run_log.skill_requests)
    _emit_skill_repair_requests(result.run_log.skill_repair_requests)
    _emit_script_executions(result.run_log.script_executions)
    _emit_result(result)


def _emit_safety_decisions(decisions: Iterable[dict]) -> None:
    for decision in decisions:
        if decision.get("decision") not in {"ASK_HUMAN", "ABORT_UNSAFE"}:
            continue
        typer.echo("")
        typer.echo("SAFETY")
        typer.echo(f"Decision: {decision['decision']}")
        typer.echo(f"Capability: {decision['capability']}")
        typer.echo(f"Reason: {decision['reason']}")
        typer.echo(f"Approval required: {decision.get('requires_human_approval', False)}")


def _emit_skill_requests(skill_requests: Iterable[dict]) -> None:
    for request in skill_requests:
        typer.echo("")
        typer.echo("BLOCKED")
        typer.echo(f"Missing capability: {request['missing_capability']}")
        typer.echo(f"Requested skill: {request['desired_skill_name']}")
        typer.echo(f"Risk: {request['risk_level']}")
        typer.echo(f"Status: {request['status']}")
        typer.echo(f"Request ID: {request['id']}")
        temporary = request.get("temporary_skill")
        if temporary:
            typer.echo(f"Temporary skill: {temporary['skill_name']}")
            typer.echo(f"Validation passed: {temporary['validation_passed']}")
            typer.echo(f"Loaded: {temporary['loaded']}")


def _emit_skill_repair_requests(skill_repair_requests: Iterable[dict]) -> None:
    for request in skill_repair_requests:
        typer.echo("")
        typer.echo("REPAIR_REQUESTED")
        typer.echo(f"Skill: {request['skill_name']}")
        typer.echo(f"Failed capability: {request['failed_capability']}")
        typer.echo(f"Status: {request['status']}")
        typer.echo(f"Repair ID: {request['id']}")
        typer.echo(f"Skill request ID: {request['skill_request_id']}")
        typer.echo(f"Objective: {request['repair_objective']}")
        for reason in request["failure_reasons"]:
            typer.echo(f"Failure reason: {reason}")


def _emit_script_executions(script_executions: Iterable[ScriptExecutionLog]) -> None:
    for execution in script_executions:
        typer.echo("")
        typer.echo("SCRIPT_EXECUTED")
        typer.echo(f"Skill: {execution.skill_name}")
        typer.echo(f"Return code: {execution.returncode}")
        typer.echo(f"Timed out: {execution.timed_out}")
        if execution.failure_category:
            typer.echo(f"Failure category: {execution.failure_category}")
        typer.echo(f"Output validated: {execution.output_validated}")
        if execution.stdout:
            typer.echo(f"Stdout: {execution.stdout}")
        if execution.stderr:
            typer.echo(f"Stderr: {execution.stderr}")


def _emit_result(result: AgentRunResult) -> None:
    loaded_names = _format_skill_names(result.run_log.skills_loaded)
    temporary_names = _format_skill_names(
        skill for skill in result.run_log.skills_loaded if skill.temporary
    )

    typer.echo("")
    typer.echo("RESULT")
    typer.echo(f"Run ID: {result.run_log.run_id}")
    typer.echo(f"Task ID: {result.run_log.task_id}")
    typer.echo(f"Result category: {result.run_log.result_category}")
    typer.echo(f"Exit code: {result.exit_code}")
    typer.echo(f"Loaded skills: {loaded_names}")
    typer.echo(f"Temporary skills: {temporary_names}")
    typer.echo(f"Run log: {result.run_log_path}")


def _format_skill_names(skills: Iterable[LoadedSkillLog]) -> str:
    names = [skill.name for skill in skills]
    if not names:
        return "-"
    return ", ".join(names)


def _sorted_candidate_entries(
    entries: Iterable[SkillCandidateLedgerEntry],
) -> list[SkillCandidateLedgerEntry]:
    return sorted(entries, key=lambda entry: (entry.status, entry.skill_name, entry.candidate_id))


def _candidate_status_counts(entries: Iterable[SkillCandidateLedgerEntry]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry.status] = counts.get(entry.status, 0) + 1
    return dict(sorted(counts.items()))


def _format_list(values: Iterable[str]) -> str:
    items = [value for value in values if value]
    return ", ".join(items) if items else "-"
