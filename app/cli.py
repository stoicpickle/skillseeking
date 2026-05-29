from __future__ import annotations

from pathlib import Path
from typing import Annotated
import json

import typer

from app.agent_loop import run_task
from app.cli_output import emit_run_output
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
    emit_run_output(result)
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
