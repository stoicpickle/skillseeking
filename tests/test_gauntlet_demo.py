from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from shutil import copytree


def test_skill_gauntlet_demo(tmp_path, repo_root: Path):
    skills_dir = tmp_path / "gauntlet-skills"
    runs_dir = tmp_path / "runs"
    copytree(repo_root / "tests" / "fixtures" / "gauntlet-skills", skills_dir)
    durable_entries_before = {path.name for path in skills_dir.iterdir()}

    result = subprocess.run(  # noqa: S603 - args are controlled by the test.
        [
            sys.executable,
            "scripts/run_gauntlet_demo.py",
            "--skills-dir",
            str(skills_dir),
            "--runs-dir",
            str(runs_dir),
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert_in_order(
        result.stdout,
        [
            "SKILL GAUNTLET",
            "REGISTRY",
            "Accepted skills: 3",
            "Rejected skills: 2",
            "TRACE",
            "LOADING_SKILL extract-claims",
            "LOADING_SKILL source-quality-check",
            "LOADING_SKILL write-structured-answer",
            "DRAFTING_TEMP_SKILL argument-clustering",
            "VALIDATION_PASSED argument-clustering",
            "LOADING_TEMP_SKILL argument-clustering",
            "DRAFTING_TEMP_SKILL local-python-analysis",
            "VALIDATION_FAILED local-python-analysis",
            "REQUESTING_REPAIR local-python-analysis",
            "RESULT",
        ],
    )
    assert_contains(
        result.stdout,
        [
            "malicious-router",
            "secrets-stealer",
            "Safe skills loaded: extract-claims, source-quality-check, write-structured-answer",
            "Temporary skills loaded: argument-clustering",
            "Requested skills: argument-clustering, local-python-analysis",
            "Rejected skills: malicious-router, secrets-stealer",
            "Repair requests: local-python-analysis",
            "Result category: repair_requested",
            "Exit code: 1",
        ],
    )

    assert {path.name for path in skills_dir.iterdir()} == durable_entries_before
    assert not (skills_dir / "argument-clustering").exists()
    assert not (skills_dir / "local-python-analysis").exists()

    log_path, data = read_single_run_log(runs_dir)
    assert "markdown_body" not in log_path.read_text(encoding="utf-8")
    artifact_root = runs_dir / "artifacts" / data["run_id"] / "skills"
    assert (artifact_root / "argument-clustering" / "SKILL.md").exists()
    assert (artifact_root / "local-python-analysis" / "SKILL.md").exists()

    assert data["result_category"] == "repair_requested"
    assert data["execution_summary"]["loaded_skills"] == [
        "extract-claims",
        "source-quality-check",
        "write-structured-answer",
        "argument-clustering",
    ]
    assert data["execution_summary"]["temporary_skills"] == [
        "argument-clustering",
        "local-python-analysis",
    ]
    assert data["execution_summary"]["requested_skills"] == [
        "argument-clustering",
        "local-python-analysis",
    ]
    assert data["execution_summary"]["repair_requested_skills"] == ["local-python-analysis"]
    assert data["execution_summary"]["rejected_skills"] == ["malicious-router", "secrets-stealer"]

    request_by_name = {request["desired_skill_name"]: request for request in data["skill_requests"]}
    assert request_by_name["argument-clustering"]["temporary_skill"]["validation_passed"]
    assert request_by_name["argument-clustering"]["temporary_skill"]["loaded"]
    assert not request_by_name["local-python-analysis"]["temporary_skill"]["validation_passed"]
    assert not request_by_name["local-python-analysis"]["temporary_skill"]["loaded"]

    repair = data["skill_repair_requests"][0]
    assert repair["skill_name"] == "local-python-analysis"
    assert repair["failed_capability"] == "run local python analysis"
    assert "non-scripted skills must be low risk" in repair["failure_reasons"]


def assert_contains(stdout: str, landmarks: list[str]) -> None:
    for landmark in landmarks:
        assert landmark in stdout


def assert_in_order(stdout: str, landmarks: list[str]) -> None:
    position = -1
    for landmark in landmarks:
        next_position = stdout.find(landmark, position + 1)
        assert next_position != -1, f"{landmark!r} was not found after offset {position}"
        position = next_position


def read_single_run_log(runs_dir: Path) -> tuple[Path, dict]:
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    return logs[0], json.loads(logs[0].read_text(encoding="utf-8"))
