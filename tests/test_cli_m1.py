from __future__ import annotations

import json

from typer.testing import CliRunner

from app.cli import app


def test_registry_command_lists_seed_skills(seed_skills_dir):
    runner = CliRunner()

    result = runner.invoke(app, ["registry", "--skills-dir", str(seed_skills_dir)])

    assert result.exit_code == 0
    assert "extract-claims" in result.stdout
    assert "write-structured-answer" in result.stdout


def test_existing_skill_demo(copied_seed_skills, tmp_path):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"

    result = runner.invoke(
        app,
        [
            "run",
            "Extract claims from this article and write a structured summary with source-quality notes.",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )

    assert result.exit_code == 0
    assert "PLANNING" in result.stdout
    assert "USE_SKILL extract-claims" in result.stdout
    assert "USE_SKILL source-quality-check" in result.stdout
    assert "USE_SKILL write-structured-answer" in result.stdout
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    data = json.loads(logs[0].read_text(encoding="utf-8"))
    loaded_names = {skill["name"] for skill in data["skills_loaded"]}
    assert {"extract-claims", "source-quality-check", "write-structured-answer"} <= loaded_names
    assert data["skill_requests"] == []
    assert "markdown_body" not in logs[0].read_text(encoding="utf-8")

