from __future__ import annotations

import json
import subprocess
from pathlib import Path
from textwrap import dedent
from shutil import copytree

from typer.testing import CliRunner

from app.cli import app
from app.registry import SkillRegistry
from app.script_executor import STDOUT_LIMIT, execute_scripted_skill
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
    assert execution.parsed_stdout == {"word_count": 3}
    assert execution.output_validated
    assert execution.failure_category is None
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
    assert "SECURITY" in result.stdout
    assert "Scripted skills are trusted-local subprocesses" in result.stdout
    assert "SCRIPT_EXECUTED" in result.stdout
    assert "Skill: count-words" in result.stdout
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    data = json.loads(logs[0].read_text(encoding="utf-8"))
    assert data["script_executions"][0]["skill_name"] == "count-words"
    assert data["security_warnings"] == [
        "Scripted skills are trusted-local subprocesses, not a true sandbox."
    ]
    execution = data["script_executions"][0]
    assert json.loads(execution["stdout"]) == {"word_count": 6}
    assert execution["parsed_stdout"] == {"word_count": 6}
    assert execution["output_validated"]
    assert execution["failure_category"] is None
    assert execution["security_warnings"] == data["security_warnings"]


def test_cli_json_surfaces_scripted_skill_warning_when_enabled(tmp_path, repo_root: Path):
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
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["security_warnings"] == [
        "Scripted skills are trusted-local subprocesses, not a true sandbox."
    ]
    assert "SCRIPTED_SKILL_WARNING" in payload["trace"]
    warning_events = [
        event
        for event in payload["trace_events"]
        if event["stage"] == "SCRIPTED_SKILL_WARNING"
    ]
    assert len(warning_events) == 1
    assert warning_events[0]["message"] == payload["security_warnings"][0]

    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    persisted = json.loads(logs[0].read_text(encoding="utf-8"))
    assert persisted["security_warnings"] == payload["security_warnings"]
    assert "SCRIPTED_SKILL_WARNING" in persisted["trace"]


def test_execute_scripted_skill_redacts_stdout_and_stderr(tmp_path, repo_root: Path):
    record = _copied_script_record(tmp_path, repo_root)
    _write_script(
        record.path.parent,
        """
        import json
        import sys
        fake_key = "s" + "k-" + ("a" * 24)
        print(json.dumps({"word_count": 1, "token": fake_key, "auth": "Bearer " + fake_key}))
        sys.stderr.write("api_key=" + fake_key)
        """,
    )

    execution = execute_scripted_skill(record, {"text": "one"})

    assert execution.returncode == 0
    assert execution.redactions_applied
    assert "[REDACTED:openai_key]" in execution.stdout
    assert "[REDACTED:bearer]" in execution.stdout
    assert "api_key=[REDACTED:credential]" in execution.stderr
    assert "sk-" not in execution.stdout
    assert "sk-" not in execution.stderr
    assert execution.parsed_stdout["token"] == "[REDACTED:openai_key]"
    assert execution.parsed_stdout["auth"] == "[REDACTED:bearer]"
    assert execution.output_validated


def test_execute_scripted_skill_invalid_json_failure(tmp_path, repo_root: Path):
    record = _copied_script_record(tmp_path, repo_root)
    _write_script(record.path.parent, 'print("not json")')

    execution = execute_scripted_skill(record, {"text": "one"})

    assert execution.returncode == 0
    assert execution.failure_category == "invalid_json"
    assert not execution.output_validated


def test_execute_scripted_skill_schema_mismatch_failure(tmp_path, repo_root: Path):
    record = _copied_script_record(tmp_path, repo_root)
    _write_script(record.path.parent, 'import json; print(json.dumps({"word_count": "three"}))')

    execution = execute_scripted_skill(record, {"text": "one two three"})

    assert execution.returncode == 0
    assert execution.parsed_stdout == {"word_count": "three"}
    assert execution.failure_category == "output_schema_mismatch"
    assert not execution.output_validated


def test_execute_scripted_skill_huge_output_is_capped_and_failed(tmp_path, repo_root: Path):
    record = _copied_script_record(tmp_path, repo_root)
    _write_script(record.path.parent, f'print("x" * {STDOUT_LIMIT + 100})')

    execution = execute_scripted_skill(record, {"text": "one"})

    assert execution.failure_category == "output_too_large"
    assert len(execution.stdout) < STDOUT_LIMIT + 100
    assert "truncated" in execution.stdout


def test_execute_scripted_skill_timeout_failure(tmp_path, repo_root: Path):
    record = _copied_script_record(tmp_path, repo_root)
    assert record.script is not None
    record.script.timeout_seconds = 1
    _write_script(record.path.parent, "import time; time.sleep(2)")

    execution = execute_scripted_skill(record, {"text": "one"})

    assert execution.timed_out
    assert execution.failure_category == "timeout"


def test_execute_scripted_skill_nonzero_failure(tmp_path, repo_root: Path):
    record = _copied_script_record(tmp_path, repo_root)
    _write_script(record.path.parent, "import sys; print('bad'); sys.exit(2)")

    execution = execute_scripted_skill(record, {"text": "one"})

    assert execution.returncode == 2
    assert execution.failure_category == "nonzero_exit"


def _copied_script_record(tmp_path: Path, repo_root: Path):
    skills_dir = tmp_path / "scripted-skills"
    copytree(repo_root / "tests" / "fixtures" / "scripted-skills", skills_dir)
    registry = SkillRegistry.load(skills_dir, allow_scripts=True)
    record = registry.get("count-words")
    assert record is not None
    return record


def _write_script(skill_dir: Path, body: str) -> None:
    script = skill_dir / "scripts" / "count_words.py"
    script.write_text(
        "from __future__ import annotations\n"
        + dedent(body).strip()
        + "\n",
        encoding="utf-8",
    )
