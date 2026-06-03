from __future__ import annotations

from collections.abc import Iterable
import json

import typer

from app.models import (
    AdmissionPlanReport,
    AdmissionSourceArtifact,
    AgentRunResult,
    DurableAdmissionPreviewReport,
    InputRequest,
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
from app.input_focus import candidate_input_requests


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
                "input_requests": [
                    request.model_dump(mode="json")
                    for request in result.run_log.input_requests
                ],
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
                        "input_requests": [
                            request.model_dump(mode="json")
                            for request in candidate_input_requests(entry)
                        ],
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
        _emit_candidate_next_action(entry)


def emit_admission_plan_json(report: AdmissionPlanReport) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_durable_admission_preview_json(report: DurableAdmissionPreviewReport) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_durable_admission_preview_output(report: DurableAdmissionPreviewReport) -> None:
    typer.echo("DURABLE_ADMISSION_PREVIEW")
    typer.echo(f"Candidate: {report.candidate_id}")
    typer.echo(f"Outcome: {report.outcome}")
    typer.echo(f"Ready for mutation preview: {str(report.ready_for_mutation_preview).lower()}")
    typer.echo(f"Dry run: {str(report.dry_run).lower()}")
    typer.echo(f"Mutation supported: {str(report.mutation_supported).lower()}")
    typer.echo(f"Durable skill installed: {str(report.durable_skill_installed).lower()}")
    typer.echo(f"Ledger mutated: {str(report.ledger_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(f"Resolution ledger mutated: {str(report.resolution_ledger_mutated).lower()}")
    typer.echo(f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}")

    typer.echo("")
    typer.echo("SOURCE")
    typer.echo(f"Source SKILL.md: {report.source_skill_path or '-'}")
    typer.echo(f"Source sha256: {report.source_sha256 or '-'}")

    typer.echo("")
    typer.echo("TARGET")
    typer.echo(f"Target skill dir: {report.target_skill_dir or '-'}")
    typer.echo(f"Target SKILL.md: {report.target_skill_path or '-'}")

    typer.echo("")
    typer.echo("WRITE_PLAN")
    typer.echo(f"Operation: {report.write_plan.operation}")
    typer.echo(f"Collision policy: {report.write_plan.collision_policy}")
    typer.echo(f"Permission policy: {report.write_plan.permission_policy}")
    typer.echo(f"Permission approval ID: {report.write_plan.permission_approval_id or '-'}")
    typer.echo(f"Replacement approved: {str(report.write_plan.replacement_approved).lower()}")
    typer.echo(
        "Permission widening approved: "
        f"{str(report.write_plan.permission_widening_approved).lower()}"
    )
    typer.echo(f"Snapshot dir: {report.write_plan.snapshot_dir or '-'}")
    typer.echo(f"Snapshot SKILL.md: {report.write_plan.snapshot_skill_path or '-'}")
    typer.echo(f"Snapshot sha256: {report.write_plan.snapshot_sha256 or '-'}")
    typer.echo(
        f"Source snapshot created: {str(report.write_plan.source_snapshot_created).lower()}"
    )
    typer.echo("Write blockers:")
    _emit_string_items(report.write_plan.blockers)

    typer.echo("")
    typer.echo("REQUIRED_HUMAN_RECORDS")
    _emit_string_items(report.required_human_records)

    typer.echo("")
    typer.echo("BLOCKERS")
    _emit_string_items(report.blockers)

    typer.echo("")
    typer.echo("WARNINGS")
    _emit_string_items(report.warnings)

    typer.echo("")
    typer.echo("NEXT_STEPS")
    _emit_string_items(report.next_steps)


def emit_admission_plan_output(report: AdmissionPlanReport) -> None:
    typer.echo("ADMISSION_PLAN")
    typer.echo(f"Candidate: {report.candidate_id}")
    typer.echo(f"Skill: {report.candidate.get('skill_name', '-')}")
    typer.echo(f"Status: {report.candidate.get('status', '-')}")
    typer.echo(f"Outcome: {report.outcome}")
    typer.echo(f"Ready for durable workflow review: {str(report.ready_for_durable_review).lower()}")
    typer.echo(f"Dry run: {str(report.dry_run).lower()}")
    typer.echo(f"Durable skill installed: {str(report.durable_skill_installed).lower()}")
    typer.echo(f"Ledger mutated: {str(report.ledger_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(f"Auto-promotion: {'enabled' if report.auto_promotion_enabled else 'disabled'}")
    typer.echo(f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}")

    typer.echo("")
    typer.echo("SOURCE")
    selected = _selected_source(report)
    if selected is None:
        typer.echo("Selected temporary SKILL.md: -")
        if report.selected_source_artifact:
            typer.echo(
                "Source warning: selected source artifact missing from report: "
                f"{report.selected_source_artifact}"
            )
        typer.echo("Source validation passed: -")
    else:
        typer.echo(f"Selected temporary SKILL.md: {selected.skill_path}")
        typer.echo(f"Source validation passed: {str(selected.validation_accepted).lower()}")
        typer.echo(f"Source skill: {selected.skill_name or '-'}")
        typer.echo(f"Source risk: {selected.risk_level or '-'}")
        typer.echo(f"Source permissions: {selected.permissions or '-'}")

    typer.echo("")
    typer.echo("EVIDENCE")
    if not report.evidence_runs:
        typer.echo("none")
    for run in report.evidence_runs:
        typer.echo(
            f"- run_id: {run.run_id} found={str(run.found).lower()} "
            f"validation_passed={_optional_bool(run.validation_passed)} "
            f"loaded={_optional_bool(run.loaded)}"
        )

    typer.echo("")
    typer.echo("DURABLE_REGISTRY")
    typer.echo(f"Accepted skills: {report.durable_registry.durable_registry_accepted_count}")
    typer.echo(f"Rejected skills: {report.durable_registry.durable_registry_rejected_count}")
    typer.echo(f"Name collision: {report.durable_registry.name_collision or 'none'}")
    typer.echo(f"Contract overlaps: {report.durable_registry.contract_overlaps or 'none'}")
    typer.echo(f"Permission widening: {_format_list(report.durable_registry.permission_widening)}")
    typer.echo(f"Scripted implications: {_format_list(report.durable_registry.scripted_implications)}")

    typer.echo("")
    typer.echo("PROMOTION_REQUIREMENTS")
    _emit_string_items(report.promotion_requirements)

    typer.echo("")
    typer.echo("BLOCKERS")
    _emit_string_items(report.blockers)

    typer.echo("")
    typer.echo("WARNINGS")
    _emit_string_items(report.warnings)

    typer.echo("")
    typer.echo("NEXT_STEPS")
    _emit_string_items(report.next_steps)
    if report.input_request is not None:
        typer.echo("")
        typer.echo("INPUT_NEEDED")
        _emit_input_request(report.input_request)


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
    _emit_input_requests(result.run_log.input_requests)
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


def _emit_input_requests(input_requests: Iterable[InputRequest]) -> None:
    requests = list(input_requests)
    if not requests:
        return
    typer.echo("")
    typer.echo("INPUT_NEEDED")
    for request in requests:
        _emit_input_request(request)


def _emit_input_request(request: InputRequest) -> None:
    typer.echo(f"Input: {request.id}")
    typer.echo(f"Kind: {request.kind}")
    typer.echo(f"Status: {request.status}")
    typer.echo(f"Title: {request.title}")
    typer.echo(f"Blocked scope: {request.blocked_scope}")
    typer.echo(f"Requested decision: {request.requested_decision}")
    if request.recommended_option:
        typer.echo(f"Recommended option: {request.recommended_option}")
    if request.evidence_refs:
        typer.echo(f"Evidence: {_format_list(request.evidence_refs)}")
    if request.next_commands:
        typer.echo("Suggested command:")
        for command in request.next_commands:
            typer.echo(f"  {command}")


def _emit_candidate_next_action(entry: SkillCandidateLedgerEntry) -> None:
    requests = candidate_input_requests(entry)
    if not requests:
        typer.echo("Recommended next action: -")
        typer.echo("Suggested command: -")
        typer.echo("Blocked scope: -")
        return
    request = requests[0]
    typer.echo(f"Recommended next action: {request.title}")
    typer.echo(f"Suggested command: {_format_list(request.next_commands)}")
    typer.echo(f"Blocked scope: {request.blocked_scope}")


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


def _emit_string_items(values: Iterable[str]) -> None:
    items = [value for value in values if value]
    if not items:
        typer.echo("none")
        return
    for value in items:
        typer.echo(f"- {value}")


def _optional_bool(value: bool | None) -> str:
    if value is None:
        return "-"
    return str(value).lower()


def _selected_source(report: AdmissionPlanReport) -> AdmissionSourceArtifact | None:
    if report.selected_source_artifact is None:
        return None
    for artifact in report.source_artifacts:
        if artifact.skill_path == report.selected_source_artifact:
            return artifact
    return None
