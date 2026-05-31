from __future__ import annotations

from pathlib import Path
from typing import Annotated
import json

import typer

from app.agent_loop import run_task
from app.cli_output import emit_run_json, emit_registry_json, emit_run_output
from app.eval_runner import EvalSuiteError, run_eval_suite, write_eval_reports
from app.explain import ExplainError, explain_run_log
from app.librarian import analyze_library
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
) -> None:
    try:
        typer.echo(explain_run_log(run_log))
    except ExplainError as exc:
        typer.echo(str(exc))
        raise typer.Exit(1) from exc


def main() -> None:
    app()


if __name__ == "__main__":
    main()
