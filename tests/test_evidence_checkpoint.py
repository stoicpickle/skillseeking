from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app
from app.evidence_checkpoint import load_evidence_checkpoint_ledger


def test_evidence_checkpoint_dry_run_writes_nothing(tmp_path):
    runs_dir = tmp_path / "runs"
    _write_core_evidence(runs_dir)
    before = _snapshot_tree(runs_dir)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["evidence-checkpoint", "--runs-dir", str(runs_dir), "--json"],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["outcome"] == "checkpoint_ready"
    assert data["dry_run"] is True
    assert data["checkpoint_ledger_mutated"] is False
    assert data["evidence_file_count"] == 3
    assert data["checkpoint_hash"]
    assert all(item["path"] != "evidence_checkpoints.json" for item in data["evidence_files"])
    _assert_no_mutation_flags(data)
    assert _snapshot_tree(runs_dir) == before
    assert not (runs_dir / "evidence_checkpoints.json").exists()


def test_evidence_checkpoint_non_dry_run_appends_and_verifies_without_rewriting_evidence(
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    _write_core_evidence(runs_dir)
    core_before = _snapshot_tree(runs_dir)
    runner = CliRunner()

    append = runner.invoke(
        app,
        [
            "evidence-checkpoint",
            "--runs-dir",
            str(runs_dir),
            "--no-dry-run",
            "--json",
        ],
    )
    verify = runner.invoke(
        app,
        ["evidence-checkpoint", "--runs-dir", str(runs_dir), "--verify", "--json"],
    )

    assert append.exit_code == 0
    appended = json.loads(append.stdout)
    assert appended["outcome"] == "checkpoint_appended"
    assert appended["dry_run"] is False
    assert appended["checkpoint_ledger_mutated"] is True
    assert appended["checkpoint_count"] == 1
    assert appended["checkpoints_verified"] == 1
    assert appended["previous_checkpoint_hash"] is None
    assert appended["checkpoint_hash"]
    assert _snapshot_tree_excluding_checkpoint(runs_dir) == core_before

    ledger = load_evidence_checkpoint_ledger(runs_dir)
    assert len(ledger.checkpoints) == 1
    assert ledger.checkpoints[0].checkpoint_hash == appended["checkpoint_hash"]

    assert verify.exit_code == 0
    verified = json.loads(verify.stdout)
    assert verified["outcome"] == "verified"
    assert verified["chain_valid"] is True
    assert verified["current_evidence_matches_latest"] is True
    assert verified["checkpoint_ledger_mutated"] is False
    _assert_no_mutation_flags(verified)
    assert _snapshot_tree_excluding_checkpoint(runs_dir) == core_before


def test_repeated_evidence_checkpoints_chain_history_without_including_checkpoint_ledger(
    tmp_path,
):
    runs_dir = tmp_path / "runs"
    _write_core_evidence(runs_dir)
    runner = CliRunner()

    first = runner.invoke(
        app,
        ["evidence-checkpoint", "--runs-dir", str(runs_dir), "--no-dry-run", "--json"],
    )
    assert first.exit_code == 0
    first_data = json.loads(first.stdout)
    (runs_dir / "admission_staging" / "candidate_1").mkdir(parents=True)
    (runs_dir / "admission_staging" / "candidate_1" / "SKILL.md").write_text(
        "# staged\n",
        encoding="utf-8",
    )
    core_before_second = _snapshot_tree_excluding_checkpoint(runs_dir)

    second = runner.invoke(
        app,
        ["evidence-checkpoint", "--runs-dir", str(runs_dir), "--no-dry-run", "--json"],
    )

    assert second.exit_code == 0
    second_data = json.loads(second.stdout)
    assert second_data["outcome"] == "checkpoint_appended"
    assert second_data["checkpoint_count"] == 2
    assert second_data["checkpoints_verified"] == 2
    assert second_data["previous_checkpoint_hash"] == first_data["checkpoint_hash"]
    assert second_data["evidence_file_count"] == 4
    assert all(
        item["path"] != "evidence_checkpoints.json"
        for item in second_data["evidence_files"]
    )

    ledger = load_evidence_checkpoint_ledger(runs_dir)
    assert len(ledger.checkpoints) == 2
    assert ledger.checkpoints[1].previous_checkpoint_hash == ledger.checkpoints[0].checkpoint_hash
    assert _snapshot_tree_excluding_checkpoint(runs_dir) == core_before_second


def test_evidence_checkpoint_verify_detects_current_evidence_tamper(tmp_path):
    runs_dir = tmp_path / "runs"
    _write_core_evidence(runs_dir)
    runner = CliRunner()
    append = runner.invoke(
        app,
        ["evidence-checkpoint", "--runs-dir", str(runs_dir), "--no-dry-run", "--json"],
    )
    assert append.exit_code == 0
    checkpoint_before = (runs_dir / "evidence_checkpoints.json").read_bytes()

    (runs_dir / "run_alpha.json").write_text(
        json.dumps({"run_id": "run_alpha", "result_category": "tampered"}) + "\n",
        encoding="utf-8",
    )
    verify = runner.invoke(
        app,
        ["evidence-checkpoint", "--runs-dir", str(runs_dir), "--verify", "--json"],
    )

    assert verify.exit_code == 0
    data = json.loads(verify.stdout)
    assert data["outcome"] == "blocked"
    assert data["chain_valid"] is True
    assert data["current_evidence_matches_latest"] is False
    assert "current_evidence_differs_from_latest_checkpoint" in data["blockers"]
    assert data["checkpoint_ledger_mutated"] is False
    assert (runs_dir / "evidence_checkpoints.json").read_bytes() == checkpoint_before


def test_evidence_checkpoint_verify_detects_checkpoint_ledger_tamper(tmp_path):
    runs_dir = tmp_path / "runs"
    _write_core_evidence(runs_dir)
    runner = CliRunner()
    append = runner.invoke(
        app,
        ["evidence-checkpoint", "--runs-dir", str(runs_dir), "--no-dry-run", "--json"],
    )
    assert append.exit_code == 0
    core_before = _snapshot_tree_excluding_checkpoint(runs_dir)
    ledger_path = runs_dir / "evidence_checkpoints.json"
    ledger_data = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger_data["checkpoints"][0]["evidence_files"][0]["sha256"] = "0" * 64
    ledger_path.write_text(json.dumps(ledger_data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    verify = runner.invoke(
        app,
        ["evidence-checkpoint", "--runs-dir", str(runs_dir), "--verify", "--json"],
    )

    assert verify.exit_code == 0
    data = json.loads(verify.stdout)
    assert data["outcome"] == "blocked"
    assert data["chain_valid"] is False
    assert any(
        blocker.startswith("checkpoint_hash_mismatch:")
        for blocker in data["blockers"]
    )
    assert data["checkpoint_ledger_mutated"] is False
    assert _snapshot_tree_excluding_checkpoint(runs_dir) == core_before


def _write_core_evidence(runs_dir: Path) -> None:
    runs_dir.mkdir(parents=True)
    (runs_dir / "run_alpha.json").write_text(
        json.dumps({"run_id": "run_alpha", "result_category": "success"}) + "\n",
        encoding="utf-8",
    )
    (runs_dir / "skill_candidate_ledger.json").write_text(
        json.dumps({"schema_version": 3, "entries": []}) + "\n",
        encoding="utf-8",
    )
    (runs_dir / "input_request_resolutions.json").write_text(
        json.dumps({"schema_version": 3, "resolutions": []}) + "\n",
        encoding="utf-8",
    )
    (runs_dir / "evals").mkdir()
    (runs_dir / "evals" / "eval_report.json").write_text(
        json.dumps({"ignored": True}) + "\n",
        encoding="utf-8",
    )


def _assert_no_mutation_flags(data: dict) -> None:
    assert data["run_logs_mutated"] is False
    assert data["candidate_ledger_mutated"] is False
    assert data["resolution_ledger_mutated"] is False
    assert data["durable_skills_mutated"] is False
    assert data["registry_mutated"] is False
    assert data["governor_steering_enabled"] is False


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def _snapshot_tree_excluding_checkpoint(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file() and item.name != "evidence_checkpoints.json"
    }
