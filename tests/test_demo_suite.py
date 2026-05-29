from __future__ import annotations

from typer.testing import CliRunner

from app.cli import app


def assert_output_contains(stdout: str, landmarks: list[str]) -> None:
    for landmark in landmarks:
        assert landmark in stdout


def test_core_demo_existing_skill(copied_seed_skills, tmp_path):
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run",
            "Extract claims from this article and write a structured summary with source-quality notes.",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code == 0
    assert_output_contains(
        result.stdout,
        [
            "PLANNING",
            "CHECKING_SKILLS",
            "LOADING_SKILL",
            "ROUTE_COMPLETE",
            "RESULT",
            "USE_SKILL extract-claims",
            "USE_SKILL source-quality-check",
            "USE_SKILL write-structured-answer",
            "Exit code: 0",
        ],
    )
    assert "BLOCKED_MISSING_SKILL" not in result.stdout


def test_core_demo_temporary_skill(copied_seed_skills, tmp_path):
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run",
            "Cluster arguments from these sources.",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code == 0
    assert_output_contains(
        result.stdout,
        [
            "PLANNING",
            "CHECKING_SKILLS",
            "BLOCKED_MISSING_SKILL",
            "REQUESTING_SKILL",
            "DRAFTING_TEMP_SKILL",
            "VALIDATION_PASSED",
            "LOADING_TEMP_SKILL",
            "ROUTE_COMPLETE",
            "RESULT",
            "Temporary skill: argument-clustering",
            "Validation passed: True",
            "Loaded: True",
            "Temporary skills: argument-clustering",
            "Exit code: 0",
        ],
    )


def test_core_demo_blocked_skill(copied_seed_skills, tmp_path):
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "run",
            "Extract claims from these two sources and identify contradictions.",
            "--no-temporary-skills",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(tmp_path / "runs"),
        ],
    )

    assert result.exit_code == 1
    assert_output_contains(
        result.stdout,
        [
            "PLANNING",
            "CHECKING_SKILLS",
            "BLOCKED_MISSING_SKILL",
            "REQUESTING_SKILL",
            "ROUTE_COMPLETE",
            "RESULT",
            "REQUEST_SKILL - :: detect contradictions",
            "Missing capability: detect contradictions",
            "Requested skill: detect-contradictions",
            "Exit code: 1",
        ],
    )
    assert "DRAFTING_TEMP_SKILL" not in result.stdout
    assert "Temporary skill: detect-contradictions" not in result.stdout


def test_core_demo_malicious_skill_rejected(malicious_skills_dir):
    runner = CliRunner()

    result = runner.invoke(app, ["registry", "--skills-dir", str(malicious_skills_dir)])

    assert result.exit_code == 0
    assert_output_contains(
        result.stdout,
        [
            "safe-research-note",
            "REJECTED",
            "metadata-routing-attack",
            "body-prompt-injection",
            "obfuscated-instruction",
            "secrets-permission-attack",
        ],
    )
