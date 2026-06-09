from __future__ import annotations

from collections.abc import Iterable
import json

import typer

from app.models import (
    AdmissionPlanReport,
    AdmissionSourceArtifact,
    AgentRunResult,
    CandidateDecisionReport,
    CandidateUsefulnessReport,
    DurableAdmissionPreviewReport,
    EvidenceCheckpointReport,
    EvidenceGovernorReport,
    InputRequest,
    LoadedSkillLog,
    NegativeEvidenceReport,
    OperatorDecisionItem,
    OperatorSummaryItem,
    OperatorSummaryReport,
    ScriptExecutionLog,
    ShadowActivationAcceptanceReport,
    ShadowActivationPlanReport,
    ShadowManagedWriteReport,
    ShadowRollbackPlanReport,
    StableReadinessReport,
    ShadowWriteGateReport,
    SkillCandidateLedger,
    SkillCandidateLedgerEntry,
    SkillReceiptReport,
)
from app.registry import SkillRegistry
from app.redaction import redact_data
from app.skill_candidate_ledger import (
    candidate_review_queue_counts,
    candidate_review_queue_names,
    candidate_review_queues,
)
from app.input_focus import candidate_input_requests


def emit_run_json(result: AgentRunResult) -> None:
    payload = {
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
        "script_executions": [
            execution.model_dump(mode="json")
            for execution in result.run_log.script_executions
        ],
        "skills_loaded": [skill.model_dump(mode="json") for skill in result.run_log.skills_loaded],
        "rejected_skills": result.run_log.rejected_skills,
        "trace": result.run_log.trace,
        "trace_events": [event.model_dump(mode="json") for event in result.run_log.trace_events],
        "security_warnings": result.run_log.security_warnings,
        "redactions_applied": result.run_log.redactions_applied,
    }
    typer.echo(
        json.dumps(
            redact_data(payload),
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


def emit_candidate_usefulness_json(report: CandidateUsefulnessReport) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_candidate_usefulness_output(report: CandidateUsefulnessReport) -> None:
    typer.echo("CANDIDATE_USEFULNESS")
    typer.echo(f"Candidate: {report.candidate_id}")
    typer.echo(f"Skill: {report.skill_name}")
    typer.echo(f"Capability: {report.capability}")
    typer.echo(f"Outcome: {report.outcome}")
    typer.echo(f"Usefulness supported: {str(report.usefulness_supported).lower()}")
    typer.echo(
        "Baseline comparison available: "
        f"{str(report.baseline_comparison_available).lower()}"
    )
    typer.echo(f"Successful temporary uses: {report.successful_temporary_uses}")
    typer.echo(
        "Validation: "
        f"passed={report.validation_pass_count} failed={report.validation_failure_count}"
    )
    typer.echo(
        "Admission plan: "
        f"{report.admission_plan_outcome or '-'} "
        f"ready={str(report.admission_plan_ready).lower()}"
    )

    typer.echo("")
    typer.echo("SUCCESSFUL_RUNS")
    _emit_string_items(report.matching_successful_run_ids)

    typer.echo("")
    typer.echo("EVIDENCE_RUNS")
    if not report.evidence_runs:
        typer.echo("none")
    for run in report.evidence_runs:
        typer.echo(
            f"- run_id: {run.run_id} found={str(run.found).lower()} "
            f"result={run.result_category or '-'} "
            f"validation_passed={_optional_bool(run.validation_passed)} "
            f"loaded={_optional_bool(run.loaded)} "
            f"successful={str(run.successful).lower()}"
        )
        if run.temporary_skill_paths:
            typer.echo(f"  temporary_skill_paths: {_format_list(run.temporary_skill_paths)}")

    typer.echo("")
    typer.echo("BASELINE_COMPARISON")
    if report.comparison is None:
        typer.echo("none")
    else:
        comparison = report.comparison
        typer.echo(f"Outcome: {comparison.outcome}")
        typer.echo(f"Summary: {comparison.summary}")
        typer.echo(
            f"Baseline: {comparison.baseline_run_id} "
            f"result={comparison.baseline_result_category or '-'} "
            f"temporary_present={str(comparison.baseline_temporary_skill_present).lower()} "
            f"temporary_loaded={str(comparison.baseline_temporary_skill_loaded).lower()}"
        )
        typer.echo(
            f"Treatment: {comparison.treatment_run_id} "
            f"result={comparison.treatment_result_category or '-'} "
            f"temporary_present={str(comparison.treatment_temporary_skill_present).lower()} "
            f"temporary_loaded={str(comparison.treatment_temporary_skill_loaded).lower()}"
        )
        if comparison.blockers:
            typer.echo(f"Blockers: {_format_list(comparison.blockers)}")
        if comparison.warnings:
            typer.echo(f"Warnings: {_format_list(comparison.warnings)}")

    typer.echo("")
    typer.echo("BLOCKERS")
    _emit_string_items(report.blockers)

    typer.echo("")
    typer.echo("WARNINGS")
    _emit_string_items(report.warnings)

    typer.echo("")
    typer.echo("MUTATION_BOUNDARY")
    typer.echo(f"Run logs mutated: {str(report.run_logs_mutated).lower()}")
    typer.echo(
        f"Candidate ledger mutated: {str(report.candidate_ledger_mutated).lower()}"
    )
    typer.echo(f"Durable skills mutated: {str(report.durable_skills_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(
        f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}"
    )

    typer.echo("")
    typer.echo("NEXT_STEPS")
    _emit_string_items(report.next_steps)


def emit_skill_receipt_json(report: SkillReceiptReport) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_skill_receipt_output(report: SkillReceiptReport) -> None:
    typer.echo("SKILL_RECEIPT")
    typer.echo(f"Candidate: {report.candidate_id}")
    typer.echo(f"Skill: {report.skill_name}")
    typer.echo(f"Capability: {report.capability}")
    typer.echo(f"Status: {report.status or '-'}")
    typer.echo(f"Outcome: {report.outcome}")
    typer.echo(f"Dry run: {str(report.dry_run).lower()}")

    typer.echo("")
    typer.echo("PROOFS")
    for proof in report.proofs:
        typer.echo(f"- {proof.category}: {proof.status}")
        typer.echo(f"  summary: {proof.summary}")
        if proof.evidence_refs:
            typer.echo(f"  evidence: {_format_list(proof.evidence_refs)}")
        if proof.blockers:
            typer.echo(f"  blockers: {_format_list(proof.blockers)}")
        if proof.warnings:
            typer.echo(f"  warnings: {_format_list(proof.warnings)}")

    preview = report.durable_admission_preview
    typer.echo("")
    typer.echo("RECEIPT_DIGESTS")
    typer.echo(f"Source sha256: {preview.source_sha256 or '-'}")
    typer.echo(f"Plan digest: {preview.write_plan.plan_digest or '-'}")
    typer.echo(
        "Plan approval verified: "
        f"{str(preview.write_plan.plan_approval_verified).lower()}"
    )

    typer.echo("")
    typer.echo("MUTATION_BOUNDARY")
    typer.echo(f"Run logs mutated: {str(report.run_logs_mutated).lower()}")
    typer.echo(
        f"Candidate ledger mutated: {str(report.candidate_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Resolution ledger mutated: {str(report.resolution_ledger_mutated).lower()}"
    )
    typer.echo(f"Durable skills mutated: {str(report.durable_skills_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(
        f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}"
    )

    typer.echo("")
    typer.echo("NEXT_STEPS")
    _emit_string_items(report.next_steps)


def emit_stable_readiness_json(report: StableReadinessReport) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_candidate_decision_json(report: CandidateDecisionReport) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_candidate_decision_output(report: CandidateDecisionReport) -> None:
    typer.echo("CANDIDATE_DECISION")
    typer.echo(f"Candidate: {report.candidate_id}")
    typer.echo(f"Skill: {report.skill_name or '-'}")
    typer.echo(f"Capability: {report.capability or '-'}")
    typer.echo(f"Decision: {report.decision}")
    typer.echo(f"Reason: {report.decision_reason}")
    typer.echo(f"Advisory only: {str(report.advisory_only).lower()}")
    typer.echo(f"Approval granted: {str(report.approval_granted).lower()}")
    typer.echo(f"Install authorized: {str(report.install_authorized).lower()}")
    typer.echo(
        "Stable review authorized: "
        f"{str(report.stable_review_authorized).lower()}"
    )
    typer.echo(
        "Stable promotion authorized: "
        f"{str(report.stable_promotion_authorized).lower()}"
    )
    typer.echo(f"Stable routing enabled: {str(report.stable_routing_enabled).lower()}")
    typer.echo(
        "Permission widening authorized: "
        f"{str(report.permission_widening_authorized).lower()}"
    )
    typer.echo(
        f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}"
    )
    typer.echo(f"Next command: {report.next_command}")

    typer.echo("")
    typer.echo("WHY")
    for item in report.why:
        typer.echo(f"- {item.source_report}:{item.signal}: {item.status}")
        typer.echo(f"  summary: {item.summary}")
        if item.evidence_refs:
            typer.echo(f"  evidence: {_format_list(item.evidence_refs)}")
        if item.blockers:
            typer.echo(f"  blockers: {_format_list(item.blockers)}")
        if item.warnings:
            typer.echo(f"  warnings: {_format_list(item.warnings)}")

    typer.echo("")
    typer.echo("SOURCE_REPORTS")
    _emit_string_items(report.source_reports)

    typer.echo("")
    typer.echo("BLOCKERS")
    _emit_string_items(report.blockers)

    typer.echo("")
    typer.echo("WARNINGS")
    _emit_string_items(report.warnings)

    typer.echo("")
    typer.echo("MUTATION_BOUNDARY")
    typer.echo(f"Run logs mutated: {str(report.run_logs_mutated).lower()}")
    typer.echo(
        f"Candidate ledger mutated: {str(report.candidate_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Resolution ledger mutated: {str(report.resolution_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Checkpoint ledger mutated: {str(report.checkpoint_ledger_mutated).lower()}"
    )
    typer.echo(f"Durable skills mutated: {str(report.durable_skills_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(
        f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}"
    )

    typer.echo("")
    typer.echo("NEXT_STEPS")
    _emit_string_items(report.next_steps)


def emit_stable_readiness_output(report: StableReadinessReport) -> None:
    typer.echo("STABLE_READINESS")
    typer.echo(f"Candidate: {report.candidate_id}")
    typer.echo(f"Skill: {report.skill_name}")
    typer.echo(f"Capability: {report.capability}")
    typer.echo(f"Candidate status: {report.candidate_status}")
    typer.echo(f"Outcome: {report.outcome}")
    typer.echo(
        "Ready for stable review: "
        f"{str(report.ready_for_stable_review).lower()}"
    )
    typer.echo(
        "Successful temporary uses: "
        f"{report.successful_temporary_uses}/{report.required_successful_temporary_uses}"
    )
    typer.echo(
        "Stable review approval required: "
        f"{str(report.stable_review_approval_required).lower()}"
    )
    typer.echo(f"Stable review authorized: {str(report.stable_review_authorized).lower()}")
    typer.echo(f"Advisory only: {str(report.advisory_only).lower()}")
    typer.echo(
        "Stable promotion authorized: "
        f"{str(report.stable_promotion_authorized).lower()}"
    )
    typer.echo(f"Stable routing enabled: {str(report.stable_routing_enabled).lower()}")

    typer.echo("")
    typer.echo("CHECKS")
    for check in report.checks:
        typer.echo(f"- {check.category}: {check.status}")
        typer.echo(f"  summary: {check.summary}")
        if check.evidence_refs:
            typer.echo(f"  evidence: {_format_list(check.evidence_refs)}")
        if check.blockers:
            typer.echo(f"  blockers: {_format_list(check.blockers)}")
        if check.warnings:
            typer.echo(f"  warnings: {_format_list(check.warnings)}")

    typer.echo("")
    typer.echo("BLOCKERS")
    _emit_string_items(report.blockers)

    typer.echo("")
    typer.echo("WARNINGS")
    _emit_string_items(report.warnings)

    typer.echo("")
    typer.echo("MUTATION_BOUNDARY")
    typer.echo(f"Run logs mutated: {str(report.run_logs_mutated).lower()}")
    typer.echo(
        f"Candidate ledger mutated: {str(report.candidate_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Resolution ledger mutated: {str(report.resolution_ledger_mutated).lower()}"
    )
    typer.echo(f"Durable skills mutated: {str(report.durable_skills_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(
        f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}"
    )

    typer.echo("")
    typer.echo("NEXT_STEPS")
    _emit_string_items(report.next_steps)


def emit_negative_evidence_json(report: NegativeEvidenceReport) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_negative_evidence_output(report: NegativeEvidenceReport) -> None:
    typer.echo("NEGATIVE_EVIDENCE")
    typer.echo(f"Runs dir: {report.runs_dir}")
    typer.echo(f"Candidate filter: {report.candidate_id or '-'}")
    typer.echo(f"Evidence count: {report.evidence_count}")
    typer.echo(f"Counts by type: {report.counts_by_type or '-'}")
    typer.echo(f"Dry run: {str(report.dry_run).lower()}")
    if not report.items:
        typer.echo("none")
    for item in report.items:
        typer.echo("")
        typer.echo(f"Evidence: {item.id}")
        typer.echo(f"Type: {item.evidence_type}")
        typer.echo(f"Candidate: {item.candidate_id or '-'}")
        typer.echo(f"Skill: {item.skill_name or '-'}")
        typer.echo(f"Decision: {item.decision or '-'}")
        typer.echo(f"Resolution class: {item.resolution_class or '-'}")
        typer.echo(f"Status: {item.status or '-'}")
        typer.echo(f"Reason: {item.reason}")
        typer.echo(f"Remaining blocked scope: {item.remaining_blocked_scope or '-'}")
        typer.echo(f"Source: {item.source}")
        typer.echo(f"Evidence refs: {_format_list(item.evidence_refs)}")
        if item.notes:
            typer.echo(f"Notes: {item.notes}")

    typer.echo("")
    typer.echo("MUTATION_BOUNDARY")
    typer.echo(f"Run logs mutated: {str(report.run_logs_mutated).lower()}")
    typer.echo(
        f"Candidate ledger mutated: {str(report.candidate_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Resolution ledger mutated: {str(report.resolution_ledger_mutated).lower()}"
    )
    typer.echo(f"Durable skills mutated: {str(report.durable_skills_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(
        f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}"
    )


def emit_operator_summary_json(report: OperatorSummaryReport) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_operator_summary_output(report: OperatorSummaryReport) -> None:
    typer.echo("OPERATOR_SUMMARY")
    typer.echo(f"Runs dir: {report.runs_dir}")
    typer.echo(f"Advisory only: {str(report.advisory_only).lower()}")
    typer.echo(f"Input requests: {report.input_request_count}")
    typer.echo(f"Candidate entries: {report.candidate_count}")
    typer.echo(f"Negative evidence: {report.negative_evidence_count}")
    typer.echo(f"Blocked items: {len(report.blocked_items)}")
    typer.echo(f"Human input items: {len(report.human_input_items)}")
    typer.echo(f"Promotion-ready candidates: {len(report.promotion_ready_candidates)}")
    typer.echo(f"Missing evidence items: {len(report.missing_evidence_items)}")
    typer.echo(f"Unsafe/negative items: {len(report.unsafe_or_negative_items)}")
    typer.echo(f"Checkpoint status: {report.checkpoint.status}")
    typer.echo(
        "Checkpoint changes: "
        f"added={report.checkpoint.added_count} "
        f"changed={report.checkpoint.changed_count} "
        f"removed={report.checkpoint.removed_count}"
    )
    typer.echo("")

    _emit_operator_decisions(report.operator_decisions)
    _emit_operator_summary_items("BLOCKED_ITEMS", report.blocked_items)
    _emit_operator_summary_items("HUMAN_INPUT", report.human_input_items)
    _emit_operator_summary_items(
        "PROMOTION_READY_CANDIDATES", report.promotion_ready_candidates
    )
    _emit_operator_summary_items("MISSING_EVIDENCE", report.missing_evidence_items)
    _emit_operator_summary_items("UNSAFE_OR_NEGATIVE", report.unsafe_or_negative_items)
    _emit_operator_summary_items("CHECKPOINT_CHANGES", report.checkpoint_change_items)

    typer.echo("CHECKPOINT")
    typer.echo(f"Latest checkpoint: {report.checkpoint.latest_checkpoint_hash or '-'}")
    typer.echo(
        "Current evidence matches latest: "
        f"{str(report.checkpoint.current_evidence_matches_latest).lower()}"
    )
    typer.echo(f"Blockers: {_format_list(report.checkpoint.blockers)}")
    typer.echo(f"Warnings: {_format_list(report.checkpoint.warnings)}")
    typer.echo("")

    typer.echo("SOURCE_WARNINGS")
    _emit_string_items(report.warnings)
    typer.echo("")

    typer.echo("MUTATION_BOUNDARY")
    typer.echo(f"Run logs mutated: {str(report.run_logs_mutated).lower()}")
    typer.echo(f"Candidate ledger mutated: {str(report.candidate_ledger_mutated).lower()}")
    typer.echo(
        f"Resolution ledger mutated: {str(report.resolution_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Checkpoint ledger mutated: {str(report.checkpoint_ledger_mutated).lower()}"
    )
    typer.echo(f"Durable skills mutated: {str(report.durable_skills_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(
        f"Governor steering enabled: {str(report.governor_steering_enabled).lower()}"
    )
    typer.echo("")

    typer.echo("NEXT_STEPS")
    _emit_string_items(report.next_steps)


def _emit_operator_decisions(items: list[OperatorDecisionItem]) -> None:
    typer.echo("OPERATOR_DECISIONS")
    if not items:
        typer.echo("none")
        typer.echo("")
        return
    for item in items:
        typer.echo(f"- {item.decision}")
        typer.echo(f"  Priority: {item.priority}")
        typer.echo(f"  Severity: {item.severity}")
        typer.echo(f"  Title: {item.title}")
        typer.echo(f"  Reason: {item.reason}")
        typer.echo(f"  Primary command: {item.primary_command or '-'}")
        typer.echo(f"  Supporting commands: {_format_list(item.supporting_commands)}")
        typer.echo(f"  Source item ids: {_format_list(item.source_item_ids)}")
        typer.echo(f"  Blockers: {_format_list(item.blockers)}")
        typer.echo(f"  Warnings: {_format_list(item.warnings)}")
    typer.echo("")


def _emit_operator_summary_items(
    title: str,
    items: list[OperatorSummaryItem],
) -> None:
    typer.echo(title)
    if not items:
        typer.echo("none")
        typer.echo("")
        return
    for item in items:
        typer.echo(f"- {item.id}")
        typer.echo(f"  Severity: {item.severity}")
        typer.echo(f"  Title: {item.title}")
        typer.echo(f"  Reason: {item.reason}")
        typer.echo(f"  Status: {item.status or '-'}")
        typer.echo(f"  Candidate: {item.candidate_id or '-'}")
        source = [item.source_type, item.source_path or "", item.source_detail or ""]
        typer.echo(f"  Source: {_format_list(source)}")
        typer.echo(f"  Evidence refs: {_format_list(item.evidence_refs)}")
        typer.echo(f"  Next commands: {_format_list(item.next_commands)}")
    typer.echo("")


def emit_evidence_checkpoint_json(report: EvidenceCheckpointReport) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_evidence_checkpoint_output(report: EvidenceCheckpointReport) -> None:
    typer.echo("EVIDENCE_CHECKPOINT")
    typer.echo(f"Runs dir: {report.runs_dir}")
    typer.echo(f"Ledger: {report.ledger_path}")
    typer.echo(f"Mode: {report.mode}")
    typer.echo(f"Outcome: {report.outcome}")
    typer.echo(f"Dry run: {str(report.dry_run).lower()}")
    typer.echo(f"Scope: {report.scope}")
    typer.echo(f"Checkpoint ID: {report.checkpoint_id or '-'}")
    typer.echo(f"Previous checkpoint hash: {report.previous_checkpoint_hash or '-'}")
    typer.echo(f"Checkpoint hash: {report.checkpoint_hash or '-'}")
    typer.echo(f"Latest checkpoint hash: {report.latest_checkpoint_hash or '-'}")
    typer.echo(f"Checkpoint count: {report.checkpoint_count}")
    typer.echo(f"Checkpoints verified: {report.checkpoints_verified}")
    typer.echo(f"Chain valid: {str(report.chain_valid).lower()}")
    typer.echo(
        "Current evidence matches latest: "
        f"{str(report.current_evidence_matches_latest).lower()}"
    )
    typer.echo(f"Evidence files: {report.evidence_file_count}")
    for item in report.evidence_files:
        typer.echo(f"- {item.path} sha256={item.sha256} bytes={item.size_bytes}")

    typer.echo("")
    typer.echo("BLOCKERS")
    _emit_string_items(report.blockers)

    typer.echo("")
    typer.echo("WARNINGS")
    _emit_string_items(report.warnings)

    typer.echo("")
    typer.echo("MUTATION_BOUNDARY")
    typer.echo(
        f"Checkpoint ledger mutated: {str(report.checkpoint_ledger_mutated).lower()}"
    )
    typer.echo(f"Run logs mutated: {str(report.run_logs_mutated).lower()}")
    typer.echo(
        f"Candidate ledger mutated: {str(report.candidate_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Resolution ledger mutated: {str(report.resolution_ledger_mutated).lower()}"
    )
    typer.echo(f"Durable skills mutated: {str(report.durable_skills_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(
        f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}"
    )

    typer.echo("")
    typer.echo("NEXT_STEPS")
    _emit_string_items(report.next_steps)


def emit_evidence_governor_json(report: EvidenceGovernorReport) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_evidence_governor_output(report: EvidenceGovernorReport) -> None:
    typer.echo("EVIDENCE_GOVERNOR")
    typer.echo(f"Candidate: {report.candidate_id}")
    typer.echo(f"Skill: {report.skill_name or '-'}")
    typer.echo(f"Recommendation: {report.recommendation}")
    typer.echo(f"Reason: {report.recommendation_reason}")
    typer.echo(f"Advisory only: {str(report.advisory_only).lower()}")
    typer.echo(f"Approval granted: {str(report.approval_granted).lower()}")
    typer.echo(f"Install authorized: {str(report.install_authorized).lower()}")
    typer.echo(f"Promotion authorized: {str(report.promotion_authorized).lower()}")
    typer.echo(
        "Permission widening authorized: "
        f"{str(report.permission_widening_authorized).lower()}"
    )
    typer.echo(f"Route steering enabled: {str(report.route_steering_enabled).lower()}")

    typer.echo("")
    typer.echo("SIGNALS")
    for signal in report.signals:
        typer.echo(f"- {signal.name}: {signal.status}")
        typer.echo(f"  summary: {signal.summary}")
        if signal.evidence_refs:
            typer.echo(f"  evidence: {_format_list(signal.evidence_refs)}")
        if signal.blockers:
            typer.echo(f"  blockers: {_format_list(signal.blockers)}")
        if signal.warnings:
            typer.echo(f"  warnings: {_format_list(signal.warnings)}")

    typer.echo("")
    typer.echo("BLOCKERS")
    _emit_string_items(report.blockers)

    typer.echo("")
    typer.echo("WARNINGS")
    _emit_string_items(report.warnings)

    typer.echo("")
    typer.echo("MUTATION_BOUNDARY")
    typer.echo(f"Run logs mutated: {str(report.run_logs_mutated).lower()}")
    typer.echo(
        f"Candidate ledger mutated: {str(report.candidate_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Resolution ledger mutated: {str(report.resolution_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Checkpoint ledger mutated: {str(report.checkpoint_ledger_mutated).lower()}"
    )
    typer.echo(f"Durable skills mutated: {str(report.durable_skills_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(
        f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}"
    )

    typer.echo("")
    typer.echo("NEXT_STEPS")
    _emit_string_items(report.next_steps)


def emit_shadow_activation_plan_json(report: ShadowActivationPlanReport) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_shadow_activation_plan_output(report: ShadowActivationPlanReport) -> None:
    typer.echo("SHADOW_ACTIVATION_PLAN")
    typer.echo(f"Candidate: {report.candidate_id}")
    typer.echo(f"Skill: {report.skill_name or '-'}")
    typer.echo(f"Outcome: {report.outcome}")
    typer.echo(
        "Ready for shadow activation preview: "
        f"{str(report.ready_for_shadow_activation_preview).lower()}"
    )
    typer.echo(f"Dry run: {str(report.dry_run).lower()}")
    typer.echo(f"Mutation supported: {str(report.mutation_supported).lower()}")

    typer.echo("")
    typer.echo("MANAGED_PREFIX")
    typer.echo(f"Prefix: {report.managed_prefix}")
    typer.echo(f"Prefix exists: {str(report.managed_prefix_exists).lower()}")
    typer.echo(f"Store dir: {report.store_dir or '-'}")
    typer.echo(f"Store SKILL.md: {report.store_skill_path or '-'}")

    typer.echo("")
    typer.echo("GENERATION")
    typer.echo(f"Profile: {report.profile_name}")
    typer.echo(f"Profile dir: {report.profile_dir or '-'}")
    typer.echo(f"Activation pointer: {report.activation_pointer or '-'}")
    typer.echo(f"Previous generation: {report.previous_generation or '-'}")
    typer.echo(f"Planned generation: {report.planned_generation or '-'}")
    typer.echo(f"Generation dir: {report.generation_dir or '-'}")
    typer.echo(f"Generation SKILL.md: {report.generation_skill_path or '-'}")
    typer.echo(f"Rollback target: {report.rollback_target or '-'}")

    typer.echo("")
    typer.echo("DIGESTS")
    typer.echo(f"Source sha256: {report.source_sha256 or '-'}")
    typer.echo(f"Durable plan digest: {report.durable_plan_digest or '-'}")
    typer.echo(f"Shadow plan digest: {report.shadow_plan_digest or '-'}")

    typer.echo("")
    typer.echo("POLICIES")
    typer.echo(f"Collision policy: {report.collision_policy}")
    typer.echo(f"Activation policy: {report.activation_policy}")
    typer.echo(f"Canary scope: {report.canary_scope}")

    typer.echo("")
    typer.echo("BLOCKERS")
    _emit_string_items(report.blockers)

    typer.echo("")
    typer.echo("WARNINGS")
    _emit_string_items(report.warnings)

    typer.echo("")
    typer.echo("MUTATION_BOUNDARY")
    typer.echo(f"Managed prefix mutated: {str(report.managed_prefix_mutated).lower()}")
    typer.echo(f"Profile mutated: {str(report.profile_mutated).lower()}")
    typer.echo(f"Run logs mutated: {str(report.run_logs_mutated).lower()}")
    typer.echo(
        f"Candidate ledger mutated: {str(report.candidate_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Resolution ledger mutated: {str(report.resolution_ledger_mutated).lower()}"
    )
    typer.echo(f"Durable skills mutated: {str(report.durable_skills_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(
        f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}"
    )

    typer.echo("")
    typer.echo("NEXT_STEPS")
    _emit_string_items(report.next_steps)


def emit_shadow_rollback_plan_json(report: ShadowRollbackPlanReport) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_shadow_rollback_plan_output(report: ShadowRollbackPlanReport) -> None:
    typer.echo("SHADOW_ROLLBACK_PLAN")
    typer.echo(f"Candidate: {report.candidate_id}")
    typer.echo(f"Skill: {report.skill_name or '-'}")
    typer.echo(f"Outcome: {report.outcome}")
    typer.echo(f"Rollback verifiable: {str(report.rollback_verifiable).lower()}")
    typer.echo(f"Dry run: {str(report.dry_run).lower()}")
    typer.echo(f"Mutation supported: {str(report.mutation_supported).lower()}")

    typer.echo("")
    typer.echo("PROFILE")
    typer.echo(f"Managed prefix: {report.managed_prefix}")
    typer.echo(f"Profile: {report.profile_name}")
    typer.echo(f"Profile dir: {report.profile_dir or '-'}")
    typer.echo(f"Activation pointer: {report.activation_pointer or '-'}")
    typer.echo(
        f"Activation pointer exists: {str(report.activation_pointer_exists).lower()}"
    )
    typer.echo(f"Activation pointer target: {report.activation_pointer_target or '-'}")

    typer.echo("")
    typer.echo("ROLLBACK")
    typer.echo(f"Current generation: {report.current_generation or '-'}")
    typer.echo(f"Planned generation: {report.planned_generation or '-'}")
    typer.echo(f"Rollback generation: {report.rollback_generation or '-'}")
    typer.echo(f"Rollback target: {report.rollback_target or '-'}")
    typer.echo(f"Rollback target exists: {str(report.rollback_target_exists).lower()}")

    typer.echo("")
    typer.echo("DIGESTS")
    typer.echo(f"Shadow plan digest: {report.shadow_plan_digest or '-'}")
    typer.echo(f"Rollback plan digest: {report.rollback_plan_digest or '-'}")

    typer.echo("")
    typer.echo("BLOCKERS")
    _emit_string_items(report.blockers)

    typer.echo("")
    typer.echo("WARNINGS")
    _emit_string_items(report.warnings)

    typer.echo("")
    typer.echo("MUTATION_BOUNDARY")
    typer.echo(f"Managed prefix mutated: {str(report.managed_prefix_mutated).lower()}")
    typer.echo(f"Profile mutated: {str(report.profile_mutated).lower()}")
    typer.echo(f"Run logs mutated: {str(report.run_logs_mutated).lower()}")
    typer.echo(
        f"Candidate ledger mutated: {str(report.candidate_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Resolution ledger mutated: {str(report.resolution_ledger_mutated).lower()}"
    )
    typer.echo(f"Durable skills mutated: {str(report.durable_skills_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(
        f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}"
    )

    typer.echo("")
    typer.echo("NEXT_STEPS")
    _emit_string_items(report.next_steps)


def emit_shadow_activation_acceptance_json(
    report: ShadowActivationAcceptanceReport,
) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_shadow_activation_acceptance_output(
    report: ShadowActivationAcceptanceReport,
) -> None:
    typer.echo("SHADOW_ACTIVATION_ACCEPTANCE")
    typer.echo(f"Candidate: {report.candidate_id}")
    typer.echo(f"Skill: {report.skill_name or '-'}")
    typer.echo(f"Outcome: {report.outcome}")
    typer.echo(f"Acceptance prepared: {str(report.acceptance_prepared).lower()}")
    typer.echo(f"Activation verified: {str(report.activation_verified).lower()}")
    typer.echo(f"Rollback verified: {str(report.rollback_verified).lower()}")
    typer.echo(f"Dry run: {str(report.dry_run).lower()}")
    typer.echo(f"Mutation supported: {str(report.mutation_supported).lower()}")

    typer.echo("")
    typer.echo("PREFIXES")
    typer.echo(f"Planned managed prefix: {report.planned_managed_prefix}")
    typer.echo(f"Acceptance prefix: {report.acceptance_prefix}")
    typer.echo(f"Acceptance prefix exists: {str(report.acceptance_prefix_exists).lower()}")
    typer.echo(f"Profile: {report.profile_name}")

    typer.echo("")
    typer.echo("PATHS")
    typer.echo(f"Source SKILL.md: {report.source_skill_path or '-'}")
    typer.echo(f"Source sha256: {report.source_sha256 or '-'}")
    typer.echo(f"Acceptance store SKILL.md: {report.acceptance_store_skill_path or '-'}")
    typer.echo(
        f"Acceptance generation SKILL.md: {report.acceptance_generation_skill_path or '-'}"
    )
    typer.echo(f"Acceptance pointer: {report.acceptance_activation_pointer or '-'}")
    typer.echo(f"Acceptance rollback target: {report.acceptance_rollback_target or '-'}")

    typer.echo("")
    typer.echo("GENERATION")
    typer.echo(f"Previous generation: {report.previous_generation or '-'}")
    typer.echo(f"Planned generation: {report.planned_generation or '-'}")
    typer.echo(f"Pointer before acceptance: {report.activation_pointer_before or '-'}")
    typer.echo(
        "Pointer after activation: "
        f"{report.activation_pointer_after_activation or '-'}"
    )
    typer.echo(
        "Pointer after rollback: "
        f"{report.activation_pointer_after_rollback or '-'}"
    )
    typer.echo(
        "Interrupted activation recovered: "
        f"{str(report.interrupted_activation_recovered).lower()}"
    )
    typer.echo(
        "Acceptance conflict detected: "
        f"{str(report.acceptance_conflict_detected).lower()}"
    )

    typer.echo("")
    typer.echo("DIGESTS")
    typer.echo(f"Shadow plan digest: {report.shadow_plan_digest or '-'}")
    typer.echo(f"Acceptance plan digest: {report.acceptance_plan_digest or '-'}")

    typer.echo("")
    typer.echo("BLOCKERS")
    _emit_string_items(report.blockers)

    typer.echo("")
    typer.echo("WARNINGS")
    _emit_string_items(report.warnings)

    typer.echo("")
    typer.echo("MUTATION_BOUNDARY")
    typer.echo(
        f"Acceptance prefix mutated: {str(report.acceptance_prefix_mutated).lower()}"
    )
    typer.echo(f"Managed prefix mutated: {str(report.managed_prefix_mutated).lower()}")
    typer.echo(f"Profile mutated: {str(report.profile_mutated).lower()}")
    typer.echo(f"Run logs mutated: {str(report.run_logs_mutated).lower()}")
    typer.echo(
        f"Candidate ledger mutated: {str(report.candidate_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Resolution ledger mutated: {str(report.resolution_ledger_mutated).lower()}"
    )
    typer.echo(f"Durable skills mutated: {str(report.durable_skills_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(
        f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}"
    )

    typer.echo("")
    typer.echo("NEXT_STEPS")
    _emit_string_items(report.next_steps)


def emit_shadow_write_gate_json(report: ShadowWriteGateReport) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_shadow_write_gate_output(report: ShadowWriteGateReport) -> None:
    typer.echo("SHADOW_WRITE_GATE")
    typer.echo(f"Candidate: {report.candidate_id}")
    typer.echo(f"Skill: {report.skill_name or '-'}")
    typer.echo(f"Outcome: {report.outcome}")
    typer.echo(
        "Ready for human managed-prefix write: "
        f"{str(report.ready_for_human_managed_prefix_write).lower()}"
    )
    typer.echo(f"Dry run: {str(report.dry_run).lower()}")
    typer.echo(f"Mutation supported: {str(report.mutation_supported).lower()}")

    typer.echo("")
    typer.echo("PREFIXES")
    typer.echo(f"Managed prefix: {report.managed_prefix}")
    typer.echo(f"Acceptance prefix: {report.acceptance_prefix}")
    typer.echo(f"Profile: {report.profile_name}")

    typer.echo("")
    typer.echo("EVIDENCE")
    typer.echo(f"Source SKILL.md: {report.source_skill_path or '-'}")
    typer.echo(f"Source sha256: {report.source_sha256 or '-'}")
    typer.echo(f"Source hash verified: {str(report.source_hash_verified).lower()}")
    typer.echo(f"Acceptance store SKILL.md: {report.acceptance_store_skill_path or '-'}")
    typer.echo(
        f"Acceptance store verified: {str(report.acceptance_store_verified).lower()}"
    )
    typer.echo(
        "Acceptance generation SKILL.md: "
        f"{report.acceptance_generation_skill_path or '-'}"
    )
    typer.echo(
        "Acceptance generation verified: "
        f"{str(report.acceptance_generation_verified).lower()}"
    )
    typer.echo(f"Acceptance pointer: {report.acceptance_activation_pointer or '-'}")
    typer.echo(f"Acceptance pointer target: {report.acceptance_pointer_target or '-'}")
    typer.echo(
        "Acceptance pointer restored: "
        f"{str(report.acceptance_pointer_restored).lower()}"
    )
    typer.echo(f"Acceptance rollback target: {report.acceptance_rollback_target or '-'}")
    typer.echo(
        "Acceptance rollback marker verified: "
        f"{str(report.acceptance_rollback_marker_verified).lower()}"
    )

    typer.echo("")
    typer.echo("DIGESTS")
    typer.echo(f"Durable plan digest: {report.durable_plan_digest or '-'}")
    typer.echo(f"Shadow plan digest: {report.shadow_plan_digest or '-'}")
    typer.echo(f"Rollback plan digest: {report.rollback_plan_digest or '-'}")
    typer.echo(f"Acceptance plan digest: {report.acceptance_plan_digest or '-'}")
    typer.echo(
        "Expected acceptance plan digest: "
        f"{report.expected_acceptance_plan_digest or '-'}"
    )
    typer.echo(
        "Acceptance plan digest verified: "
        f"{str(report.acceptance_plan_digest_verified).lower()}"
    )

    typer.echo("")
    typer.echo("BLOCKERS")
    _emit_string_items(report.blockers)

    typer.echo("")
    typer.echo("WARNINGS")
    _emit_string_items(report.warnings)

    typer.echo("")
    typer.echo("MUTATION_BOUNDARY")
    typer.echo(
        f"Acceptance prefix mutated: {str(report.acceptance_prefix_mutated).lower()}"
    )
    typer.echo(f"Managed prefix mutated: {str(report.managed_prefix_mutated).lower()}")
    typer.echo(f"Profile mutated: {str(report.profile_mutated).lower()}")
    typer.echo(f"Run logs mutated: {str(report.run_logs_mutated).lower()}")
    typer.echo(
        f"Candidate ledger mutated: {str(report.candidate_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Resolution ledger mutated: {str(report.resolution_ledger_mutated).lower()}"
    )
    typer.echo(f"Durable skills mutated: {str(report.durable_skills_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(
        f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}"
    )

    typer.echo("")
    typer.echo("NEXT_STEPS")
    _emit_string_items(report.next_steps)


def emit_shadow_managed_write_json(report: ShadowManagedWriteReport) -> None:
    typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))


def emit_shadow_managed_write_output(report: ShadowManagedWriteReport) -> None:
    typer.echo("SHADOW_MANAGED_WRITE")
    typer.echo(f"Candidate: {report.candidate_id}")
    typer.echo(f"Skill: {report.skill_name or '-'}")
    typer.echo(f"Outcome: {report.outcome}")
    typer.echo(
        "Ready for managed-prefix write: "
        f"{str(report.ready_for_managed_prefix_write).lower()}"
    )
    typer.echo(f"Dry run: {str(report.dry_run).lower()}")
    typer.echo(f"Mutation supported: {str(report.mutation_supported).lower()}")

    typer.echo("")
    typer.echo("PREFIXES")
    typer.echo(f"Managed prefix: {report.managed_prefix}")
    typer.echo(f"Acceptance prefix: {report.acceptance_prefix}")
    typer.echo(f"Profile: {report.profile_name}")

    typer.echo("")
    typer.echo("PATHS")
    typer.echo(f"Source SKILL.md: {report.source_skill_path or '-'}")
    typer.echo(f"Store SKILL.md: {report.store_skill_path or '-'}")
    typer.echo(f"Generation SKILL.md: {report.generation_skill_path or '-'}")
    typer.echo(f"Activation pointer: {report.activation_pointer or '-'}")
    typer.echo(f"Activation pointer target: {report.activation_pointer_target or '-'}")
    typer.echo(f"Rollback target: {report.rollback_target or '-'}")
    typer.echo(f"Write receipt: {report.write_receipt_path or '-'}")

    typer.echo("")
    typer.echo("DIGESTS")
    typer.echo(f"Source sha256: {report.source_sha256 or '-'}")
    typer.echo(f"Durable plan digest: {report.durable_plan_digest or '-'}")
    typer.echo(f"Shadow plan digest: {report.shadow_plan_digest or '-'}")
    typer.echo(f"Rollback plan digest: {report.rollback_plan_digest or '-'}")
    typer.echo(f"Acceptance plan digest: {report.acceptance_plan_digest or '-'}")
    typer.echo(
        "Managed write plan digest: "
        f"{report.managed_write_plan_digest or '-'}"
    )
    typer.echo(f"Latest checkpoint hash: {report.latest_checkpoint_hash or '-'}")

    typer.echo("")
    typer.echo("EXPECTED_MATCHES")
    typer.echo(
        "Expected source sha256 verified: "
        f"{str(report.expected_source_sha256_verified).lower()}"
    )
    typer.echo(
        "Durable plan digest verified: "
        f"{str(report.durable_plan_digest_verified).lower()}"
    )
    typer.echo(
        "Shadow plan digest verified: "
        f"{str(report.shadow_plan_digest_verified).lower()}"
    )
    typer.echo(
        "Rollback plan digest verified: "
        f"{str(report.rollback_plan_digest_verified).lower()}"
    )
    typer.echo(
        "Acceptance plan digest verified: "
        f"{str(report.acceptance_plan_digest_verified).lower()}"
    )
    typer.echo(
        "Managed write plan digest verified: "
        f"{str(report.managed_write_plan_digest_verified).lower()}"
    )
    typer.echo(
        f"Checkpoint hash verified: {str(report.checkpoint_hash_verified).lower()}"
    )
    typer.echo(
        "Exact expected values verified: "
        f"{str(report.exact_expected_values_verified).lower()}"
    )

    typer.echo("")
    typer.echo("STATUS")
    typer.echo(f"Source hash verified: {str(report.source_hash_verified).lower()}")
    typer.echo(f"Receipt acceptable: {str(report.receipt_acceptable).lower()}")
    typer.echo(
        "Receipt reversibility accepted: "
        f"{str(report.receipt_reversibility_accepted).lower()}"
    )
    typer.echo(f"Checkpoint verified: {str(report.checkpoint_verified).lower()}")
    typer.echo(f"Shadow write gate ready: {str(report.shadow_write_gate_ready).lower()}")
    typer.echo(f"Rollback ready: {str(report.rollback_ready).lower()}")
    typer.echo(f"Store verified: {str(report.store_verified).lower()}")
    typer.echo(f"Generation verified: {str(report.generation_verified).lower()}")
    typer.echo(
        "Activation pointer updated: "
        f"{str(report.activation_pointer_updated).lower()}"
    )
    typer.echo(
        "Activation pointer verified: "
        f"{str(report.activation_pointer_verified).lower()}"
    )
    typer.echo(
        "Rollback target verified: "
        f"{str(report.rollback_target_verified).lower()}"
    )
    typer.echo(f"Already applied: {str(report.already_applied).lower()}")
    typer.echo(
        "Interrupted activation recovered: "
        f"{str(report.interrupted_activation_recovered).lower()}"
    )
    typer.echo(f"Write approval id: {report.write_approval_id or '-'}")
    typer.echo(f"Write approval digest: {report.write_approval_digest or '-'}")
    typer.echo(f"Write approval expires at: {report.write_approval_expires_at or '-'}")
    typer.echo(f"Write approval present: {str(report.write_approval_present).lower()}")
    typer.echo(f"Write approval verified: {str(report.write_approval_verified).lower()}")

    typer.echo("")
    typer.echo("POLICIES")
    typer.echo(f"Managed-prefix write policy: {report.managed_prefix_write_policy}")
    typer.echo(f"Profile activation policy: {report.profile_activation_policy}")
    typer.echo(f"Rollback policy: {report.rollback_policy}")
    typer.echo(f"Stable routing policy: {report.stable_routing_policy}")
    typer.echo(f"Governor policy: {report.governor_policy}")

    typer.echo("")
    typer.echo("BLOCKERS")
    _emit_string_items(report.blockers)

    typer.echo("")
    typer.echo("WARNINGS")
    _emit_string_items(report.warnings)

    typer.echo("")
    typer.echo("MUTATION_BOUNDARY")
    typer.echo(
        f"Acceptance prefix mutated: {str(report.acceptance_prefix_mutated).lower()}"
    )
    typer.echo(f"Managed prefix mutated: {str(report.managed_prefix_mutated).lower()}")
    typer.echo(f"Profile mutated: {str(report.profile_mutated).lower()}")
    typer.echo(f"Run logs mutated: {str(report.run_logs_mutated).lower()}")
    typer.echo(
        f"Candidate ledger mutated: {str(report.candidate_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Resolution ledger mutated: {str(report.resolution_ledger_mutated).lower()}"
    )
    typer.echo(
        f"Checkpoint ledger mutated: {str(report.checkpoint_ledger_mutated).lower()}"
    )
    typer.echo(f"Durable skills mutated: {str(report.durable_skills_mutated).lower()}")
    typer.echo(f"Registry mutated: {str(report.registry_mutated).lower()}")
    typer.echo(
        f"Governor steering: {'enabled' if report.governor_steering_enabled else 'disabled'}"
    )

    typer.echo("")
    typer.echo("NEXT_STEPS")
    _emit_string_items(report.next_steps)


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
    typer.echo(f"Plan digest algorithm: {report.write_plan.plan_digest_algorithm}")
    typer.echo(f"Plan digest: {report.write_plan.plan_digest or '-'}")
    typer.echo(f"Plan approval ID: {report.write_plan.plan_approval_id or '-'}")
    typer.echo(f"Plan approval digest: {report.write_plan.plan_approval_digest or '-'}")
    typer.echo(
        f"Plan approval expires at: {report.write_plan.plan_approval_expires_at or '-'}"
    )
    typer.echo(
        f"Plan approval verified: {str(report.write_plan.plan_approval_verified).lower()}"
    )
    typer.echo(f"Collision policy: {report.write_plan.collision_policy}")
    typer.echo(f"Permission policy: {report.write_plan.permission_policy}")
    typer.echo(f"Permission approval ID: {report.write_plan.permission_approval_id or '-'}")
    typer.echo("Permission/dependency diff:")
    diff = report.write_plan.permission_dependency_diff
    typer.echo(
        "  Added permissions: "
        f"{_format_list(diff.added_permission_classes) if diff.added_permission_classes else 'none'}"
    )
    typer.echo(
        "  Added tools: "
        f"{_format_list(diff.added_tools) if diff.added_tools else 'none'}"
    )
    typer.echo(
        "  Dependencies declared: "
        f"{str(diff.dependency_diff.dependencies_declared).lower()}"
    )
    typer.echo(
        "  Dependency declaration keys: "
        f"{_format_list(diff.dependency_diff.declaration_keys) if diff.dependency_diff.declaration_keys else 'none'}"
    )
    typer.echo(
        "  Exact dependency realization: "
        f"{str(diff.dependency_diff.exact_realization_available).lower()}"
    )
    contract = report.write_plan.dependency_install_contract
    typer.echo("Dependency install contract:")
    typer.echo(f"  Policy: {contract.policy}")
    typer.echo(f"  Dependency plan digest: {contract.dependency_plan_digest or '-'}")
    typer.echo(
        "  Expected dependency plan digest: "
        f"{contract.expected_dependency_plan_digest or '-'}"
    )
    typer.echo(
        "  Dependency plan digest verified: "
        f"{str(contract.dependency_plan_digest_verified).lower()}"
    )
    typer.echo(
        "  Prepare dependency evidence: "
        f"{str(contract.prepare_dependency_evidence).lower()}"
    )
    typer.echo(f"  Evidence manifest: {contract.evidence_manifest_path or '-'}")
    typer.echo(f"  Evidence manifest sha256: {contract.evidence_manifest_sha256 or '-'}")
    typer.echo(
        "  Evidence manifest created: "
        f"{str(contract.evidence_manifest_created).lower()}"
    )
    typer.echo(
        "  Evidence manifest retained: "
        f"{str(contract.evidence_manifest_retained).lower()}"
    )
    typer.echo(f"  Dependency approval ID: {contract.dependency_approval_id or '-'}")
    typer.echo(f"  Dependency approval digest: {contract.dependency_approval_digest or '-'}")
    typer.echo(
        "  Dependency approval expires at: "
        f"{contract.dependency_approval_expires_at or '-'}"
    )
    typer.echo(
        "  Dependency approval verified: "
        f"{str(contract.dependency_approval_verified).lower()}"
    )
    typer.echo(f"  Install supported: {str(contract.install_supported).lower()}")
    typer.echo(f"  Install attempted: {str(contract.install_attempted).lower()}")
    typer.echo(f"  Dependencies installed: {str(contract.dependencies_installed).lower()}")
    typer.echo("  Dependency blockers:")
    _emit_string_items(contract.blockers)
    typer.echo(f"Replacement approved: {str(report.write_plan.replacement_approved).lower()}")
    typer.echo(
        "Permission widening approved: "
        f"{str(report.write_plan.permission_widening_approved).lower()}"
    )
    typer.echo(f"Snapshot dir: {report.write_plan.snapshot_dir or '-'}")
    typer.echo(f"Snapshot SKILL.md: {report.write_plan.snapshot_skill_path or '-'}")
    typer.echo(f"Snapshot sha256: {report.write_plan.snapshot_sha256 or '-'}")
    typer.echo(
        f"Prepare write evidence: {str(report.write_plan.prepare_write_evidence).lower()}"
    )
    typer.echo(f"Expected source sha256: {report.write_plan.expected_source_sha256 or '-'}")
    typer.echo(
        f"Source hash verified: {str(report.write_plan.source_hash_verified).lower()}"
    )
    typer.echo(
        f"Source snapshot created: {str(report.write_plan.source_snapshot_created).lower()}"
    )
    typer.echo(
        f"Source snapshot retained: {str(report.write_plan.source_snapshot_retained).lower()}"
    )
    typer.echo(f"Destination stage dir: {report.write_plan.destination_stage_dir or '-'}")
    typer.echo(
        "Destination stage SKILL.md: "
        f"{report.write_plan.destination_stage_skill_path or '-'}"
    )
    typer.echo(f"Destination stage sha256: {report.write_plan.destination_stage_sha256 or '-'}")
    typer.echo(
        f"Destination stage created: {str(report.write_plan.destination_stage_created).lower()}"
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
    _emit_security_warnings(result.run_log.security_warnings)
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


def _emit_security_warnings(warnings: Iterable[str]) -> None:
    items = list(dict.fromkeys(warnings))
    if not items:
        return
    typer.echo("")
    typer.echo("SECURITY")
    for warning in items:
        typer.echo(f"Warning: {warning}")


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
        typer.echo(f"Redactions applied: {str(execution.redactions_applied).lower()}")
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
    _emit_run_next_action(result)


def _emit_run_next_action(result: AgentRunResult) -> None:
    if (
        result.exit_code == 0
        and not result.run_log.skill_requests
        and not result.run_log.skill_repair_requests
        and not result.run_log.input_requests
    ):
        return

    runs_dir = result.run_log_path.parent
    typer.echo("")
    typer.echo("NEXT_ACTION")
    typer.echo(f"Start with summary: skill-agent operator-summary --runs-dir {runs_dir}")
    typer.echo(f"Explain this run: skill-agent explain {result.run_log_path}")
    if result.run_log.input_requests:
        typer.echo(f"Review open input: skill-agent input-requests --runs-dir {runs_dir}")
    if result.run_log.skill_requests:
        typer.echo(f"Review candidate evidence: skill-agent candidates --runs-dir {runs_dir}")
    if result.run_log.skill_repair_requests:
        typer.echo("Repair required: inspect the failure reasons above before approval.")
    typer.echo("Boundary: no durable skill admission or stable routing happened automatically.")


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
