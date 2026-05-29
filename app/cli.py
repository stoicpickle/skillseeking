from __future__ import annotations

from pathlib import Path
from typing import Annotated
import json

import typer

from app.agent_loop import run_task
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
) -> None:
    result = run_task(
        task,
        skills_dir=skills_dir,
        runs_dir=runs_dir,
        create_temporary_skills=temporary_skills,
        allow_scripted_skills=scripted_skills,
    )
    for stage in result.run_log.trace:
        typer.echo(stage)
    for decision in result.run_log.capability_decisions:
        selected = decision.get("selected_skill") if decision["decision"] == "USE_SKILL" else None
        typer.echo(f"{decision['decision']} {selected or '-'} :: {decision['capability']}")
    for request in result.run_log.skill_requests:
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
    for execution in result.run_log.script_executions:
        typer.echo("")
        typer.echo("SCRIPT_EXECUTED")
        typer.echo(f"Skill: {execution.skill_name}")
        typer.echo(f"Return code: {execution.returncode}")
        typer.echo(f"Timed out: {execution.timed_out}")
        if execution.stdout:
            typer.echo(f"Stdout: {execution.stdout}")
        if execution.stderr:
            typer.echo(f"Stderr: {execution.stderr}")
    typer.echo(f"RUN_LOG {result.run_log_path}")
    if result.exit_code:
        raise typer.Exit(result.exit_code)


@app.command()
def registry(
    skills_dir: Annotated[Path, typer.Option(help="Local skills directory.")] = Path("skills"),
) -> None:
    skill_registry = SkillRegistry.load(skills_dir)
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


def main() -> None:
    app()


if __name__ == "__main__":
    main()
