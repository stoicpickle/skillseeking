from __future__ import annotations

from pathlib import Path


def test_durable_admission_workflow_design_preserves_advisory_boundary(repo_root: Path):
    plan = (
        repo_root
        / "docs"
        / "plans"
        / "durable-admission-workflow-design-2026-06-03.md"
    )
    text = plan.read_text(encoding="utf-8")

    required_phrases = [
        "Status: design/proof slice complete",
        "candidate -> review gate -> admission-plan dry run -> required proof -> human approval boundary",
        "approve_review",
        "does not copy, install, admit, promote to stable, widen permissions, or steer the governor",
        "Do not copy or install a durable skill in this slice.",
        "Do not mutate historical run logs, candidate ledgers, input request resolution ledgers, mismatched source snapshots, mismatched staging files, or durable skill files.",
        "Do not widen permissions.",
        "Do not add active governor steering.",
        "admit-candidate --dry-run mutation preview",
        "Dry-Run Write-Mode Contract",
        "Collision policy:",
        "Source snapshot retention and destination staging:",
        "--prepare-write-evidence",
        "--no-dry-run` is rejected",
    ]
    for phrase in required_phrases:
        assert phrase in text


def test_durable_admission_workflow_is_referenced_without_overclaiming(repo_root: Path):
    plan_name = "durable-admission-workflow-design-2026-06-03.md"
    build_map = (repo_root / "docs" / "build-map.md").read_text(encoding="utf-8")
    contracts = (repo_root / "docs" / "contracts" / "data-contracts.md").read_text(
        encoding="utf-8"
    )

    assert plan_name in build_map
    assert plan_name in contracts
    assert "not durable install/copy approval" in contracts
    assert "before any future install/copy work" in build_map


def test_shadow_managed_write_docs_preserve_boundaries(repo_root: Path):
    docs = {
        "build_map": (repo_root / "docs" / "build-map.md").read_text(encoding="utf-8"),
        "operating_roadmap": (repo_root / "docs" / "operating-roadmap.md").read_text(
            encoding="utf-8"
        ),
        "skill_lifecycle": (repo_root / "docs" / "skill-lifecycle.md").read_text(
            encoding="utf-8"
        ),
        "contracts": (repo_root / "docs" / "contracts" / "data-contracts.md").read_text(
            encoding="utf-8"
        ),
    }

    for text in docs.values():
        assert "shadow-managed-write" in text

    required_contract_phrases = [
        "## Shadow Managed Write",
        "ShadowManagedWriteReport",
        "managed_write_plan_digest",
        "approval_required",
        "ready_for_managed_prefix_write",
        "managed_prefix_write_applied",
        "already_applied",
        '"managed_prefix_mutated": true',
        '"profile_mutated": true',
        '"durable_skills_mutated": false',
        '"registry_mutated": false',
        '"candidate_ledger_mutated": false',
        '"resolution_ledger_mutated": false',
        '"run_logs_mutated": false',
        '"governor_steering_enabled": false',
        'stable_routing_policy: "stable_routing_unchanged"',
    ]
    for phrase in required_contract_phrases:
        assert phrase in docs["contracts"]

    assert "distinct from durable candidate copy/install into `skills/`" in docs["build_map"]
    assert "Operator sequence for `shadow-managed-write`" in docs["operating_roadmap"]
    assert "Managed-prefix activation is not candidate-to-stable promotion" in docs[
        "skill_lifecycle"
    ]
