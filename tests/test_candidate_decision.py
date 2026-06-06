from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.candidate_decision import build_candidate_decision_report
from app.cli import app
from app.models import SkillCandidateLedger
from app.skill_candidate_ledger import (
    approve_candidate_promotion,
    load_candidate_ledger,
    write_candidate_ledger,
)


def test_candidate_decision_asks_for_human_when_ready_for_review(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id = _create_candidate(runner, copied_seed_skills, runs_dir)
    _promote_with_successes(runs_dir, candidate_id, successful_uses=10)
    durable_before = _snapshot_tree(copied_seed_skills)
    runs_before = _snapshot_tree(runs_dir)

    report = build_candidate_decision_report(
        candidate_id,
        runs_dir=runs_dir,
        skills_dir=copied_seed_skills,
    )
    result = runner.invoke(
        app,
        [
            "candidate-decision",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--json",
        ],
    )
    text_result = runner.invoke(
        app,
        [
            "candidate-decision",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
        ],
    )

    assert report.decision == "ask_human"
    assert report.stable_readiness.ready_for_stable_review is True
    assert report.next_command == f"skill-agent stable-readiness {candidate_id}"
    assert "stable-readiness" in report.source_reports
    assert "skill-receipt" in report.source_reports
    _assert_no_mutation_flags(report.model_dump(mode="json"))

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["decision"] == "ask_human"
    assert data["stable_readiness"]["ready_for_stable_review"] is True
    assert data["stable_promotion_authorized"] is False
    assert data["stable_routing_enabled"] is False
    assert _why(data, "stable-readiness", "stable_readiness")["status"] == (
        "ready_for_stable_review"
    )
    _assert_no_mutation_flags(data)

    assert text_result.exit_code == 0
    assert "CANDIDATE_DECISION" in text_result.stdout
    assert "Decision: ask_human" in text_result.stdout
    assert "Stable routing enabled: false" in text_result.stdout
    assert "Next command: skill-agent stable-readiness" in text_result.stdout

    assert _snapshot_tree(copied_seed_skills) == durable_before
    assert _snapshot_tree(runs_dir) == runs_before


def test_candidate_decision_asks_when_human_promotion_is_missing(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id = _create_candidate(runner, copied_seed_skills, runs_dir)
    ledger = load_candidate_ledger(runs_dir)
    entry = ledger.entries[0]
    entry.status = "candidate"
    entry.successful_temporary_uses = 10
    entry.human_approval_required = True
    entry.promotion_approved_by = None
    entry.promotion_approved_at = None
    write_candidate_ledger(SkillCandidateLedger(entries=[entry]), runs_dir)

    result = runner.invoke(
        app,
        [
            "candidate-decision",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["decision"] == "ask_human"
    assert "candidate_promotion_evidence_missing" in data["blockers"]
    assert _why(data, "stable-readiness", "lifecycle")["status"] == "missing"
    assert data["approval_granted"] is False
    _assert_no_mutation_flags(data)


def test_candidate_decision_denies_negative_duplicate_evidence(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id = _create_candidate(runner, copied_seed_skills, runs_dir)
    ledger = load_candidate_ledger(runs_dir)
    entry = ledger.entries[0]
    entry.duplicate_of = "candidate_existing"
    entry.duplicate_evidence = ["same contract as candidate_existing"]
    write_candidate_ledger(SkillCandidateLedger(entries=[entry]), runs_dir)

    result = runner.invoke(
        app,
        [
            "candidate-decision",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["decision"] == "deny"
    assert "candidate_duplicate" in data["blockers"]
    assert _why(data, "negative-evidence", "negative_evidence")["status"] == "present"
    assert data["install_authorized"] is False
    _assert_no_mutation_flags(data)


def test_candidate_decision_defers_dependency_install_unsupported(
    copied_seed_skills,
    tmp_path,
):
    runner = CliRunner()
    runs_dir = tmp_path / "runs"
    candidate_id = _create_candidate(runner, copied_seed_skills, runs_dir)
    _promote_with_successes(runs_dir, candidate_id, successful_uses=10)
    ledger = load_candidate_ledger(runs_dir)
    _add_exact_dependency_realization(runs_dir, ledger.entries[0].skill_name)

    result = runner.invoke(
        app,
        [
            "candidate-decision",
            candidate_id,
            "--runs-dir",
            str(runs_dir),
            "--skills-dir",
            str(copied_seed_skills),
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["decision"] == "defer"
    assert "dependency_install_unsupported" in data["blockers"]
    dependency_item = _why(data, "skill-receipt", "receipt:containment")
    assert dependency_item["status"] == "blocked"
    assert "dependency_install_unsupported" in dependency_item["blockers"]
    assert data["permission_widening_authorized"] is False
    _assert_no_mutation_flags(data)


def _create_candidate(
    runner: CliRunner,
    skills_dir: Path,
    runs_dir: Path,
) -> str:
    result = runner.invoke(
        app,
        [
            "run",
            "Cluster arguments from these sources.",
            "--skills-dir",
            str(skills_dir),
            "--runs-dir",
            str(runs_dir),
        ],
    )
    assert result.exit_code == 0
    return load_candidate_ledger(runs_dir).entries[0].candidate_id


def _promote_with_successes(
    runs_dir: Path,
    candidate_id: str,
    *,
    successful_uses: int,
) -> None:
    approve_candidate_promotion(
        runs_dir,
        candidate_id,
        reviewer="Ada",
        notes="Validated candidate evidence before stable review.",
    )
    ledger = load_candidate_ledger(runs_dir)
    ledger.entries[0].successful_temporary_uses = successful_uses
    ledger.entries[0].validation_pass_count = max(
        ledger.entries[0].validation_pass_count,
        successful_uses,
    )
    write_candidate_ledger(ledger, runs_dir)


def _add_exact_dependency_realization(runs_dir: Path, skill_name: str) -> None:
    skill_path = next(runs_dir.rglob(f"{skill_name}/SKILL.md"))
    text = skill_path.read_text(encoding="utf-8")
    text = text.replace(
        "validation:\n",
        (
            "dependencies:\n"
            "  - example-package==1.0.0\n"
            "dependency_realization:\n"
            "  - name: example-package\n"
            "    version: 1.0.0\n"
            "    sha256: "
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
            "validation:\n"
        ),
        1,
    )
    skill_path.write_text(text, encoding="utf-8")


def _why(data: dict, source_report: str, signal: str) -> dict:
    matches = [
        item
        for item in data["why"]
        if item["source_report"] == source_report and item["signal"] == signal
    ]
    assert len(matches) == 1
    return matches[0]


def _assert_no_mutation_flags(data: dict) -> None:
    assert data["run_logs_mutated"] is False
    assert data["candidate_ledger_mutated"] is False
    assert data["resolution_ledger_mutated"] is False
    assert data["checkpoint_ledger_mutated"] is False
    assert data["durable_skills_mutated"] is False
    assert data["registry_mutated"] is False
    assert data["governor_steering_enabled"] is False


def _snapshot_tree(path: Path) -> dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }
