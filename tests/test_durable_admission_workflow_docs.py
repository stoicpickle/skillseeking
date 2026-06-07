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


def test_stable_readiness_docs_preserve_advisory_boundary(repo_root: Path):
    docs = {
        "contracts": (repo_root / "docs" / "contracts" / "data-contracts.md").read_text(
            encoding="utf-8"
        ),
        "operating_roadmap": (repo_root / "docs" / "operating-roadmap.md").read_text(
            encoding="utf-8"
        ),
        "skill_lifecycle": (repo_root / "docs" / "skill-lifecycle.md").read_text(
            encoding="utf-8"
        ),
        "build_map": (repo_root / "docs" / "build-map.md").read_text(encoding="utf-8"),
    }

    for text in docs.values():
        assert "stable-readiness" in text

    required_contract_phrases = [
        "StableReadinessReport",
        "ready_for_stable_review",
        "needs_more_evidence",
        "already_stable",
        '"stable_review_authorized": false',
        '"stable_promotion_authorized": false',
        '"stable_routing_enabled": false',
        "does not mark the candidate stable",
        "enable stable routing",
        "mutate ledgers",
        "steer the governor",
    ]
    for phrase in required_contract_phrases:
        assert phrase in docs["contracts"]

    assert "advisory candidate-to-stable evidence report" in docs["operating_roadmap"]
    assert "does not mark a candidate stable" in docs["skill_lifecycle"]
    assert "without stable promotion or routing authority" in docs["build_map"]


def test_no_write_dependency_contract_docs_preserve_boundaries(repo_root: Path):
    docs = {
        "contracts": (repo_root / "docs" / "contracts" / "data-contracts.md").read_text(
            encoding="utf-8"
        ),
        "operating_roadmap": (repo_root / "docs" / "operating-roadmap.md").read_text(
            encoding="utf-8"
        ),
        "skill_lifecycle": (repo_root / "docs" / "skill-lifecycle.md").read_text(
            encoding="utf-8"
        ),
    }

    required_contract_phrases = [
        "write_plan.dependency_install_contract",
        'policy: "no_write_dependency_evidence_only"',
        "dependency_plan_digest",
        "runs/admission_dependency_evidence/<candidate_id>/<source_sha256>/dependency_plan.json",
        "dependency_evidence_manifest_hash_mismatch",
        "--dependency-approval-id",
        "install_supported: false",
        "install_attempted: false",
        "dependencies_installed: false",
        "it does not authorize installation",
        "mutate durable skills or ledgers",
        "enable routing",
        "steer the governor",
    ]
    for phrase in required_contract_phrases:
        assert phrase in docs["contracts"]

    boundary_phrase = (
        "Dependency evidence is not dependency installation, candidate-to-stable promotion, "
        "durable `skills/` admission, registry mutation, ledger mutation, stable routing, "
        "or governor steering."
    )
    assert boundary_phrase in docs["operating_roadmap"]
    assert (
        "Dependency evidence from `admit-candidate --dry-run` is no-write review evidence only"
        in docs["skill_lifecycle"]
    )
    assert "stable routing, dependency installation, registry mutation, ledger mutation" in docs[
        "skill_lifecycle"
    ]


def test_candidate_to_stable_rfc_preserves_design_only_boundary(repo_root: Path):
    rfc_path = (
        repo_root
        / "docs"
        / "plans"
        / "candidate-to-stable-and-durable-admission-rfc-2026-06-07.md"
    )
    rfc = rfc_path.read_text(encoding="utf-8")
    docs = {
        "build_map": (repo_root / "docs" / "build-map.md").read_text(encoding="utf-8"),
        "operating_roadmap": (repo_root / "docs" / "operating-roadmap.md").read_text(
            encoding="utf-8"
        ),
        "skill_lifecycle": (repo_root / "docs" / "skill-lifecycle.md").read_text(
            encoding="utf-8"
        ),
        "stable_routing": (repo_root / "docs" / "stable-routing-policy.md").read_text(
            encoding="utf-8"
        ),
    }

    required_rfc_phrases = [
        "Status: design only",
        "Candidate evidence",
        "Promotion approval",
        "Durable admission review",
        "Managed-prefix local use",
        "Stable routing",
        "Source hash",
        "Exact plan digest",
        "Latest evidence checkpoint hash",
        "Human approval ID",
        "Approval expiry",
        "Permission diff",
        "Dependency diff",
        "Rollback or deactivation evidence",
        "Stale source hash",
        "Expired approval",
        "Digest mismatch",
        "Permission widening",
        "Duplicate candidate",
        "Negative evidence present",
        "Missing checkpoint",
        "Symlink or path escape",
        "No durable generated-skill admission into `skills/`.",
        "No positive stable routing.",
        "No active governor steering.",
    ]
    for phrase in required_rfc_phrases:
        assert phrase in rfc

    for text in docs.values():
        assert "candidate-to-stable-and-durable-admission-rfc-2026-06-07.md" in text
    assert "It does not enable stable routing." in docs["stable_routing"]
    assert "not a write path" in docs["operating_roadmap"]


def test_active_governor_preflight_preserves_non_steering_boundary(repo_root: Path):
    design_path = (
        repo_root
        / "docs"
        / "plans"
        / "active-governor-preflight-design-2026-06-07.md"
    )
    design = design_path.read_text(encoding="utf-8")
    docs = {
        "build_map": (repo_root / "docs" / "build-map.md").read_text(encoding="utf-8"),
        "operating_roadmap": (repo_root / "docs" / "operating-roadmap.md").read_text(
            encoding="utf-8"
        ),
        "homeostatic_governor": (repo_root / "docs" / "homeostatic-governor.md").read_text(
            encoding="utf-8"
        ),
    }

    required_design_phrases = [
        "Status: design only",
        "Advisory",
        "Blocking",
        "Authorizing",
        "Current governor surfaces are advisory or trace-only",
        "must not steer routing",
        "Smallest Reversible Future Behavior",
        "checkpoint verification fails",
        "disabled by default",
        "governor_blocker_missing",
        "governor_authorized_without_approval",
        "override_digest_mismatch",
        "No code path starts consulting the governor for new authority.",
        "No routing, promotion, durable admission, permission, dependency, marketplace",
    ]
    for phrase in required_design_phrases:
        assert phrase in design

    for text in docs.values():
        assert "active-governor-preflight-design-2026-06-07.md" in text
    assert "does not implement active steering" in docs["homeostatic_governor"]
