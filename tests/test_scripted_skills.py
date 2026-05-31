from __future__ import annotations

import json
import subprocess
from pathlib import Path
from shutil import copytree

from typer.testing import CliRunner

from app.cli import app
from app.registry import SkillRegistry
from app.script_executor import execute_scripted_skill
from app.script_validator import validate_script_tests


def test_scripted_skill_rejected_unless_explicitly_enabled(repo_root: Path):
    skills_dir = repo_root / "tests" / "fixtures" / "scripted-skills"

    disabled = SkillRegistry.load(skills_dir)
    enabled = SkillRegistry.load(skills_dir, allow_scripts=True)

    assert disabled.get("count-words") is None
    assert any(rejection.name == "count-words" for rejection in disabled.rejections())
    assert enabled.get("count-words") is not None
    assert enabled.rejections() == []


def test_scripted_skill_validates_with_relative_skills_dir():
    skills_dir = Path("tests/fixtures/scripted-skills")

    enabled = SkillRegistry.load(skills_dir, allow_scripts=True)

    assert enabled.get("count-words") is not None
    assert enabled.rejections() == []


def test_script_validation_timeout_returns_failure(monkeypatch, repo_root: Path):
    skills_dir = repo_root / "tests" / "fixtures" / "scripted-skills" / "count-words"

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["pytest"], timeout=1, output="out", stderr="err")

    monkeypatch.setattr(subprocess, "run", raise_timeout)

    passed, output = validate_script_tests(skills_dir, timeout_seconds=1)

    assert not passed
    assert output == "out\nerr"


def test_execute_scripted_skill_contract(repo_root: Path):
    skills_dir = repo_root / "tests" / "fixtures" / "scripted-skills"
    registry = SkillRegistry.load(skills_dir, allow_scripts=True)
    record = registry.get("count-words")
    assert record is not None

    execution = execute_scripted_skill(record, {"text": "one two three"})

    assert execution.returncode == 0
    assert json.loads(execution.stdout) == {"word_count": 3}
    assert not execution.timed_out


def test_cli_executes_scripted_skill_when_enabled(tmp_path, repo_root: Path):
    skills_dir = tmp_path / "scripted-skills"
    copytree(repo_root / "tests" / "fixtures" / "scripted-skills", skills_dir)
    runs_dir = tmp_path / "runs"
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run",
            "Count words in one two three.",
            "--scripted-skills",
            "--no-temporary-skills",
            "--skills-dir",
            str(skills_dir),
            "--runs-dir",
            str(runs_dir),
        ],
    )

    assert result.exit_code == 0
    assert "EXECUTING_SCRIPT" in result.stdout
    assert "SCRIPT_EXECUTED" in result.stdout
    assert "Skill: count-words" in result.stdout
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    data = json.loads(logs[0].read_text(encoding="utf-8"))
    assert data["script_executions"][0]["skill_name"] == "count-words"
    assert json.loads(data["script_executions"][0]["stdout"]) == {"word_count": 6}
