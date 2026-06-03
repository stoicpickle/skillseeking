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
        "Do not mutate historical run logs, candidate ledgers, or input request resolution ledgers.",
        "Do not widen permissions.",
        "Do not add active governor steering.",
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
