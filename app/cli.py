from __future__ import annotations

from pathlib import Path
from typing import Annotated
import json
import re

import typer

from app.admission_plan import AdmissionPlanError, build_admission_plan
from app.agent_loop import run_task
from app.cli_banner import emit_cli_banner
from app.cli_output import (
    emit_admission_plan_json,
    emit_admission_plan_output,
    emit_candidate_decision_json,
    emit_candidate_decision_output,
    emit_candidate_usefulness_json,
    emit_candidate_usefulness_output,
    emit_candidates_json,
    emit_candidates_output,
    emit_durable_admission_preview_json,
    emit_durable_admission_preview_output,
    emit_evidence_checkpoint_json,
    emit_evidence_checkpoint_output,
    emit_evidence_governor_json,
    emit_evidence_governor_output,
    emit_negative_evidence_json,
    emit_negative_evidence_output,
    emit_operator_summary_json,
    emit_operator_summary_output,
    emit_run_json,
    emit_registry_json,
    emit_run_output,
    emit_shadow_activation_acceptance_json,
    emit_shadow_activation_acceptance_output,
    emit_shadow_activation_plan_json,
    emit_shadow_activation_plan_output,
    emit_shadow_managed_write_json,
    emit_shadow_managed_write_output,
    emit_shadow_rollback_plan_json,
    emit_shadow_rollback_plan_output,
    emit_shadow_write_gate_json,
    emit_shadow_write_gate_output,
    emit_skill_receipt_json,
    emit_skill_receipt_output,
    emit_stable_readiness_json,
    emit_stable_readiness_output,
)
from app.candidate_decision import (
    CandidateDecisionError,
    build_candidate_decision_report,
)
from app.candidate_usefulness import (
    CandidateUsefulnessError,
    build_candidate_usefulness_report,
)
from app.durable_admission import build_durable_admission_preview
from app.evidence_checkpoint import (
    EvidenceCheckpointError,
    build_evidence_checkpoint_report,
)
from app.evidence_governor import EvidenceGovernorError, build_evidence_governor_report
from app.eval_runner import EvalSuiteError, run_eval_suite, write_eval_reports
from app.explain import ExplainError, explain_run_log
from app.input_focus import (
    collect_input_request_queue,
    input_request_kind_counts,
    input_request_source_warnings,
)
from app.input_resolution import InputResolutionError, resolve_input_request as resolve_input_request_report
from app.librarian import analyze_library
from app.negative_evidence import build_negative_evidence_report
from app.operator_summary import build_operator_summary_report
from app.shadow_activation import (
    ShadowActivationPlanError,
    build_shadow_activation_acceptance_report,
    build_shadow_activation_plan,
    build_shadow_managed_write_report,
    build_shadow_rollback_plan,
    build_shadow_write_gate_report,
)
from app.skill_candidate_ledger import (
    SkillCandidateLedgerError,
    approve_candidate_promotion,
    ledger_path,
    load_candidate_ledger,
)
from app.skill_receipt import SkillReceiptError, build_skill_receipt_report
from app.stable_readiness import StableReadinessError, build_stable_readiness_report
from app.registry import SkillRegistry
from app.redaction import redact_data


CLI_HELP = (
    "Governed local skill acquisition CLI. Start with run, operator-summary, "
    "candidate-decision, or v1-local-use before drilling into raw evidence."
)

PANEL_START_HERE = "Start here"
PANEL_CORE = "Core task loop"
PANEL_OPERATOR = "Operator decision review"
PANEL_CANDIDATE = "Candidate evidence"
PANEL_HUMAN = "Human input and approvals"
PANEL_MANAGED = "Managed-prefix local writes"
PANEL_EVAL = "Eval and diagnostics"


app = typer.Typer(
    no_args_is_help=True,
    help=CLI_HELP,
    epilog=(
        "Recommended reviewer path: run the launch demo, inspect operator-summary, "
        "then use candidate-decision or explain only when more proof is needed."
    ),
)


V1_LOCAL_USE_REPORT = {
    "scope": "managed-prefix-first local use",
    "primary_command": "shadow-managed-write",
    "mutation_surface": "managed prefix only",
    "stable_routing_policy": "deferred_for_v1",
    "operator_sequence": [
        "Create or inspect candidate evidence with skill-agent run and candidate-decision.",
        "Record human promotion review with promote-candidate when temporary evidence supports review.",
        "Inspect durable admission evidence with admit-candidate --dry-run and capture the durable plan digest.",
        "Prepare run-scoped acceptance evidence with shadow-activation-acceptance --prepare-acceptance-evidence.",
        "Verify rollback and acceptance evidence with shadow-write-gate.",
        "Run shadow-managed-write in dry-run mode and capture the managed-write plan digest.",
        "Record a separate approve_review input resolution whose notes include managed_write_plan_digest=<digest>.",
        "Append or verify an evidence checkpoint and capture the latest checkpoint hash.",
        "Run shadow-managed-write --no-dry-run only with every expected digest, checkpoint hash, and write approval id.",
        "Rerun shadow-managed-write --no-dry-run with the same proof to verify already_applied idempotency if needed.",
    ],
    "required_inputs": [
        "--expected-source-sha256",
        "--expected-durable-plan-digest",
        "--expected-shadow-plan-digest",
        "--expected-rollback-plan-digest",
        "--expected-acceptance-plan-digest",
        "--expected-managed-write-plan-digest",
        "--expected-checkpoint-hash",
        "--write-approval-id",
    ],
    "safety_guarantees": [
        "Requires a non-expired human write approval bound to the exact managed-write digest.",
        "Requires exact source, durable, shadow, rollback, acceptance, managed-write, and checkpoint matches.",
        "Blocks stale source hashes, digest mismatches, missing rollback evidence, conflicting bytes, and managed-prefix path escapes.",
        "Writes only the managed store skill file, profile generation skill file, profile pointer, and managed-prefix-local receipt.",
        "Supports idempotent already_applied verification for a matching prior write receipt.",
        "Keeps stable routing deferred for v1 even when stable-readiness evidence is ready for review.",
    ],
    "unchanged_authority": [
        "durable skills",
        "registry",
        "candidate ledger",
        "resolution ledger",
        "run logs",
        "permissions",
        "stable routing",
        "governor steering",
    ],
    "excluded_authority": [
        "durable skills admission",
        "automatic candidate-to-stable promotion",
        "positive stable routing",
        "dependency installation",
        "marketplace publication",
        "hosted service behavior",
        "true sandboxing claims",
    ],
}


NEW_AUTHORITY_READINESS_REPORT = {
    "phase": "v1.0 local CLI / reviewer validation",
    "status": "ready_for_new_authority_design_review",
    "ready_for_authority_planning": True,
    "ready_to_enable_new_authority": False,
    "next_authority_candidate": "checkpoint-gated active blocker before any positive stable-routing attempt",
    "why_not_enable_yet": [
        "Reviewer feedback has not been collected against the operator-summary review path.",
        "No positive stable-routing, durable-admission, or active-governor implementation slice has been reviewed.",
        "No new-authority eval rows have proven allowed and blocked paths for the proposed authority.",
        "No digest-bound human override and revoke ledger exists for the proposed authority.",
    ],
    "required_before_enablement": [
        "Collect reviewer evidence that operator-summary decisions are understandable.",
        "Choose exactly one smallest reversible authority candidate.",
        "Write a design plan that separates advisory, blocking, and authorizing behavior.",
        "Add eval rows for allowed, blocked, overblocked, stale-evidence, expired-approval, and revoke cases.",
        "Keep run logs and explain output visibly reporting the authority decision.",
        "Require exact checkpoint, plan digest, approval ID, and approval expiry evidence.",
        "Preserve no-mutation guarantees for durable skills, registry, ledgers, permissions, dependencies, and routing unless the slice explicitly owns that authority.",
        "Pass the full local validation bundle and external/manual review before enabling the authority.",
    ],
    "must_remain_disabled_until_separate_slice": [
        "durable generated-skill admission into skills/",
        "positive stable routing",
        "active governor steering",
        "dependency installation",
        "permission widening without exact approval",
        "marketplace publication",
        "hosted service behavior",
        "true sandboxing claims",
    ],
    "proof_commands": [
        "skill-agent operator-summary --runs-dir <runs-dir>",
        "skill-agent evidence-checkpoint --runs-dir <runs-dir> --verify",
        "skill-agent stable-readiness <candidate-id> --runs-dir <runs-dir> --skills-dir <skills-dir>",
        "skill-agent evidence-governor <candidate-id> --runs-dir <runs-dir> --skills-dir <skills-dir>",
        "bash scripts/v1_smoke.sh",
    ],
    "reference_docs": [
        "docs/operator-summary-review-pack.md",
        "docs/internal/plans/candidate-to-stable-and-durable-admission-rfc-2026-06-07.md",
        "docs/internal/plans/active-governor-preflight-design-2026-06-07.md",
        "docs/product-manager.md",
        "docs/operating-roadmap.md",
    ],
}


FEEDBACK_SESSION_TEMPLATE_REPORT = {
    "status": "template_only_read_only",
    "template_name": "reviewer_session_entry",
    "source_doc": "docs/reviewer-feedback-log.md",
    "durable_record_target": "docs/reviewer-feedback-log.md",
    "operator_action": "Manually copy a completed block into the feedback log after a real reviewer session.",
    "template_only": True,
    "feedback_log_appended": False,
    "rollups_updated": False,
    "authority_granted": False,
    "heading": "## Session YYYY-MM-DD Partner Alias",
    "fields": [
        "Partner alias:",
        "Date:",
        "Workflow type:",
        "Local environment:",
        "Session source:",
        "Launch-demo completed: yes/no",
        "`operator-summary` inspected first: yes/no",
        "Next `OPERATOR_DECISIONS` action identified unaided: yes/no",
        "Candidate evidence confused with durable admission: yes/no",
        "Stable-readiness confused with stable routing: yes/no",
        "`ready_to_enable_new_authority=false` understood: yes/no",
        "Setup friction:",
        "Operator-summary decision clarity:",
        "Evidence-surface confusion:",
        "Candidate-decision confusion:",
        "Safety-boundary confusion:",
        "Stable-routing deferral confusion:",
        "New-authority readiness confusion:",
        "Most useful proof surface:",
        "Least useful or most confusing proof surface:",
        "Desired next action:",
        "Captured issue/doc note:",
        "Follow-up priority: none/docs/operator-summary/demo/readiness/other",
    ],
    "follow_up_priority_options": [
        "none",
        "docs",
        "operator-summary",
        "demo",
        "readiness",
        "other",
    ],
    "mutation_boundary": {
        "feedback_log_appended": False,
        "rollups_updated": False,
        "run_logs_mutated": False,
        "candidate_ledger_mutated": False,
        "resolution_ledger_mutated": False,
        "checkpoint_ledger_mutated": False,
        "durable_skills_mutated": False,
        "registry_mutated": False,
        "durable_admission_granted": False,
        "stable_routing_enabled": False,
        "governor_steering_enabled": False,
        "dependencies_installed": False,
        "permissions_widened": False,
        "hosted_behavior_enabled": False,
        "marketplace_behavior_enabled": False,
    },
    "excluded_authority": [
        "feedback-log append",
        "summary rollup update",
        "durable generated-skill admission into skills/",
        "positive stable routing",
        "active governor steering",
        "dependency installation",
        "permission widening",
        "hosted service behavior",
        "marketplace behavior",
        "true sandboxing claims",
    ],
    "next_steps": [
        "Run the reviewer review path before filling out the template.",
        "Manually copy completed notes into docs/reviewer-feedback-log.md.",
        "Update summary rollups manually only after real sessions are recorded.",
    ],
}


FEEDBACK_SESSION_YES_NO_FIELDS = {
    "launch_demo_completed": "Launch-demo completed",
    "operator_summary_inspected_first": "`operator-summary` inspected first",
    "operator_decision_identified_unaided": "Next `OPERATOR_DECISIONS` action identified unaided",
    "candidate_evidence_confused_with_durable_admission": "Candidate evidence confused with durable admission",
    "stable_readiness_confused_with_stable_routing": "Stable-readiness confused with stable routing",
    "ready_to_enable_new_authority_false_understood": "`ready_to_enable_new_authority=false` understood",
}

FEEDBACK_SESSION_TEXT_FIELDS = {
    "partner_alias": "Partner alias",
    "session_date": "Date",
    "workflow_type": "Workflow type",
    "local_environment": "Local environment",
    "session_source": "Session source",
    "setup_friction": "Setup friction",
    "operator_summary_decision_clarity": "Operator-summary decision clarity",
    "evidence_surface_confusion": "Evidence-surface confusion",
    "candidate_decision_confusion": "Candidate-decision confusion",
    "safety_boundary_confusion": "Safety-boundary confusion",
    "stable_routing_deferral_confusion": "Stable-routing deferral confusion",
    "new_authority_readiness_confusion": "New-authority readiness confusion",
    "most_useful_proof_surface": "Most useful proof surface",
    "least_useful_or_most_confusing_proof_surface": "Least useful or most confusing proof surface",
    "desired_next_action": "Desired next action",
    "captured_issue_doc_note": "Captured issue/doc note",
    "follow_up_priority": "Follow-up priority",
}

FEEDBACK_SESSION_ROLLUP_METRICS = {
    "completed_partner_sessions": "Completed partner sessions",
    "operator_decision_identified_unaided": "Partners who identified the next `operator-summary` decision unaided",
    "candidate_evidence_confused_with_durable_admission": "Partners who confused candidate evidence with durable admission",
    "stable_readiness_confused_with_stable_routing": "Partners who confused stable-readiness with stable routing",
    "ready_to_enable_new_authority_false_understood": "Partners who understood `ready_to_enable_new_authority=false`",
}

FEEDBACK_SESSION_APPEND_EXCLUDED_AUTHORITY = [
    "durable generated-skill admission into skills/",
    "positive stable routing",
    "active governor steering",
    "dependency installation",
    "permission widening",
    "hosted service behavior",
    "marketplace behavior",
    "true sandboxing claims",
]


@app.command(
    "banner",
    help="Print the compact human-facing CLI banner.",
    short_help="Print the CLI banner.",
    rich_help_panel=PANEL_START_HERE,
)
def banner(
    color: Annotated[
        bool,
        typer.Option(
            "--color/--no-color",
            help="Enable or disable ANSI color in the banner.",
        ),
    ] = True,
    force_color: Annotated[
        bool,
        typer.Option(
            "--force-color",
            help="Force ANSI color even when stdout is not detected as a terminal.",
        ),
    ] = False,
) -> None:
    """Print the compact human-facing CLI banner."""

    emit_cli_banner(color=color, force_color=force_color)


def _single_line(value: str) -> str:
    return " ".join(value.strip().split())


def _normalize_feedback_yes_no(value: str, *, field_name: str) -> str:
    normalized = _single_line(value).lower()
    if normalized not in {"", "yes", "no"}:
        raise typer.BadParameter(
            f"{field_name} must be blank, 'yes', or 'no'; got {value!r}."
        )
    return normalized


def _feedback_session_mutation_boundary(*, appended: bool, rollups_updated: bool) -> dict[str, bool]:
    return {
        "feedback_log_appended": appended,
        "rollups_updated": rollups_updated,
        "run_logs_mutated": False,
        "candidate_ledger_mutated": False,
        "resolution_ledger_mutated": False,
        "checkpoint_ledger_mutated": False,
        "durable_skills_mutated": False,
        "registry_mutated": False,
        "durable_admission_granted": False,
        "stable_routing_enabled": False,
        "governor_steering_enabled": False,
        "dependencies_installed": False,
        "permissions_widened": False,
        "hosted_behavior_enabled": False,
        "marketplace_behavior_enabled": False,
    }


def _build_feedback_session_entry(
    *,
    text_values: dict[str, str],
    yes_no_values: dict[str, str],
) -> tuple[str, str]:
    session_date = text_values["session_date"] or "YYYY-MM-DD"
    partner_alias = text_values["partner_alias"] or "Partner Alias"
    heading = f"## Session {session_date} {partner_alias}"
    lines = [
        heading,
        "",
        f"- Partner alias: {text_values['partner_alias']}",
        f"- Date: {text_values['session_date']}",
        f"- Workflow type: {text_values['workflow_type']}",
        f"- Local environment: {text_values['local_environment']}",
        f"- Session source: {text_values['session_source']}",
    ]
    for key, label in FEEDBACK_SESSION_YES_NO_FIELDS.items():
        lines.append(f"- {label}: {yes_no_values[key]}")
    for key in [
        "setup_friction",
        "operator_summary_decision_clarity",
        "evidence_surface_confusion",
        "candidate_decision_confusion",
        "safety_boundary_confusion",
        "stable_routing_deferral_confusion",
        "new_authority_readiness_confusion",
        "most_useful_proof_surface",
        "least_useful_or_most_confusing_proof_surface",
        "desired_next_action",
        "captured_issue_doc_note",
        "follow_up_priority",
    ]:
        lines.append(f"- {FEEDBACK_SESSION_TEXT_FIELDS[key]}: {text_values[key]}")
    return heading, "\n".join(lines).rstrip() + "\n"


def _feedback_rollup_increments(yes_no_values: dict[str, str]) -> dict[str, int]:
    increments = {FEEDBACK_SESSION_ROLLUP_METRICS["completed_partner_sessions"]: 1}
    for key, metric in FEEDBACK_SESSION_ROLLUP_METRICS.items():
        if key == "completed_partner_sessions":
            continue
        increments[metric] = 1 if yes_no_values[key] == "yes" else 0
    return increments


def _increment_feedback_rollup(text: str, *, metric: str, increment: int) -> str:
    if increment == 0:
        return text
    pattern = re.compile(rf"(\| {re.escape(metric)} \| )(\d+)( \|)")
    match = pattern.search(text)
    if not match:
        raise typer.BadParameter(f"feedback log is missing rollup metric: {metric}")
    value = int(match.group(2)) + increment
    return pattern.sub(rf"\g<1>{value}\g<3>", text, count=1)


def _append_feedback_session_to_log(
    *,
    feedback_log: Path,
    session_entry: str,
    rollup_increments: dict[str, int],
) -> None:
    if not feedback_log.exists():
        raise typer.BadParameter(f"feedback log does not exist: {feedback_log}")
    text = feedback_log.read_text(encoding="utf-8")
    for metric, increment in rollup_increments.items():
        text = _increment_feedback_rollup(text, metric=metric, increment=increment)
    marker = "## Current Sessions"
    if marker not in text:
        raise typer.BadParameter("feedback log is missing '## Current Sessions'")
    no_sessions = "No reviewer sessions have been recorded yet."
    if no_sessions in text:
        text = text.replace(no_sessions, session_entry.rstrip(), 1)
    else:
        synthesis_marker = "\n## Synthesis Checklist"
        if synthesis_marker not in text:
            raise typer.BadParameter("feedback log is missing '## Synthesis Checklist'")
        text = text.replace(synthesis_marker, f"\n{session_entry.rstrip()}\n{synthesis_marker}", 1)
    feedback_log.write_text(text.rstrip() + "\n", encoding="utf-8")


def _feedback_rollup_counts(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for metric in FEEDBACK_SESSION_ROLLUP_METRICS.values():
        pattern = re.compile(rf"\| {re.escape(metric)} \| (\d+) \|")
        match = pattern.search(text)
        if not match:
            raise typer.BadParameter(f"feedback log is missing rollup metric: {metric}")
        counts[metric] = int(match.group(1))
    for metric in [
        "Repeated setup friction items",
        "Repeated evidence-surface confusion items",
    ]:
        pattern = re.compile(rf"\| {re.escape(metric)} \| (\d+) \|")
        match = pattern.search(text)
        if match:
            counts[metric] = int(match.group(1))
    return counts


def _feedback_session_headings(text: str) -> list[str]:
    current_sessions_marker = "## Current Sessions"
    synthesis_marker = "## Synthesis Checklist"
    if current_sessions_marker not in text:
        raise typer.BadParameter("feedback log is missing '## Current Sessions'")
    current_sessions = text.split(current_sessions_marker, 1)[1]
    if synthesis_marker in current_sessions:
        current_sessions = current_sessions.split(synthesis_marker, 1)[0]
    return re.findall(r"^## Session .+$", current_sessions, flags=re.MULTILINE)


def _build_feedback_log_summary(feedback_log: Path) -> dict[str, object]:
    if not feedback_log.exists():
        raise typer.BadParameter(f"feedback log does not exist: {feedback_log}")
    text = feedback_log.read_text(encoding="utf-8")
    rollup_counts = _feedback_rollup_counts(text)
    session_headings = _feedback_session_headings(text)
    completed_sessions = rollup_counts[FEEDBACK_SESSION_ROLLUP_METRICS["completed_partner_sessions"]]
    minimum_sessions = 3
    target_sessions = 5
    sessions_needed = max(0, minimum_sessions - completed_sessions)
    ready_for_synthesis = completed_sessions >= minimum_sessions
    if completed_sessions == 0:
        recommended_next_action = "Record the first reviewer session with feedback-session-append."
        status = "no_sessions_recorded"
    elif ready_for_synthesis:
        recommended_next_action = "Manually synthesize repeated friction before planning any new authority."
        status = "ready_for_manual_synthesis"
    else:
        recommended_next_action = (
            f"Record {sessions_needed} more reviewer session(s) before synthesis."
        )
        status = "more_sessions_needed"
    return {
        "status": status,
        "feedback_log_path": feedback_log.as_posix(),
        "completed_partner_sessions": completed_sessions,
        "session_headings": session_headings,
        "session_heading_count": len(session_headings),
        "minimum_sessions_for_synthesis": minimum_sessions,
        "target_sessions_for_synthesis": target_sessions,
        "sessions_needed_for_synthesis": sessions_needed,
        "ready_for_manual_synthesis": ready_for_synthesis,
        "ready_to_enable_new_authority": False,
        "rollup_counts": rollup_counts,
        "summary_warnings": [
            "Rollup counts and session headings differ; inspect the feedback log manually."
        ]
        if len(session_headings) != completed_sessions
        else [],
        "recommended_next_action": recommended_next_action,
        "mutation_boundary": _feedback_session_mutation_boundary(
            appended=False,
            rollups_updated=False,
        ),
        "excluded_authority": FEEDBACK_SESSION_APPEND_EXCLUDED_AUTHORITY,
        "next_steps": [
            "Keep recording contained reviewer sessions until 3 to 5 sessions exist.",
            "Synthesize repeated setup and evidence-surface friction manually from recorded sessions.",
            "Do not treat feedback summary as approval to enable new authority.",
        ],
    }


@app.command(
    "v1-local-use",
    help="Print the managed-prefix-first local-use checklist and unchanged authority boundary.",
    short_help="Show the v1 local-use checklist.",
    rich_help_panel=PANEL_START_HERE,
)
def v1_local_use(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the v1 local-use checklist as JSON."),
    ] = False,
) -> None:
    if json_output:
        typer.echo(json.dumps(V1_LOCAL_USE_REPORT, indent=2, sort_keys=True))
        return

    typer.echo("V1_LOCAL_USE")
    typer.echo(f"Scope: {V1_LOCAL_USE_REPORT['scope']}")
    typer.echo(f"Primary command: skill-agent {V1_LOCAL_USE_REPORT['primary_command']}")
    typer.echo(f"Mutation surface: {V1_LOCAL_USE_REPORT['mutation_surface']}")
    typer.echo(f"Stable routing policy: {V1_LOCAL_USE_REPORT['stable_routing_policy']}")
    typer.echo("")
    typer.echo("Operator sequence:")
    for index, item in enumerate(V1_LOCAL_USE_REPORT["operator_sequence"], start=1):
        typer.echo(f"{index}. {item}")
    typer.echo("")
    typer.echo("Required inputs:")
    for item in V1_LOCAL_USE_REPORT["required_inputs"]:
        typer.echo(f"- {item}")
    typer.echo("")
    typer.echo("Safety guarantees:")
    for item in V1_LOCAL_USE_REPORT["safety_guarantees"]:
        typer.echo(f"- {item}")
    typer.echo("")
    typer.echo("Unchanged authority:")
    for item in V1_LOCAL_USE_REPORT["unchanged_authority"]:
        typer.echo(f"- {item}")
    typer.echo("")
    typer.echo("Excluded authority:")
    for item in V1_LOCAL_USE_REPORT["excluded_authority"]:
        typer.echo(f"- {item}")


@app.command(
    "feedback-session-template",
    help="Print the read-only reviewer feedback session template.",
    short_help="Print reviewer feedback template.",
    rich_help_panel=PANEL_OPERATOR,
)
def feedback_session_template(
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help="Print the reviewer feedback session template report as JSON.",
        ),
    ] = False,
) -> None:
    if json_output:
        typer.echo(json.dumps(FEEDBACK_SESSION_TEMPLATE_REPORT, indent=2, sort_keys=True))
        return

    typer.echo("FEEDBACK_SESSION_TEMPLATE")
    typer.echo(f"Status: {FEEDBACK_SESSION_TEMPLATE_REPORT['status']}")
    typer.echo(f"Source doc: {FEEDBACK_SESSION_TEMPLATE_REPORT['source_doc']}")
    typer.echo(
        f"Durable record target: {FEEDBACK_SESSION_TEMPLATE_REPORT['durable_record_target']}"
    )
    typer.echo(
        "Feedback log appended: "
        f"{str(FEEDBACK_SESSION_TEMPLATE_REPORT['feedback_log_appended']).lower()}"
    )
    typer.echo(
        "Rollups updated: "
        f"{str(FEEDBACK_SESSION_TEMPLATE_REPORT['rollups_updated']).lower()}"
    )
    typer.echo("")
    typer.echo("Markdown session block:")
    typer.echo("")
    typer.echo(FEEDBACK_SESSION_TEMPLATE_REPORT["heading"])
    typer.echo("")
    for field in FEEDBACK_SESSION_TEMPLATE_REPORT["fields"]:
        typer.echo(f"- {field}")
    typer.echo("")
    typer.echo("Mutation boundary:")
    for key, value in FEEDBACK_SESSION_TEMPLATE_REPORT["mutation_boundary"].items():
        label = key.replace("_", " ").capitalize()
        typer.echo(f"- {label}: {str(value).lower()}")
    typer.echo("")
    typer.echo("Excluded authority:")
    for item in FEEDBACK_SESSION_TEMPLATE_REPORT["excluded_authority"]:
        typer.echo(f"- {item}")
    typer.echo("")
    typer.echo("Next steps:")
    for item in FEEDBACK_SESSION_TEMPLATE_REPORT["next_steps"]:
        typer.echo(f"- {item}")


@app.command(
    "feedback-session-append",
    help="Preview or append one reviewer feedback session without granting authority.",
    short_help="Capture reviewer feedback.",
    rich_help_panel=PANEL_OPERATOR,
)
def feedback_session_append(
    feedback_log: Annotated[
        Path,
        typer.Option(help="Reviewer feedback log to preview or update."),
    ] = Path("docs/reviewer-feedback-log.md"),
    partner_alias: Annotated[str, typer.Option(help="Reviewer alias.")] = "",
    session_date: Annotated[str, typer.Option("--date", help="Session date, usually YYYY-MM-DD.")] = "",
    workflow_type: Annotated[str, typer.Option(help="Contained workflow type reviewed.")] = "",
    local_environment: Annotated[str, typer.Option(help="Local environment summary.")] = "",
    session_source: Annotated[str, typer.Option(help="Session source, issue, thread, or call note.")] = "",
    launch_demo_completed: Annotated[str, typer.Option(help="yes/no/blank.")] = "",
    operator_summary_inspected_first: Annotated[str, typer.Option(help="yes/no/blank.")] = "",
    operator_decision_identified_unaided: Annotated[str, typer.Option(help="yes/no/blank.")] = "",
    candidate_evidence_confused_with_durable_admission: Annotated[
        str,
        typer.Option(help="yes/no/blank."),
    ] = "",
    stable_readiness_confused_with_stable_routing: Annotated[
        str,
        typer.Option(help="yes/no/blank."),
    ] = "",
    ready_to_enable_new_authority_false_understood: Annotated[
        str,
        typer.Option(help="yes/no/blank."),
    ] = "",
    setup_friction: Annotated[str, typer.Option(help="Setup friction notes.")] = "",
    operator_summary_decision_clarity: Annotated[
        str,
        typer.Option(help="Operator-summary decision clarity notes."),
    ] = "",
    evidence_surface_confusion: Annotated[str, typer.Option(help="Evidence-surface confusion notes.")] = "",
    candidate_decision_confusion: Annotated[str, typer.Option(help="Candidate-decision confusion notes.")] = "",
    safety_boundary_confusion: Annotated[str, typer.Option(help="Safety-boundary confusion notes.")] = "",
    stable_routing_deferral_confusion: Annotated[
        str,
        typer.Option(help="Stable-routing deferral confusion notes."),
    ] = "",
    new_authority_readiness_confusion: Annotated[
        str,
        typer.Option(help="New-authority readiness confusion notes."),
    ] = "",
    most_useful_proof_surface: Annotated[str, typer.Option(help="Most useful proof surface.")] = "",
    least_useful_or_most_confusing_proof_surface: Annotated[
        str,
        typer.Option(help="Least useful or most confusing proof surface."),
    ] = "",
    desired_next_action: Annotated[str, typer.Option(help="Reviewer's desired next action.")] = "",
    captured_issue_doc_note: Annotated[str, typer.Option(help="Captured issue or docs note.")] = "",
    follow_up_priority: Annotated[
        str,
        typer.Option(help="none/docs/operator-summary/demo/readiness/other."),
    ] = "none",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Preview the session entry unless --no-dry-run is supplied.",
        ),
    ] = True,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the feedback-session append report as JSON."),
    ] = False,
) -> None:
    text_values = {
        "partner_alias": _single_line(partner_alias),
        "session_date": _single_line(session_date),
        "workflow_type": _single_line(workflow_type),
        "local_environment": _single_line(local_environment),
        "session_source": _single_line(session_source),
        "setup_friction": _single_line(setup_friction),
        "operator_summary_decision_clarity": _single_line(operator_summary_decision_clarity),
        "evidence_surface_confusion": _single_line(evidence_surface_confusion),
        "candidate_decision_confusion": _single_line(candidate_decision_confusion),
        "safety_boundary_confusion": _single_line(safety_boundary_confusion),
        "stable_routing_deferral_confusion": _single_line(stable_routing_deferral_confusion),
        "new_authority_readiness_confusion": _single_line(new_authority_readiness_confusion),
        "most_useful_proof_surface": _single_line(most_useful_proof_surface),
        "least_useful_or_most_confusing_proof_surface": _single_line(
            least_useful_or_most_confusing_proof_surface
        ),
        "desired_next_action": _single_line(desired_next_action),
        "captured_issue_doc_note": _single_line(captured_issue_doc_note),
        "follow_up_priority": _single_line(follow_up_priority).lower(),
    }
    if text_values["follow_up_priority"] not in FEEDBACK_SESSION_TEMPLATE_REPORT[
        "follow_up_priority_options"
    ]:
        raise typer.BadParameter(
            "follow-up priority must be one of: "
            + ", ".join(FEEDBACK_SESSION_TEMPLATE_REPORT["follow_up_priority_options"])
        )
    if not dry_run and (not text_values["partner_alias"] or not text_values["session_date"]):
        raise typer.BadParameter("--partner-alias and --date are required with --no-dry-run")

    yes_no_values = {
        key: _normalize_feedback_yes_no(value, field_name=key.replace("_", "-"))
        for key, value in {
            "launch_demo_completed": launch_demo_completed,
            "operator_summary_inspected_first": operator_summary_inspected_first,
            "operator_decision_identified_unaided": operator_decision_identified_unaided,
            "candidate_evidence_confused_with_durable_admission": candidate_evidence_confused_with_durable_admission,
            "stable_readiness_confused_with_stable_routing": stable_readiness_confused_with_stable_routing,
            "ready_to_enable_new_authority_false_understood": ready_to_enable_new_authority_false_understood,
        }.items()
    }
    heading, session_entry = _build_feedback_session_entry(
        text_values=text_values,
        yes_no_values=yes_no_values,
    )
    rollup_increments = _feedback_rollup_increments(yes_no_values)
    appended = False
    rollups_updated = False
    if not dry_run:
        _append_feedback_session_to_log(
            feedback_log=feedback_log,
            session_entry=session_entry,
            rollup_increments=rollup_increments,
        )
        appended = True
        rollups_updated = any(value > 0 for value in rollup_increments.values())

    report = {
        "status": "dry_run_preview" if dry_run else "feedback_session_appended",
        "dry_run": dry_run,
        "feedback_log_path": feedback_log.as_posix(),
        "session_heading": heading,
        "session_entry": session_entry,
        "rollup_increments": rollup_increments,
        "repeated_friction_rollups_updated": False,
        "feedback_log_appended": appended,
        "rollups_updated": rollups_updated,
        "authority_granted": False,
        "allowed_mutation": [
            "feedback log append",
            "summary rollup counter update",
        ]
        if not dry_run
        else [],
        "mutation_boundary": _feedback_session_mutation_boundary(
            appended=appended,
            rollups_updated=rollups_updated,
        ),
        "excluded_authority": FEEDBACK_SESSION_APPEND_EXCLUDED_AUTHORITY,
        "next_steps": [
            "Review the appended session with the reviewer feedback log.",
            "Leave repeated setup or evidence-surface friction rollups manual until 3 to 5 sessions exist.",
            "Do not treat feedback capture as approval to enable new authority.",
        ]
        if not dry_run
        else [
            "Review the previewed session block.",
            "Rerun with --no-dry-run only when the session is ready to record.",
            "Do not treat feedback capture as approval to enable new authority.",
        ],
    }
    if json_output:
        typer.echo(json.dumps(report, indent=2, sort_keys=True))
        return

    typer.echo("FEEDBACK_SESSION_APPEND")
    typer.echo(f"Status: {report['status']}")
    typer.echo(f"Dry run: {str(dry_run).lower()}")
    typer.echo(f"Feedback log: {feedback_log.as_posix()}")
    typer.echo(f"Feedback log appended: {str(appended).lower()}")
    typer.echo(f"Rollups updated: {str(rollups_updated).lower()}")
    typer.echo("")
    typer.echo("Session entry:")
    typer.echo("")
    typer.echo(session_entry.rstrip())
    typer.echo("")
    typer.echo("Rollup increments:")
    for metric, increment in rollup_increments.items():
        typer.echo(f"- {metric}: {increment}")
    typer.echo("")
    typer.echo("Mutation boundary:")
    for key, value in report["mutation_boundary"].items():
        label = key.replace("_", " ").capitalize()
        typer.echo(f"- {label}: {str(value).lower()}")
    typer.echo("")
    typer.echo("Excluded authority:")
    for item in report["excluded_authority"]:
        typer.echo(f"- {item}")
    typer.echo("")
    typer.echo("Next steps:")
    for item in report["next_steps"]:
        typer.echo(f"- {item}")


@app.command(
    "feedback-log-summary",
    help="Summarize recorded reviewer feedback sessions and readiness for manual synthesis.",
    short_help="Summarize reviewer feedback.",
    rich_help_panel=PANEL_OPERATOR,
)
def feedback_log_summary(
    feedback_log: Annotated[
        Path,
        typer.Option(help="Reviewer feedback log to summarize."),
    ] = Path("docs/reviewer-feedback-log.md"),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the feedback-log summary as JSON."),
    ] = False,
) -> None:
    report = _build_feedback_log_summary(feedback_log)
    if json_output:
        typer.echo(json.dumps(report, indent=2, sort_keys=True))
        return

    typer.echo("FEEDBACK_LOG_SUMMARY")
    typer.echo(f"Status: {report['status']}")
    typer.echo(f"Feedback log: {report['feedback_log_path']}")
    typer.echo(f"Completed partner sessions: {report['completed_partner_sessions']}")
    typer.echo(f"Session heading count: {report['session_heading_count']}")
    typer.echo(
        f"Ready for manual synthesis: {str(report['ready_for_manual_synthesis']).lower()}"
    )
    typer.echo(
        f"Ready to enable new authority: {str(report['ready_to_enable_new_authority']).lower()}"
    )
    typer.echo(f"Recommended next action: {report['recommended_next_action']}")
    typer.echo("")
    typer.echo("Rollup counts:")
    for metric, count in report["rollup_counts"].items():
        typer.echo(f"- {metric}: {count}")
    if report["summary_warnings"]:
        typer.echo("")
        typer.echo("Warnings:")
        for warning in report["summary_warnings"]:
            typer.echo(f"- {warning}")
    typer.echo("")
    typer.echo("Mutation boundary:")
    for key, value in report["mutation_boundary"].items():
        label = key.replace("_", " ").capitalize()
        typer.echo(f"- {label}: {str(value).lower()}")
    typer.echo("")
    typer.echo("Excluded authority:")
    for item in report["excluded_authority"]:
        typer.echo(f"- {item}")
    typer.echo("")
    typer.echo("Next steps:")
    for item in report["next_steps"]:
        typer.echo(f"- {item}")


@app.command(
    "new-authority-readiness",
    help="Report why new-authority planning is ready while enablement remains disabled.",
    short_help="Explain disabled new authority.",
    rich_help_panel=PANEL_START_HERE,
)
def new_authority_readiness(
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the new-authority readiness report as JSON."),
    ] = False,
) -> None:
    if json_output:
        typer.echo(json.dumps(NEW_AUTHORITY_READINESS_REPORT, indent=2, sort_keys=True))
        return

    typer.echo("NEW_AUTHORITY_READINESS")
    typer.echo(f"Phase: {NEW_AUTHORITY_READINESS_REPORT['phase']}")
    typer.echo(f"Status: {NEW_AUTHORITY_READINESS_REPORT['status']}")
    typer.echo(
        "Ready for authority planning: "
        f"{str(NEW_AUTHORITY_READINESS_REPORT['ready_for_authority_planning']).lower()}"
    )
    typer.echo(
        "Ready to enable new authority: "
        f"{str(NEW_AUTHORITY_READINESS_REPORT['ready_to_enable_new_authority']).lower()}"
    )
    typer.echo(
        f"Next authority candidate: {NEW_AUTHORITY_READINESS_REPORT['next_authority_candidate']}"
    )
    typer.echo("")
    typer.echo("Why not enable yet:")
    for item in NEW_AUTHORITY_READINESS_REPORT["why_not_enable_yet"]:
        typer.echo(f"- {item}")
    typer.echo("")
    typer.echo("Required before enablement:")
    for item in NEW_AUTHORITY_READINESS_REPORT["required_before_enablement"]:
        typer.echo(f"- {item}")
    typer.echo("")
    typer.echo("Must remain disabled until a separate slice:")
    for item in NEW_AUTHORITY_READINESS_REPORT["must_remain_disabled_until_separate_slice"]:
        typer.echo(f"- {item}")
    typer.echo("")
    typer.echo("Proof commands:")
    for item in NEW_AUTHORITY_READINESS_REPORT["proof_commands"]:
        typer.echo(f"- {item}")
    typer.echo("")
    typer.echo("Reference docs:")
    for item in NEW_AUTHORITY_READINESS_REPORT["reference_docs"]:
        typer.echo(f"- {item}")


@app.command(
    help="Run a task through local skill routing and write run evidence.",
    short_help="Run a task through local skills.",
    rich_help_panel=PANEL_CORE,
)
def run(
    task: Annotated[str, typer.Argument(help="Task text to route through local skills.")],
    skills_dir: Annotated[Path, typer.Option(help="Local skills directory.")] = Path("skills"),
    runs_dir: Annotated[Path, typer.Option(help="Run log output directory.")] = Path("runs"),
    temporary_skills: Annotated[
        bool,
        typer.Option(
            "--temporary-skills/--no-temporary-skills",
            help="Draft and load validated Markdown-only temporary skills for missing capabilities.",
        ),
    ] = True,
    scripted_skills: Annotated[
        bool,
        typer.Option(
            "--scripted-skills/--no-scripted-skills",
            help="Allow validated local scripted skills to run in a restricted subprocess.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the run result as JSON without human-readable sections."),
    ] = False,
) -> None:
    result = run_task(
        task,
        skills_dir=skills_dir,
        runs_dir=runs_dir,
        create_temporary_skills=temporary_skills,
        allow_scripted_skills=scripted_skills,
    )
    if json_output:
        emit_run_json(result)
    else:
        emit_run_output(result)
    if result.exit_code:
        raise typer.Exit(result.exit_code)


@app.command(
    help="List accepted and rejected local skills from the durable registry.",
    short_help="List local skills.",
    rich_help_panel=PANEL_CORE,
)
def registry(
    skills_dir: Annotated[Path, typer.Option(help="Local skills directory.")] = Path("skills"),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print accepted and rejected registry records as JSON."),
    ] = False,
) -> None:
    skill_registry = SkillRegistry.load(skills_dir)
    if json_output:
        emit_registry_json(skill_registry)
        return
    for record in skill_registry.list_records():
        typer.echo(f"{record.name} {record.version} {record.status} {record.risk_level}")
    for rejection in skill_registry.rejections():
        typer.echo(f"REJECTED {rejection.path}: {'; '.join(rejection.reasons)}")


@app.command(
    help="Summarize local skill library, run evidence, input focus, and candidate queues.",
    short_help="Summarize library health.",
    rich_help_panel=PANEL_OPERATOR,
)
def health(
    skills_dir: Annotated[Path, typer.Option(help="Local skills directory.")] = Path("skills"),
    runs_dir: Annotated[Path, typer.Option(help="Run log directory.")] = Path("runs"),
    scripted_skills: Annotated[
        bool,
        typer.Option(
            "--scripted-skills/--no-scripted-skills",
            help="Include explicitly enabled scripted skills in the health report.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the health report as JSON."),
    ] = False,
) -> None:
    report = analyze_library(skills_dir, runs_dir, allow_scripts=scripted_skills)
    if json_output:
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
        return

    typer.echo("LIBRARY_HEALTH")
    typer.echo(f"Accepted skills: {report.accepted_skills}")
    typer.echo(f"Rejected skills: {report.rejected_skills}")
    typer.echo(f"Run logs read: {report.run_logs_read}")
    typer.echo(f"Result categories: {report.result_categories or '-'}")
    typer.echo(f"Temporary outcomes: {report.temporary_outcomes or '-'}")
    typer.echo(f"Repair requests: {report.repair_requests}")
    typer.echo(f"Safety stops: {report.safety_stops}")
    typer.echo(f"Human approval waits: {report.human_approval_waits}")
    typer.echo(f"Route/load failures: {report.route_load_failures}")
    typer.echo(f"Script failure categories: {report.script_failure_categories or '-'}")
    typer.echo("")
    typer.echo("INPUT_FOCUS")
    typer.echo(f"Open input requests: {report.input_request_count}")
    typer.echo(f"Kinds: {report.input_request_kind_counts or '-'}")
    typer.echo("")
    typer.echo("CANDIDATE_LEDGER")
    typer.echo(f"Candidates: {report.candidate_count}")
    typer.echo(f"Candidate status counts: {report.candidate_status_counts or '-'}")
    typer.echo(f"Blocked candidates: {report.blocked_candidate_count}")
    typer.echo(f"Duplicate candidates: {report.duplicate_candidate_count}")
    typer.echo(f"Human-gated candidates: {report.human_gated_candidate_count}")
    typer.echo(f"Review queue counts: {report.candidate_review_queue_counts or '-'}")
    typer.echo("")
    typer.echo("SKILL_METRICS")
    for metric in report.metrics:
        typer.echo(
            f"{metric.name} uses={metric.uses} requests={metric.requests} "
            f"temporary_uses={metric.temporary_uses} script_failures={metric.script_failures}"
        )
    typer.echo("")
    typer.echo("ISSUES")
    if not report.issues:
        typer.echo("none")
    for issue in report.issues:
        skill = issue.skill_name or "-"
        typer.echo(f"{issue.severity} {issue.code} {skill}: {issue.message}")


@app.command(
    "input-requests",
    help="List active human input requests from run and candidate evidence.",
    short_help="List active input requests.",
    rich_help_panel=PANEL_HUMAN,
)
def input_requests(
    runs_dir: Annotated[Path, typer.Option(help="Run log directory to scan for input requests.")] = Path("runs"),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print input requests as JSON."),
    ] = False,
) -> None:
    queue_items = collect_input_request_queue(runs_dir)
    active_items = [item for item in queue_items if item.request.status != "resolved"]
    active = [item.request for item in active_items]
    warnings = input_request_source_warnings(runs_dir)
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "runs_dir": str(runs_dir),
                    "input_request_count": len(active),
                    "input_request_kind_counts": input_request_kind_counts(active),
                    "warnings": warnings,
                    "input_requests": [
                        request.model_dump(mode="json") for request in active
                    ],
                    "input_request_items": [
                        item.model_dump(mode="json") for item in active_items
                    ],
                },
                indent=2,
                sort_keys=True,
            )
        )
        return

    open_count = sum(1 for request in active if request.status == "open")
    blocked_count = sum(1 for request in active if request.status == "blocked")
    typer.echo("INPUT_REQUESTS")
    typer.echo(f"Open: {open_count}")
    typer.echo(f"Blocked: {blocked_count}")
    typer.echo(f"Kinds: {input_request_kind_counts(active) or '-'}")
    for warning in warnings:
        typer.echo(f"Warning: {warning}")
    if not active:
        typer.echo("none")
        return
    for item in active_items:
        request = item.request
        typer.echo("")
        typer.echo(f"Input: {request.id}")
        typer.echo(f"Kind: {request.kind}")
        typer.echo(f"Status: {request.status}")
        typer.echo(f"Title: {request.title}")
        typer.echo(f"Blocked scope: {request.blocked_scope}")
        typer.echo(f"Requested decision: {request.requested_decision}")
        if item.sources:
            typer.echo("Sources:")
            for source in item.sources:
                detail = f" ({source.source_detail})" if source.source_detail else ""
                typer.echo(f"  {source.source_type}: {source.source_path}{detail}")
        if request.recommended_option:
            typer.echo(f"Recommended option: {request.recommended_option}")
        if request.evidence_refs:
            typer.echo(f"Evidence: {', '.join(request.evidence_refs)}")
        if request.next_commands:
            typer.echo("Recommended command:")
            for command in request.next_commands:
                typer.echo(f"  {command}")


@app.command(
    "resolve-input-request",
    help="Dry-run or append an input-request resolution to the append-only ledger.",
    short_help="Resolve a human input request.",
    rich_help_panel=PANEL_HUMAN,
)
def resolve_input_request(
    input_request_id: Annotated[str, typer.Argument(help="Input request ID from skill-agent input-requests.")],
    runs_dir: Annotated[Path, typer.Option(help="Run log directory to scan for input requests.")] = Path("runs"),
    decision: Annotated[str, typer.Option("--decision", help="Resolution decision to classify.")] = "",
    reviewer: Annotated[str, typer.Option("--reviewer", help="Human reviewer for the resolution decision.")] = "",
    notes: Annotated[str, typer.Option("--notes", help="Human notes tying the decision to evidence.")] = "",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Append to the resolution ledger unless dry-run is enabled.",
        ),
    ] = True,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the resolution report as JSON."),
    ] = False,
) -> None:
    try:
        report = resolve_input_request_report(
            input_request_id,
            runs_dir=runs_dir,
            decision=decision,
            reviewer=reviewer,
            notes=notes,
            dry_run=dry_run,
        )
    except InputResolutionError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    if json_output:
        typer.echo(json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True))
        return

    typer.echo("INPUT_REQUEST_RESOLUTION_DRY_RUN" if report.dry_run else "INPUT_REQUEST_RESOLUTION")
    typer.echo(f"Input: {report.input_request_id}")
    typer.echo(f"Decision: {report.decision}")
    typer.echo(f"Resolution class: {report.resolution_class}")
    typer.echo(f"Proposed status: {report.proposed_status}")
    typer.echo(f"Reviewer: {report.reviewer}")
    typer.echo(f"Dry run: {str(report.dry_run).lower()}")
    typer.echo(f"Remaining blocked scope: {report.remaining_blocked_scope or '-'}")
    typer.echo("Mutations: none" if report.dry_run else "Mutations: resolution_ledger")
    if report.sources:
        typer.echo("Sources:")
        for source in report.sources:
            detail = f" ({source.source_detail})" if source.source_detail else ""
            typer.echo(f"  {source.source_type}: {source.source_path}{detail}")
    typer.echo("NEXT_STEPS")
    for step in report.next_steps:
        typer.echo(f"- {step}")


@app.command(
    help="List skill candidate ledger records and their review queues.",
    short_help="List skill candidates.",
    rich_help_panel=PANEL_CANDIDATE,
)
def candidates(
    runs_dir: Annotated[Path, typer.Option(help="Run log directory containing the skill candidate ledger.")] = Path("runs"),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the candidate ledger as JSON."),
    ] = False,
) -> None:
    try:
        ledger = load_candidate_ledger(runs_dir)
    except SkillCandidateLedgerError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc
    path = str(ledger_path(runs_dir))
    if json_output:
        emit_candidates_json(ledger, path)
    else:
        emit_candidates_output(ledger, path)


@app.command(
    "candidate-usefulness",
    help="Summarize temporary-skill usefulness evidence for one candidate.",
    short_help="Show candidate usefulness.",
    rich_help_panel=PANEL_CANDIDATE,
)
def candidate_usefulness(
    candidate_id: Annotated[str, typer.Argument(help="Skill Candidate Ledger candidate ID to inspect for temporary-skill usefulness evidence.")],
    runs_dir: Annotated[Path, typer.Option(help="Run log directory containing the skill candidate ledger.")] = Path("runs"),
    skills_dir: Annotated[Path, typer.Option(help="Durable local skills directory for read-only admission-plan context.")] = Path("skills"),
    baseline_run_id: Annotated[
        str | None,
        typer.Option("--baseline-run-id", help="Pinned no-temporary-skill control run ID for paired usefulness comparison."),
    ] = None,
    treatment_run_id: Annotated[
        str | None,
        typer.Option("--treatment-run-id", help="Pinned candidate temporary-skill run ID for paired usefulness comparison."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the candidate usefulness report as JSON."),
    ] = False,
) -> None:
    try:
        report = build_candidate_usefulness_report(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            baseline_run_id=baseline_run_id,
            treatment_run_id=treatment_run_id,
        )
    except CandidateUsefulnessError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    if json_output:
        emit_candidate_usefulness_json(report)
    else:
        emit_candidate_usefulness_output(report)


@app.command(
    "skill-receipt",
    help="Build a proof-carrying source, utility, containment, and reversibility receipt.",
    short_help="Show candidate receipt.",
    rich_help_panel=PANEL_CANDIDATE,
)
def skill_receipt(
    candidate_id: Annotated[str, typer.Argument(help="Skill Candidate Ledger candidate ID to summarize as a proof-carrying receipt.")],
    runs_dir: Annotated[Path, typer.Option(help="Run log directory containing the skill candidate ledger.")] = Path("runs"),
    skills_dir: Annotated[Path, typer.Option(help="Durable local skills directory for read-only admission context.")] = Path("skills"),
    baseline_run_id: Annotated[
        str | None,
        typer.Option("--baseline-run-id", help="Pinned no-temporary-skill control run ID for utility proof."),
    ] = None,
    treatment_run_id: Annotated[
        str | None,
        typer.Option("--treatment-run-id", help="Pinned candidate temporary-skill run ID for utility proof."),
    ] = None,
    collision_policy: Annotated[
        str,
        typer.Option(
            "--collision-policy",
            help="Dry-run destination collision policy: block_existing or allow_replace_with_approval.",
        ),
    ] = "block_existing",
    permission_approval_id: Annotated[
        str,
        typer.Option(
            "--permission-approval-id",
            help="Optional resolved input request resolution ID authorizing permission widening in the receipt preview.",
        ),
    ] = "",
    plan_approval_id: Annotated[
        str,
        typer.Option(
            "--plan-approval-id",
            help="Optional resolved approve_review resolution ID binding approval to the receipt plan digest.",
        ),
    ] = "",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the skill receipt report as JSON."),
    ] = False,
) -> None:
    try:
        report = build_skill_receipt_report(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            baseline_run_id=baseline_run_id,
            treatment_run_id=treatment_run_id,
            collision_policy=collision_policy,
            permission_approval_id=permission_approval_id or None,
            plan_approval_id=plan_approval_id or None,
        )
    except SkillReceiptError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    if json_output:
        emit_skill_receipt_json(report)
    else:
        emit_skill_receipt_output(report)


@app.command(
    "stable-readiness",
    help="Review candidate-to-stable evidence while keeping stable routing disabled.",
    short_help="Review stable-readiness evidence.",
    rich_help_panel=PANEL_CANDIDATE,
)
def stable_readiness(
    candidate_id: Annotated[str, typer.Argument(help="Skill Candidate Ledger candidate ID to inspect for candidate-to-stable readiness evidence.")],
    runs_dir: Annotated[Path, typer.Option(help="Run log directory containing candidate and resolution ledgers.")] = Path("runs"),
    skills_dir: Annotated[Path, typer.Option(help="Durable local skills directory for read-only registry conflict checks.")] = Path("skills"),
    baseline_run_id: Annotated[
        str | None,
        typer.Option("--baseline-run-id", help="Optional pinned baseline run ID for nested usefulness comparison."),
    ] = None,
    treatment_run_id: Annotated[
        str | None,
        typer.Option("--treatment-run-id", help="Optional pinned treatment run ID for nested usefulness comparison."),
    ] = None,
    required_successful_temporary_uses: Annotated[
        int,
        typer.Option("--required-successful-temporary-uses", help="Stable-review success threshold; defaults to lifecycle rule of 10."),
    ] = 10,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the stable-readiness report as JSON."),
    ] = False,
) -> None:
    try:
        report = build_stable_readiness_report(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            baseline_run_id=baseline_run_id,
            treatment_run_id=treatment_run_id,
            required_successful_temporary_uses=required_successful_temporary_uses,
        )
    except StableReadinessError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    if json_output:
        emit_stable_readiness_json(report)
    else:
        emit_stable_readiness_output(report)


@app.command(
    "candidate-decision",
    help="Compress candidate evidence into one advisory next human decision.",
    short_help="Summarize next candidate decision.",
    rich_help_panel=PANEL_OPERATOR,
)
def candidate_decision(
    candidate_id: Annotated[str, typer.Argument(help="Skill Candidate Ledger candidate ID to summarize into one advisory next decision.")],
    runs_dir: Annotated[Path, typer.Option(help="Run log directory containing candidate and resolution ledgers.")] = Path("runs"),
    skills_dir: Annotated[Path, typer.Option(help="Durable local skills directory for read-only registry conflict checks.")] = Path("skills"),
    baseline_run_id: Annotated[
        str | None,
        typer.Option("--baseline-run-id", help="Optional pinned baseline run ID for nested usefulness comparison."),
    ] = None,
    treatment_run_id: Annotated[
        str | None,
        typer.Option("--treatment-run-id", help="Optional pinned treatment run ID for nested usefulness comparison."),
    ] = None,
    required_successful_temporary_uses: Annotated[
        int,
        typer.Option("--required-successful-temporary-uses", help="Stable-review success threshold; defaults to lifecycle rule of 10."),
    ] = 10,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the candidate decision report as JSON."),
    ] = False,
) -> None:
    try:
        report = build_candidate_decision_report(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            baseline_run_id=baseline_run_id,
            treatment_run_id=treatment_run_id,
            required_successful_temporary_uses=required_successful_temporary_uses,
        )
    except CandidateDecisionError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    if json_output:
        emit_candidate_decision_json(report)
    else:
        emit_candidate_decision_output(report)


@app.command(
    "negative-evidence",
    help="Surface blocked, rejected, deferred, duplicate, and repair evidence without rewriting history.",
    short_help="Show negative evidence.",
    rich_help_panel=PANEL_CANDIDATE,
)
def negative_evidence(
    runs_dir: Annotated[Path, typer.Option(help="Run log directory containing candidate and resolution ledgers.")] = Path("runs"),
    candidate_id: Annotated[
        str,
        typer.Option("--candidate-id", help="Optional candidate ID to filter negative evidence."),
    ] = "",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the negative evidence report as JSON."),
    ] = False,
) -> None:
    report = build_negative_evidence_report(
        runs_dir=runs_dir,
        candidate_id=candidate_id or None,
    )
    if json_output:
        emit_negative_evidence_json(report)
    else:
        emit_negative_evidence_output(report)


@app.command(
    "operator-summary",
    help="Show prioritized operator decisions before raw evidence sections.",
    short_help="Show prioritized operator decisions.",
    rich_help_panel=PANEL_START_HERE,
)
def operator_summary(
    runs_dir: Annotated[
        Path,
        typer.Option(help="Run directory containing local operator evidence."),
    ] = Path("runs"),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the operator summary as JSON."),
    ] = False,
) -> None:
    report = build_operator_summary_report(runs_dir=runs_dir)
    if json_output:
        emit_operator_summary_json(report)
    else:
        emit_operator_summary_output(report)


@app.command(
    "evidence-checkpoint",
    help="Append or verify a local hash-chain over run evidence.",
    short_help="Checkpoint or verify evidence.",
    rich_help_panel=PANEL_CANDIDATE,
)
def evidence_checkpoint(
    runs_dir: Annotated[Path, typer.Option(help="Run directory containing evidence to checkpoint.")] = Path("runs"),
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Append to the local checkpoint ledger unless dry-run is enabled.",
        ),
    ] = True,
    verify: Annotated[
        bool,
        typer.Option(
            "--verify",
            help="Verify the checkpoint chain and current evidence against the latest checkpoint without appending.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the evidence checkpoint report as JSON."),
    ] = False,
) -> None:
    try:
        report = build_evidence_checkpoint_report(
            runs_dir=runs_dir,
            dry_run=dry_run,
            verify=verify,
        )
    except EvidenceCheckpointError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    if json_output:
        emit_evidence_checkpoint_json(report)
    else:
        emit_evidence_checkpoint_output(report)


@app.command(
    "evidence-governor",
    help="Produce a non-steering recommendation from existing candidate proof surfaces.",
    short_help="Recommend from evidence only.",
    rich_help_panel=PANEL_CANDIDATE,
)
def evidence_governor(
    candidate_id: Annotated[str, typer.Argument(help="Skill Candidate Ledger candidate ID to evaluate with the non-steering evidence governor.")],
    runs_dir: Annotated[Path, typer.Option(help="Run directory containing candidate, resolution, and checkpoint evidence.")] = Path("runs"),
    skills_dir: Annotated[Path, typer.Option(help="Durable local skills directory for read-only admission context.")] = Path("skills"),
    baseline_run_id: Annotated[
        str | None,
        typer.Option("--baseline-run-id", help="Pinned no-temporary-skill control run ID for utility proof."),
    ] = None,
    treatment_run_id: Annotated[
        str | None,
        typer.Option("--treatment-run-id", help="Pinned candidate temporary-skill run ID for utility proof."),
    ] = None,
    collision_policy: Annotated[
        str,
        typer.Option(
            "--collision-policy",
            help="Dry-run destination collision policy: block_existing or allow_replace_with_approval.",
        ),
    ] = "block_existing",
    permission_approval_id: Annotated[
        str,
        typer.Option(
            "--permission-approval-id",
            help="Optional resolved input request resolution ID authorizing permission widening in the receipt preview.",
        ),
    ] = "",
    plan_approval_id: Annotated[
        str,
        typer.Option(
            "--plan-approval-id",
            help="Optional resolved approve_review resolution ID binding approval to the receipt plan digest.",
        ),
    ] = "",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the evidence governor report as JSON."),
    ] = False,
) -> None:
    try:
        report = build_evidence_governor_report(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            baseline_run_id=baseline_run_id,
            treatment_run_id=treatment_run_id,
            collision_policy=collision_policy,
            permission_approval_id=permission_approval_id or None,
            plan_approval_id=plan_approval_id or None,
        )
    except EvidenceGovernorError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    if json_output:
        emit_evidence_governor_json(report)
    else:
        emit_evidence_governor_output(report)


@app.command(
    "shadow-activation-plan",
    help="Plan managed-prefix shadow activation without creating files or switching profiles.",
    short_help="Plan shadow activation.",
    rich_help_panel=PANEL_MANAGED,
)
def shadow_activation_plan(
    candidate_id: Annotated[str, typer.Argument(help="Skill Candidate Ledger candidate ID to plan for managed shadow activation.")],
    runs_dir: Annotated[Path, typer.Option(help="Run log directory containing candidate and resolution ledgers.")] = Path("runs"),
    skills_dir: Annotated[Path, typer.Option(help="Durable local skills directory for read-only admission context.")] = Path("skills"),
    managed_prefix: Annotated[
        Path | None,
        typer.Option(
            "--managed-prefix",
            help="Managed shadow prefix to plan under. Defaults to <runs-dir>/managed_shadow.",
        ),
    ] = None,
    profile_name: Annotated[
        str,
        typer.Option("--profile-name", help="Managed profile name for generation planning."),
    ] = "default",
    collision_policy: Annotated[
        str,
        typer.Option(
            "--collision-policy",
            help="Dry-run destination collision policy: block_existing or allow_replace_with_approval.",
        ),
    ] = "block_existing",
    permission_approval_id: Annotated[
        str,
        typer.Option(
            "--permission-approval-id",
            help="Optional resolved input request resolution ID authorizing permission widening in the admission preview.",
        ),
    ] = "",
    plan_approval_id: Annotated[
        str,
        typer.Option(
            "--plan-approval-id",
            help="Optional resolved approve_review resolution ID binding approval to the durable plan digest.",
        ),
    ] = "",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the shadow activation plan as JSON."),
    ] = False,
) -> None:
    try:
        report = build_shadow_activation_plan(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            managed_prefix=managed_prefix,
            profile_name=profile_name,
            collision_policy=collision_policy,
            permission_approval_id=permission_approval_id or None,
            plan_approval_id=plan_approval_id or None,
        )
    except ShadowActivationPlanError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    if json_output:
        emit_shadow_activation_plan_json(report)
    else:
        emit_shadow_activation_plan_output(report)


@app.command(
    "shadow-rollback-plan",
    help="Verify rollback readiness for an existing managed-prefix profile pointer.",
    short_help="Plan shadow rollback.",
    rich_help_panel=PANEL_MANAGED,
)
def shadow_rollback_plan(
    candidate_id: Annotated[str, typer.Argument(help="Skill Candidate Ledger candidate ID to verify managed-prefix rollback readiness.")],
    runs_dir: Annotated[Path, typer.Option(help="Run log directory containing candidate and resolution ledgers.")] = Path("runs"),
    skills_dir: Annotated[Path, typer.Option(help="Durable local skills directory for read-only admission context.")] = Path("skills"),
    managed_prefix: Annotated[
        Path | None,
        typer.Option(
            "--managed-prefix",
            help="Managed shadow prefix to inspect. Defaults to <runs-dir>/managed_shadow.",
        ),
    ] = None,
    profile_name: Annotated[
        str,
        typer.Option("--profile-name", help="Managed profile name for rollback planning."),
    ] = "default",
    collision_policy: Annotated[
        str,
        typer.Option(
            "--collision-policy",
            help="Dry-run destination collision policy: block_existing or allow_replace_with_approval.",
        ),
    ] = "block_existing",
    permission_approval_id: Annotated[
        str,
        typer.Option(
            "--permission-approval-id",
            help="Optional resolved input request resolution ID authorizing permission widening in the admission preview.",
        ),
    ] = "",
    plan_approval_id: Annotated[
        str,
        typer.Option(
            "--plan-approval-id",
            help="Optional resolved approve_review resolution ID binding approval to the durable plan digest.",
        ),
    ] = "",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the shadow rollback plan as JSON."),
    ] = False,
) -> None:
    try:
        report = build_shadow_rollback_plan(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            managed_prefix=managed_prefix,
            profile_name=profile_name,
            collision_policy=collision_policy,
            permission_approval_id=permission_approval_id or None,
            plan_approval_id=plan_approval_id or None,
        )
    except ShadowActivationPlanError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    if json_output:
        emit_shadow_rollback_plan_json(report)
    else:
        emit_shadow_rollback_plan_output(report)


@app.command(
    "shadow-activation-acceptance",
    help="Exercise managed-prefix activation mechanics inside a run-scoped acceptance prefix.",
    short_help="Prepare activation acceptance.",
    rich_help_panel=PANEL_MANAGED,
)
def shadow_activation_acceptance(
    candidate_id: Annotated[str, typer.Argument(help="Skill Candidate Ledger candidate ID to exercise managed-prefix activation mechanics in a run-scoped acceptance sandbox.")],
    runs_dir: Annotated[Path, typer.Option(help="Run log directory containing candidate and resolution ledgers.")] = Path("runs"),
    skills_dir: Annotated[Path, typer.Option(help="Durable local skills directory for read-only admission context.")] = Path("skills"),
    managed_prefix: Annotated[
        Path | None,
        typer.Option(
            "--managed-prefix",
            help="Managed shadow prefix to mirror for planning. Defaults to <runs-dir>/managed_shadow.",
        ),
    ] = None,
    acceptance_prefix: Annotated[
        Path | None,
        typer.Option(
            "--acceptance-prefix",
            help="Run-scoped acceptance prefix. Must be under <runs-dir>.",
        ),
    ] = None,
    profile_name: Annotated[
        str,
        typer.Option("--profile-name", help="Managed profile name for acceptance planning."),
    ] = "default",
    collision_policy: Annotated[
        str,
        typer.Option(
            "--collision-policy",
            help="Dry-run destination collision policy: block_existing or allow_replace_with_approval.",
        ),
    ] = "block_existing",
    permission_approval_id: Annotated[
        str,
        typer.Option(
            "--permission-approval-id",
            help="Optional resolved input request resolution ID authorizing permission widening in the admission preview.",
        ),
    ] = "",
    plan_approval_id: Annotated[
        str,
        typer.Option(
            "--plan-approval-id",
            help="Optional resolved approve_review resolution ID binding approval to the durable plan digest.",
        ),
    ] = "",
    prepare_acceptance_evidence: Annotated[
        bool,
        typer.Option(
            "--prepare-acceptance-evidence",
            help="Create or reuse run-scoped acceptance evidence under <runs-dir> only.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the shadow activation acceptance report as JSON."),
    ] = False,
) -> None:
    try:
        report = build_shadow_activation_acceptance_report(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            managed_prefix=managed_prefix,
            acceptance_prefix=acceptance_prefix,
            profile_name=profile_name,
            collision_policy=collision_policy,
            permission_approval_id=permission_approval_id or None,
            plan_approval_id=plan_approval_id or None,
            prepare_acceptance_evidence=prepare_acceptance_evidence,
        )
    except ShadowActivationPlanError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    if json_output:
        emit_shadow_activation_acceptance_json(report)
    else:
        emit_shadow_activation_acceptance_output(report)


@app.command(
    "shadow-write-gate",
    help="Verify human-gated managed-prefix write readiness without writing.",
    short_help="Verify managed write gate.",
    rich_help_panel=PANEL_MANAGED,
)
def shadow_write_gate(
    candidate_id: Annotated[str, typer.Argument(help="Skill Candidate Ledger candidate ID to verify human-gated managed-prefix write readiness without writing.")],
    runs_dir: Annotated[Path, typer.Option(help="Run log directory containing candidate and resolution ledgers.")] = Path("runs"),
    skills_dir: Annotated[Path, typer.Option(help="Durable local skills directory for read-only admission context.")] = Path("skills"),
    managed_prefix: Annotated[
        Path | None,
        typer.Option(
            "--managed-prefix",
            help="Managed shadow prefix to inspect. Defaults to <runs-dir>/managed_shadow.",
        ),
    ] = None,
    acceptance_prefix: Annotated[
        Path | None,
        typer.Option(
            "--acceptance-prefix",
            help="Run-scoped acceptance prefix to verify. Must be under <runs-dir>.",
        ),
    ] = None,
    profile_name: Annotated[
        str,
        typer.Option("--profile-name", help="Managed profile name for write-gate verification."),
    ] = "default",
    collision_policy: Annotated[
        str,
        typer.Option(
            "--collision-policy",
            help="Dry-run destination collision policy: block_existing or allow_replace_with_approval.",
        ),
    ] = "block_existing",
    permission_approval_id: Annotated[
        str,
        typer.Option(
            "--permission-approval-id",
            help="Optional resolved input request resolution ID authorizing permission widening in the admission preview.",
        ),
    ] = "",
    plan_approval_id: Annotated[
        str,
        typer.Option(
            "--plan-approval-id",
            help="Optional resolved approve_review resolution ID binding approval to the durable plan digest.",
        ),
    ] = "",
    acceptance_plan_digest: Annotated[
        str,
        typer.Option(
            "--acceptance-plan-digest",
            help="Optional exact acceptance plan digest expected before future write-mode work.",
        ),
    ] = "",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the shadow write gate report as JSON."),
    ] = False,
) -> None:
    try:
        report = build_shadow_write_gate_report(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            managed_prefix=managed_prefix,
            acceptance_prefix=acceptance_prefix,
            profile_name=profile_name,
            collision_policy=collision_policy,
            permission_approval_id=permission_approval_id or None,
            plan_approval_id=plan_approval_id or None,
            acceptance_plan_digest=acceptance_plan_digest or None,
        )
    except ShadowActivationPlanError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    if json_output:
        emit_shadow_write_gate_json(report)
    else:
        emit_shadow_write_gate_output(report)


@app.command(
    "shadow-managed-write",
    help="Preflight or execute the digest-bound human-approved managed-prefix write lane.",
    short_help="Preflight managed-prefix write.",
    rich_help_panel=PANEL_MANAGED,
)
def shadow_managed_write(
    candidate_id: Annotated[str, typer.Argument(help="Skill Candidate Ledger candidate ID to preflight for human-approved managed-prefix writing.")],
    runs_dir: Annotated[Path, typer.Option(help="Run log directory containing candidate, resolution, checkpoint, and acceptance evidence.")] = Path("runs"),
    skills_dir: Annotated[Path, typer.Option(help="Durable local skills directory for read-only admission context.")] = Path("skills"),
    managed_prefix: Annotated[
        Path | None,
        typer.Option(
            "--managed-prefix",
            help="Managed shadow prefix to inspect. Defaults to <runs-dir>/managed_shadow.",
        ),
    ] = None,
    acceptance_prefix: Annotated[
        Path | None,
        typer.Option(
            "--acceptance-prefix",
            help="Run-scoped acceptance prefix to verify. Must be under <runs-dir>.",
        ),
    ] = None,
    profile_name: Annotated[
        str,
        typer.Option("--profile-name", help="Managed profile name for write planning."),
    ] = "default",
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Preflight or execute the human-approved managed-prefix write.",
        ),
    ] = True,
    collision_policy: Annotated[
        str,
        typer.Option(
            "--collision-policy",
            help="Dry-run destination collision policy: block_existing or allow_replace_with_approval.",
        ),
    ] = "block_existing",
    permission_approval_id: Annotated[
        str,
        typer.Option(
            "--permission-approval-id",
            help="Optional resolved input request resolution ID authorizing permission widening in the admission preview.",
        ),
    ] = "",
    plan_approval_id: Annotated[
        str,
        typer.Option(
            "--plan-approval-id",
            help="Optional resolved approve_review resolution ID binding approval to the durable plan digest.",
        ),
    ] = "",
    expected_source_sha256: Annotated[
        str,
        typer.Option("--expected-source-sha256", help="Optional expected candidate source SHA-256."),
    ] = "",
    expected_durable_plan_digest: Annotated[
        str,
        typer.Option("--expected-durable-plan-digest", help="Optional expected durable admission plan digest."),
    ] = "",
    expected_shadow_plan_digest: Annotated[
        str,
        typer.Option("--expected-shadow-plan-digest", help="Optional expected shadow activation plan digest."),
    ] = "",
    expected_rollback_plan_digest: Annotated[
        str,
        typer.Option("--expected-rollback-plan-digest", help="Optional expected shadow rollback plan digest."),
    ] = "",
    expected_acceptance_plan_digest: Annotated[
        str,
        typer.Option("--expected-acceptance-plan-digest", help="Optional expected shadow acceptance plan digest."),
    ] = "",
    expected_managed_write_plan_digest: Annotated[
        str,
        typer.Option("--expected-managed-write-plan-digest", help="Optional expected managed-write plan digest."),
    ] = "",
    expected_checkpoint_hash: Annotated[
        str,
        typer.Option("--expected-checkpoint-hash", help="Optional expected latest evidence checkpoint hash."),
    ] = "",
    write_approval_id: Annotated[
        str,
        typer.Option("--write-approval-id", help="Optional human write approval resolution ID for --no-dry-run."),
    ] = "",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the shadow managed-write report as JSON."),
    ] = False,
) -> None:
    try:
        report = build_shadow_managed_write_report(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            dry_run=dry_run,
            managed_prefix=managed_prefix,
            acceptance_prefix=acceptance_prefix,
            profile_name=profile_name,
            collision_policy=collision_policy,
            permission_approval_id=permission_approval_id or None,
            plan_approval_id=plan_approval_id or None,
            expected_source_sha256=expected_source_sha256 or None,
            expected_durable_plan_digest=expected_durable_plan_digest or None,
            expected_shadow_plan_digest=expected_shadow_plan_digest or None,
            expected_rollback_plan_digest=expected_rollback_plan_digest or None,
            expected_acceptance_plan_digest=expected_acceptance_plan_digest or None,
            expected_managed_write_plan_digest=expected_managed_write_plan_digest or None,
            expected_checkpoint_hash=expected_checkpoint_hash or None,
            write_approval_id=write_approval_id or None,
        )
    except ShadowActivationPlanError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    if json_output:
        emit_shadow_managed_write_json(report)
    else:
        emit_shadow_managed_write_output(report)


@app.command(
    "promote-candidate",
    help="Record human approval for candidate status without durable skill admission.",
    short_help="Approve candidate status.",
    rich_help_panel=PANEL_HUMAN,
)
def promote_candidate(
    candidate_id: Annotated[str, typer.Argument(help="Skill Candidate Ledger candidate ID to approve for candidate status.")],
    runs_dir: Annotated[Path, typer.Option(help="Run log directory containing the skill candidate ledger.")] = Path("runs"),
    reviewer: Annotated[str, typer.Option("--reviewer", help="Human reviewer approving promotion.")] = "",
    notes: Annotated[str, typer.Option("--notes", help="Human review notes explaining why promotion is approved.")] = "",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the promoted candidate entry as JSON."),
    ] = False,
) -> None:
    try:
        entry = approve_candidate_promotion(
            runs_dir=runs_dir,
            candidate_id=candidate_id,
            reviewer=reviewer,
            notes=notes,
        )
    except SkillCandidateLedgerError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    if json_output:
        typer.echo(json.dumps(entry.model_dump(mode="json"), indent=2, sort_keys=True))
    else:
        typer.echo("CANDIDATE_PROMOTED")
        typer.echo(f"Candidate: {entry.candidate_id}")
        typer.echo(f"Skill: {entry.skill_name}")
        typer.echo(f"Status: {entry.status}")
        typer.echo("Durable skill installed: false")
        typer.echo("Auto-promotion: disabled")
        typer.echo(f"Promotion approved by: {entry.promotion_approved_by}")


@app.command(
    "admission-plan",
    help="Inspect durable-admission readiness evidence without copying or installing skills.",
    short_help="Inspect admission readiness.",
    rich_help_panel=PANEL_CANDIDATE,
)
def admission_plan(
    candidate_id: Annotated[str, typer.Argument(help="Skill Candidate Ledger candidate ID to inspect.")],
    runs_dir: Annotated[Path, typer.Option(help="Run log directory containing the skill candidate ledger.")] = Path("runs"),
    skills_dir: Annotated[Path, typer.Option(help="Durable local skills directory.")] = Path("skills"),
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the admission plan as JSON."),
    ] = False,
) -> None:
    try:
        report = build_admission_plan(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
        )
    except AdmissionPlanError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    if json_output:
        emit_admission_plan_json(report)
    else:
        emit_admission_plan_output(report)


@app.command(
    "admit-candidate",
    help="Preview durable admission write evidence; write mode remains intentionally unavailable.",
    short_help="Preview durable admission.",
    rich_help_panel=PANEL_HUMAN,
)
def admit_candidate(
    candidate_id: Annotated[str, typer.Argument(help="Skill Candidate Ledger candidate ID to preview for durable admission.")],
    runs_dir: Annotated[Path, typer.Option(help="Run log directory containing the skill candidate ledger.")] = Path("runs"),
    skills_dir: Annotated[Path, typer.Option(help="Durable local skills directory.")] = Path("skills"),
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run/--no-dry-run",
            help="Preview durable admission mutation. Write mode is intentionally unavailable.",
        ),
    ] = True,
    collision_policy: Annotated[
        str,
        typer.Option(
            "--collision-policy",
            help="Dry-run destination collision policy: block_existing or allow_replace_with_approval.",
        ),
    ] = "block_existing",
    permission_approval_id: Annotated[
        str,
        typer.Option(
            "--permission-approval-id",
            help="Optional resolved input request resolution ID authorizing permission widening for the dry-run write plan.",
        ),
    ] = "",
    plan_approval_id: Annotated[
        str,
        typer.Option(
            "--plan-approval-id",
            help="Optional resolved approve_review resolution ID whose notes bind approval to the emitted plan digest.",
        ),
    ] = "",
    prepare_write_evidence: Annotated[
        bool,
        typer.Option(
            "--prepare-write-evidence/--no-prepare-write-evidence",
            help="Create run-scoped snapshot and destination staging evidence for the dry-run plan.",
        ),
    ] = False,
    expected_source_sha256: Annotated[
        str,
        typer.Option(
            "--expected-source-sha256",
            help="Optional expected source SHA-256; mismatches block evidence preparation.",
        ),
    ] = "",
    prepare_dependency_evidence: Annotated[
        bool,
        typer.Option(
            "--prepare-dependency-evidence/--no-prepare-dependency-evidence",
            help="Create run-scoped no-write dependency evidence manifest for the dry-run plan.",
        ),
    ] = False,
    expected_dependency_plan_digest: Annotated[
        str,
        typer.Option(
            "--expected-dependency-plan-digest",
            help="Optional expected dependency plan digest; mismatches block dependency evidence preparation.",
        ),
    ] = "",
    dependency_approval_id: Annotated[
        str,
        typer.Option(
            "--dependency-approval-id",
            help="Optional resolved approve_review resolution ID whose notes bind review to dependency_plan_digest.",
        ),
    ] = "",
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the durable admission preview as JSON."),
    ] = False,
) -> None:
    try:
        report = build_durable_admission_preview(
            candidate_id,
            runs_dir=runs_dir,
            skills_dir=skills_dir,
            dry_run=dry_run,
            collision_policy=collision_policy,
            permission_approval_id=permission_approval_id or None,
            plan_approval_id=plan_approval_id or None,
            prepare_write_evidence=prepare_write_evidence,
            expected_source_sha256=expected_source_sha256 or None,
            prepare_dependency_evidence=prepare_dependency_evidence,
            expected_dependency_plan_digest=expected_dependency_plan_digest or None,
            dependency_approval_id=dependency_approval_id or None,
        )
    except AdmissionPlanError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc

    if json_output:
        emit_durable_admission_preview_json(report)
    else:
        emit_durable_admission_preview_output(report)


@app.command(
    "eval",
    help="Run a JSONL eval suite through the real skill-agent loop and write reports.",
    short_help="Run an eval suite.",
    rich_help_panel=PANEL_EVAL,
)
def eval_command(
    suite: Annotated[
        Path,
        typer.Option(
            help="JSONL eval suite.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    skills_dir: Annotated[Path, typer.Option(help="Local skills directory.")] = Path("skills"),
    runs_dir: Annotated[Path, typer.Option(help="Eval run log output directory.")] = Path("runs/evals"),
    report_dir: Annotated[
        Path | None,
        typer.Option(help="Eval report output directory. Defaults to the runs directory."),
    ] = None,
    temporary_skills: Annotated[
        bool,
        typer.Option(
            "--temporary-skills/--no-temporary-skills",
            help="Draft temporary skills while evaluating missing-capability paths.",
        ),
    ] = False,
    scripted_skills: Annotated[
        bool,
        typer.Option(
            "--scripted-skills/--no-scripted-skills",
            help="Allow validated local scripted skills during eval runs.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print the eval report as JSON."),
    ] = False,
) -> None:
    try:
        report = run_eval_suite(
            suite_path=suite,
            skills_dir=skills_dir,
            runs_dir=runs_dir,
            create_temporary_skills=temporary_skills,
            allow_scripted_skills=scripted_skills,
        )
    except EvalSuiteError as exc:
        raise typer.BadParameter(str(exc)) from exc

    json_path, md_path = write_eval_reports(report, report_dir or runs_dir)
    report["json_report_path"] = str(json_path)
    report["markdown_report_path"] = str(md_path)
    if json_output:
        typer.echo(json.dumps(redact_data(report), indent=2, sort_keys=True))
    else:
        aggregate = report["aggregate"]
        typer.echo("EVAL")
        typer.echo(f"Suite: {report['suite']}")
        typer.echo(f"Total: {aggregate['total']}")
        typer.echo(f"Passed: {aggregate['passed']}")
        typer.echo(f"Failed: {aggregate['failed']}")
        typer.echo(f"Task pass rate: {aggregate['task_pass_rate']}")
        typer.echo(f"Average request quality: {aggregate['average_request_quality']}")
        typer.echo(
            f"Trace completeness: {aggregate['trace_complete_count']} / {aggregate['total']}"
        )
        typer.echo(f"Failure categories: {aggregate['failure_categories'] or '-'}")
        weakest = aggregate.get("weakest_diagnostic_dimensions") or []
        weakest_names = ", ".join(item["dimension"] for item in weakest) if weakest else "-"
        typer.echo(f"Weakest diagnostic dimensions: {weakest_names}")
        typer.echo(f"JSON report: {json_path}")
        typer.echo(f"Markdown summary: {md_path}")
    if not report["passed"]:
        raise typer.Exit(1)


@app.command(
    help="Explain one JSON run log and optionally include matching candidate evidence.",
    short_help="Explain one run log.",
    rich_help_panel=PANEL_EVAL,
)
def explain(
    run_log: Annotated[
        Path,
        typer.Argument(
            help="Run log JSON file to explain.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            resolve_path=True,
        ),
    ],
    include_candidates: Annotated[
        bool,
        typer.Option("--include-candidates", help="Include matching Skill Candidate Ledger entries."),
    ] = False,
) -> None:
    try:
        typer.echo(explain_run_log(run_log, include_candidates=include_candidates))
    except ExplainError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc


def main() -> None:
    app()


if __name__ == "__main__":
    main()
