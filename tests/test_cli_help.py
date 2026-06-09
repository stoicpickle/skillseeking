from __future__ import annotations

from typer.testing import CliRunner

from app.cli import app


def test_top_level_help_groups_commands_by_operator_path():
    runner = CliRunner()

    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "Governed local skill acquisition CLI" in result.stdout
    assert "Recommended reviewer path" in result.stdout
    for panel in [
        "Start here",
        "Operator decision review",
        "Core task loop",
        "Human input and approvals",
        "Candidate evidence",
        "Managed-prefix local writes",
        "Eval and diagnostics",
    ]:
        assert panel in result.stdout
    for command, short_help in {
        "operator-summary": "Show prioritized operator decisions.",
        "candidate-decision": "Summarize next candidate decision.",
        "run": "Run a task through local skills.",
        "admit-candidate": "Preview durable admission.",
        "shadow-managed-write": "Preflight managed-prefix write.",
        "eval": "Run an eval suite.",
    }.items():
        assert command in result.stdout
        assert short_help in result.stdout


def test_operator_summary_command_help_states_front_door_role():
    runner = CliRunner()

    result = runner.invoke(app, ["operator-summary", "--help"])

    assert result.exit_code == 0
    assert "Show prioritized operator decisions before raw evidence sections." in result.stdout
    assert "--runs-dir" in result.stdout
    assert "--json" in result.stdout
