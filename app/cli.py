from __future__ import annotations

from pathlib import Path
from typing import Annotated
import json

import typer

from app.admission_plan import AdmissionPlanError, build_admission_plan
from app.agent_loop import run_task
from app.cli_output import (
    emit_admission_plan_json,
    emit_admission_plan_output,
    emit_candidates_json,
    emit_candidates_output,
    emit_run_json,
    emit_registry_json,
    emit_run_output,
)
from app.eval_runner import EvalSuiteError, run_eval_suite, write_eval_reports
from app.explain import ExplainError, explain_run_log
from app.input_focus import (
    collect_input_request_queue,
    input_request_kind_counts,
    input_request_source_warnings,
)
from app.input_resolution import InputResolutionError, resolve_input_request as resolve_input_request_report
from app.librarian import analyze_library
from app.skill_candidate_ledger import (
    SkillCandidateLedgerError,
    approve_candidate_promotion,
    ledger_path,
    load_candidate_ledger,
)
from app.registry import SkillRegistry


app = typer.Typer(no_args_is_help=True)


@app.command()
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


@app.command()
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


@app.command()
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


@app.command("input-requests")
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


@app.command("resolve-input-request")
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


@app.command()
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


@app.command("promote-candidate")
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


@app.command("admission-plan")
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


@app.command("eval")
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
        typer.echo(json.dumps(report, indent=2, sort_keys=True))
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


@app.command()
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
