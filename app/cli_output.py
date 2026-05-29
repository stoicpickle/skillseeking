from __future__ import annotations

from collections.abc import Iterable

import typer

from app.models import AgentRunResult, LoadedSkillLog, ScriptExecutionLog


def emit_run_output(result: AgentRunResult) -> None:
    typer.echo("TRACE")
    for stage in result.run_log.trace:
        typer.echo(stage)

    typer.echo("")
    typer.echo("DECISIONS")
    for decision in result.run_log.capability_decisions:
        selected = decision.get("selected_skill") if decision["decision"] == "USE_SKILL" else None
        typer.echo(f"{decision['decision']} {selected or '-'} :: {decision['capability']}")

    _emit_skill_requests(result.run_log.skill_requests)
    _emit_script_executions(result.run_log.script_executions)
    _emit_result(result)


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


def _emit_script_executions(script_executions: Iterable[ScriptExecutionLog]) -> None:
    for execution in script_executions:
        typer.echo("")
        typer.echo("SCRIPT_EXECUTED")
        typer.echo(f"Skill: {execution.skill_name}")
        typer.echo(f"Return code: {execution.returncode}")
        typer.echo(f"Timed out: {execution.timed_out}")
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
    typer.echo(f"Exit code: {result.exit_code}")
    typer.echo(f"Loaded skills: {loaded_names}")
    typer.echo(f"Temporary skills: {temporary_names}")
    typer.echo(f"Run log: {result.run_log_path}")


def _format_skill_names(skills: Iterable[LoadedSkillLog]) -> str:
    names = [skill.name for skill in skills]
    if not names:
        return "-"
    return ", ".join(names)
