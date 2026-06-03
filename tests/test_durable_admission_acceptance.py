from __future__ import annotations

import hashlib
import json
from pathlib import Path
from shutil import copytree

from typer.testing import CliRunner

from app.cli import app
from app.input_resolution_ledger import load_input_request_resolution_ledger


def test_acceptance_write_plan_verifies_destination_snapshot_hash_and_no_writes(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path, _ = _prepare_reviewed_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    result = _admit_candidate_json(runner, candidate_id, runs_dir, copied_seed_skills)

    assert result["outcome"] == "ready_for_mutation_preview"
    assert result["ready_for_mutation_preview"] is True
    assert result["source_sha256"] == _sha256(source_path)
    assert result["target_skill_path"] == str(
        copied_seed_skills / "argument-clustering" / "SKILL.md"
    )
    assert result["write_plan"]["operation"] == "copy_new_skill"
    assert result["write_plan"]["source_skill_path"] == str(source_path)
    assert result["write_plan"]["source_sha256"] == result["source_sha256"]
    assert result["write_plan"]["target_skill_path"] == result["target_skill_path"]
    assert result["write_plan"]["snapshot_skill_path"] == str(
        runs_dir / "admission_snapshots" / candidate_id / result["source_sha256"] / "SKILL.md"
    )
    assert result["write_plan"]["snapshot_sha256"] == result["source_sha256"]
    assert result["write_plan"]["blockers"] == []
    _assert_no_admission_mutation(result)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert not (runs_dir / "admission_snapshots").exists()

    write_result = runner.invoke(
        app,
        [
            "admit-candidate",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--no-dry-run",
        ],
    )

    assert write_result.exit_code == 1
    assert "durable admission mutation is not implemented" in write_result.stdout
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_acceptance_source_drift_changes_hash_and_snapshot_path_without_writing(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path, _ = _prepare_reviewed_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )

    first = _admit_candidate_json(runner, candidate_id, runs_dir, copied_seed_skills)
    source_path.write_text(
        source_path.read_text(encoding="utf-8") + "\nAdditional drift evidence.\n",
        encoding="utf-8",
    )
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    second = _admit_candidate_json(runner, candidate_id, runs_dir, copied_seed_skills)

    assert second["source_sha256"] == _sha256(source_path)
    assert second["source_sha256"] != first["source_sha256"]
    assert second["write_plan"]["snapshot_skill_path"] == str(
        runs_dir / "admission_snapshots" / candidate_id / second["source_sha256"] / "SKILL.md"
    )
    assert (
        second["write_plan"]["snapshot_skill_path"]
        != first["write_plan"]["snapshot_skill_path"]
    )
    assert second["write_plan"]["operation"] == "copy_new_skill"
    _assert_no_admission_mutation(second)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert not (runs_dir / "admission_snapshots").exists()


def test_acceptance_collision_approval_gates_replacement_preview_without_writing(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    no_review_skills = tmp_path / "skills-no-review"
    reviewed_skills = tmp_path / "skills-reviewed"
    copytree(copied_seed_skills, no_review_skills)
    copytree(copied_seed_skills, reviewed_skills)
    runs_dir = tmp_path / "runs-no-review"
    candidate_id, source_path = _prepare_promoted_candidate(
        runner,
        no_review_skills,
        runs_dir,
    )
    copytree(source_path.parent, no_review_skills / "argument-clustering")
    durable_before_review = _snapshot_tree(no_review_skills)
    runs_before_review = _snapshot_tree(runs_dir)

    no_review = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        no_review_skills,
        "--collision-policy",
        "allow_replace_with_approval",
    )

    assert no_review["write_plan"]["operation"] == "blocked"
    assert no_review["write_plan"]["replacement_approved"] is False
    assert "durable_review_resolution_missing" in no_review["write_plan"]["blockers"]
    assert _snapshot_tree(no_review_skills) == durable_before_review
    assert _snapshot_tree(runs_dir) == runs_before_review

    reviewed_runs_dir = tmp_path / "runs-reviewed"
    reviewed_candidate_id, reviewed_source_path, _ = _prepare_reviewed_candidate(
        runner,
        reviewed_skills,
        reviewed_runs_dir,
    )
    copytree(reviewed_source_path.parent, reviewed_skills / "argument-clustering")
    durable_before_preview = _snapshot_tree(reviewed_skills)
    runs_before_preview = _snapshot_tree(reviewed_runs_dir)
    default_policy = _admit_candidate_json(
        runner,
        reviewed_candidate_id,
        reviewed_runs_dir,
        reviewed_skills,
    )
    replacement = _admit_candidate_json(
        runner,
        reviewed_candidate_id,
        reviewed_runs_dir,
        reviewed_skills,
        "--collision-policy",
        "allow_replace_with_approval",
    )

    assert default_policy["write_plan"]["operation"] == "blocked"
    assert "durable_name_collision" in default_policy["write_plan"]["blockers"]
    assert replacement["ready_for_mutation_preview"] is True
    assert replacement["write_plan"]["operation"] == "replace_existing_skill"
    assert replacement["write_plan"]["replacement_approved"] is True
    assert replacement["write_plan"]["blockers"] == []
    _assert_no_admission_mutation(replacement)
    assert _snapshot_tree(reviewed_skills) == durable_before_preview
    assert _snapshot_tree(reviewed_runs_dir) == runs_before_preview
    assert not (reviewed_runs_dir / "admission_snapshots").exists()


def test_acceptance_permission_approval_clears_only_permission_gate_without_writing(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id, source_path, permission_approval_id = _prepare_reviewed_candidate(
        runner,
        copied_seed_skills,
        runs_dir,
    )
    updated_source = source_path.read_text(encoding="utf-8").replace(
        "network: false",
        "network: true",
        1,
    )
    source_path.write_text(
        updated_source,
        encoding="utf-8",
    )
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    without_permission = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
    )
    with_permission = _admit_candidate_json(
        runner,
        candidate_id,
        runs_dir,
        copied_seed_skills,
        "--permission-approval-id",
        permission_approval_id,
    )

    assert without_permission["write_plan"]["operation"] == "blocked"
    assert (
        "permission_widening_approval_missing"
        in without_permission["write_plan"]["blockers"]
    )
    assert without_permission["write_plan"]["permission_widening_approved"] is False
    assert with_permission["write_plan"]["operation"] == "blocked"
    assert with_permission["write_plan"]["permission_widening_approved"] is True
    assert (
        "permission_widening_approval_missing"
        not in with_permission["write_plan"]["blockers"]
    )
    assert "source_permission_widening" in with_permission["write_plan"]["blockers"]
    _assert_no_admission_mutation(with_permission)
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before
    assert not (runs_dir / "admission_snapshots").exists()


def _prepare_reviewed_candidate(
    runner: CliRunner,
    skills_dir: Path,
    runs_dir: Path,
) -> tuple[str, Path, str]:
    candidate_id, source_path = _prepare_promoted_candidate(runner, skills_dir, runs_dir)
    resolution_id = _approve_admission_review(runner, candidate_id, runs_dir, skills_dir)
    return candidate_id, source_path, resolution_id


def _prepare_promoted_candidate(
    runner: CliRunner,
    skills_dir: Path,
    runs_dir: Path,
) -> tuple[str, Path]:
    run_result = runner.invoke(
        app,
        [
            "run",
            "Cluster arguments from these sources.",
            "--temporary-skills",
            "--skills-dir",
            str(skills_dir),
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert run_result.exit_code == 0
    run_log = _single_run_log(runs_dir)
    source_path = Path(
        json.loads(run_log.read_text(encoding="utf-8"))["skill_requests"][0]["temporary_skill"][
            "skill_path"
        ]
    )
    candidates_result = runner.invoke(
        app,
        ["candidates", "--runs-dir", str(runs_dir), "--json"],
    )
    assert candidates_result.exit_code == 0
    candidate_id = json.loads(candidates_result.stdout)["entries"][0]["candidate_id"]
    promote_result = runner.invoke(
        app,
        [
            "promote-candidate",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--reviewer",
            "Ada",
            "--notes",
            "Reviewed temporary evidence.",
            "--json",
        ],
    )
    assert promote_result.exit_code == 0
    return candidate_id, source_path


def _approve_admission_review(
    runner: CliRunner,
    candidate_id: str,
    runs_dir: Path,
    skills_dir: Path,
) -> str:
    admission_result = runner.invoke(
        app,
        [
            "admission-plan",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(skills_dir),
            "--json",
        ],
    )
    assert admission_result.exit_code == 0
    admission = json.loads(admission_result.stdout)
    assert admission["input_request"]["kind"] == "durable_admission_review"
    resolve_result = runner.invoke(
        app,
        [
            "resolve-input-request",
            admission["input_request"]["id"],
            "--runs-dir",
            str(runs_dir),
            "--decision",
            "approve_review",
            "--reviewer",
            "Ada",
            "--notes",
            "Reviewed durable admission evidence.",
            "--no-dry-run",
            "--json",
        ],
    )
    assert resolve_result.exit_code == 0
    ledger = load_input_request_resolution_ledger(runs_dir)
    return ledger.resolutions[-1].id


def _admit_candidate_json(
    runner: CliRunner,
    candidate_id: str,
    runs_dir: Path,
    skills_dir: Path,
    *extra_args: str,
) -> dict:
    result = runner.invoke(
        app,
        [
            "admit-candidate",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(skills_dir),
            *extra_args,
            "--json",
        ],
    )
    assert result.exit_code == 0
    return json.loads(result.stdout)


def _assert_no_admission_mutation(report: dict) -> None:
    for key in [
        "mutation_supported",
        "durable_skill_installed",
        "ledger_mutated",
        "registry_mutated",
        "resolution_ledger_mutated",
        "governor_steering_enabled",
    ]:
        assert report[key] is False
    for key in [
        "durable_skill_installed",
        "ledger_mutated",
        "registry_mutated",
        "resolution_ledger_mutated",
        "source_snapshot_created",
        "governor_steering_enabled",
    ]:
        assert report["write_plan"][key] is False


def _single_run_log(runs_dir: Path) -> Path:
    logs = list(runs_dir.glob("run_*.json"))
    assert len(logs) == 1
    return logs[0]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
