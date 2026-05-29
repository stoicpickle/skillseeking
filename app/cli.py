from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from app.agent_loop import run_task
from app.registry import SkillRegistry


app = typer.Typer(no_args_is_help=True)


@app.command()
def run(
    task: Annotated[str, typer.Argument(help="Task text to route through local skills.")],
    skills_dir: Annotated[Path, typer.Option(help="Local skills directory.")] = Path("skills"),
    runs_dir: Annotated[Path, typer.Option(help="Run log output directory.")] = Path("runs"),
) -> None:
    result = run_task(task, skills_dir=skills_dir, runs_dir=runs_dir)
    for stage in result.run_log.trace:
        typer.echo(stage)
    for decision in result.run_log.capability_decisions:
        selected = decision.get("selected_skill") or decision.get("best_match", {}).get("skill_name")
        typer.echo(f"{decision['decision']} {selected or '-'} :: {decision['capability']}")
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


def main() -> None:
    app()


if __name__ == "__main__":
    main()

