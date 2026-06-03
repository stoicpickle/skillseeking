from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app
from app.skill_candidate_ledger import load_candidate_ledger


def test_lifecycle_admission_cli_path_is_ready_for_iteration(copied_seed_skills, tmp_path):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    durable_before = _snapshot_tree(copied_seed_skills)

    run_result = runner.invoke(
        app,
        [
            "run",
            "Cluster arguments from these sources.",
            "--temporary-skills",
            "--skills-dir",
            str(copied_seed_skills),
            "--runs-dir",
            str(runs_dir),
        ],
    )

    assert run_result.exit_code == 0
    run_log = next(runs_dir.rglob("run_*.json"))
    run_data = json.loads(run_log.read_text(encoding="utf-8"))
    source_path = Path(run_data["skill_requests"][0]["temporary_skill"]["skill_path"])
    assert source_path.exists()
    assert source_path.name == "SKILL.md"
    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert not (copied_seed_skills / "argument-clustering").exists()

    candidates_result = runner.invoke(
        app,
        ["candidates", "--runs-dir", str(runs_dir), "--json"],
    )

    assert candidates_result.exit_code == 0
    candidates = json.loads(candidates_result.stdout)
    assert candidates["candidate_count"] == 1
    assert candidates["auto_promotion_enabled"] is False
    assert candidates["review_queue_counts"] == {"promotion_ready": 1}
    entry = candidates["entries"][0]
    assert entry["status"] == "temporary"
    assert entry["review_queues"] == ["promotion_ready"]
    candidate_id = entry["candidate_id"]

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
            "Reviewed temporary evidence for local testing readiness.",
            "--json",
        ],
    )

    assert promote_result.exit_code == 0
    promoted = json.loads(promote_result.stdout)
    assert promoted["status"] == "candidate"
    assert promoted["promotion_approved_by"] == "Ada"
    assert promoted["human_approval_required"] is False
    assert load_candidate_ledger(runs_dir).entries[0].status == "candidate"
    assert _snapshot_tree(copied_seed_skills) == durable_before

    admission_result = runner.invoke(
        app,
        [
            "admission-plan",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--json",
        ],
    )

    assert admission_result.exit_code == 0
    admission = json.loads(admission_result.stdout)
    assert admission["outcome"] == "ready_for_durable_review"
    assert admission["ready_for_durable_review"] is True
    assert admission["blockers"] == []
    assert admission["dry_run"] is True
    assert admission["auto_promotion_enabled"] is False
    assert admission["durable_skill_installed"] is False
    assert admission["ledger_mutated"] is False
    assert admission["registry_mutated"] is False
    assert admission["governor_steering_enabled"] is False
    assert _snapshot_tree(copied_seed_skills) == durable_before


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
