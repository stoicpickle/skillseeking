from __future__ import annotations

import re
import tomllib
from pathlib import Path


def test_v1_release_docs_exist_and_are_non_empty(repo_root: Path):
    required_paths = [
        repo_root / "README.md",
        repo_root / "CHANGELOG.md",
        repo_root / "docs" / "v1-release-notes.md",
        repo_root / "docs" / "v1-release-contract.md",
        repo_root / "docs" / "v1-release-tasking.md",
        repo_root / "docs" / "launch-proof-2026-06-07.md",
        repo_root / "docs" / "launch-demo-transcript.md",
        repo_root / "CONTRIBUTING.md",
        repo_root / "docs" / "operator-summary-review-pack.md",
        repo_root / "docs" / "design-partner-feedback-log.md",
        repo_root
        / "docs"
        / "plans"
        / "candidate-to-stable-and-durable-admission-rfc-2026-06-07.md",
        repo_root
        / "docs"
        / "plans"
        / "active-governor-preflight-design-2026-06-07.md",
        repo_root / "docs" / "design-partner-feedback.md",
        repo_root / "docs" / "governance-monetization-principles.md",
    ]

    for path in required_paths:
        assert path.exists(), f"missing release doc: {path}"
        assert path.read_text(encoding="utf-8").strip(), f"empty release doc: {path}"


def test_readme_positions_v1_as_local_cli_with_boundaries(repo_root: Path):
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    lower = readme.lower()
    opening = lower[:500]

    assert "v1.0 local cli release" in lower
    assert "governed capability acquisition" in lower
    assert "version `1.0.0` is the local cli compatibility stamp" in lower
    assert "git release tag is `v1.0.0`" in lower
    assert "not a production agent framework" in lower
    assert "not a hosted platform" in lower
    assert "not production-safe" in lower
    assert "not stamped or tagged as `1.0.0` yet" not in lower
    assert "cli-first research prototype" not in opening
    assert "`--scripted-skills` is trusted-local only" in readme
    assert "does not provide a sandbox" in readme
    assert "docs/v1-release-notes.md" in readme
    assert "docs/launch-demo-transcript.md" in readme
    assert "CONTRIBUTING.md" in readme
    assert "docs/operator-summary-review-pack.md" in readme
    assert "new-authority-readiness" in readme
    assert "not ready to enable new authority" in readme
    assert "feedback-session-template" in readme
    assert "feedback-session-append" in readme
    assert "defaults to `--dry-run`" in readme
    assert "updates objective session/yes-no rollup counters" in readme
    assert "docs/design-partner-feedback.md" in readme
    assert "docs/governance-monetization-principles.md" in readme
    assert "CHANGELOG.md" in readme


def test_release_notes_are_honest_about_current_v1_state(repo_root: Path):
    notes = (repo_root / "docs" / "v1-release-notes.md").read_text(
        encoding="utf-8"
    )
    lower = notes.lower()

    assert "status: v1.0 local cli release" in lower
    assert "package version: `1.0.0`" in lower
    assert "git release tag: `v1.0.0`" in lower
    assert "released for local cli use" in lower
    assert "governed capability acquisition" in lower
    assert "stable routing is deferred for v1" in lower
    assert "not a true sandbox" in lower
    assert "not a hosted service" in lower
    assert "not provide an external skill marketplace" in lower
    assert "not stamped or tagged as `1.0.0` yet" not in lower
    assert "no `1.0.0` version stamp, tag, or published release" not in lower
    assert "release gate passed on the commit tagged `v1.0.0`" in lower


def test_changelog_and_version_are_stamped_for_1_0_0(repo_root: Path):
    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    pyproject = tomllib.loads(
        (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    project_version = pyproject["project"]["version"]

    assert "## Unreleased" in changelog
    assert "## [1.0.0] - 2026-06-06" in changelog
    assert "local v1 cli release" in changelog.lower()
    assert "`pyproject.toml` is stamped as `1.0.0`" in changelog
    assert "the matching git release tag is `v1.0.0`" in changelog.lower()
    assert project_version == "1.0.0"
    assert (
        pyproject["project"]["description"]
        == "Local CLI for governed capability-gap detection, skill requests, and evidence-controlled skill review."
    )
    released_1_0_0 = re.search(r"^## \[?1\.0\.0\]?", changelog, re.MULTILINE)
    assert released_1_0_0 is not None


def test_release_contract_marks_final_v1_state_without_overclaiming(repo_root: Path):
    contract = (repo_root / "docs" / "v1-release-contract.md").read_text(
        encoding="utf-8"
    )
    lower = contract.lower()

    assert "status: v1.0 local cli release" in lower
    assert "changelog.md" in lower
    assert "docs/v1-release-notes.md" in lower
    assert "set to `1.0.0`" in lower
    assert "git release tag is `v1.0.0`" in lower
    assert "stable routing positive coverage remains intentionally out of scope" in lower
    assert "- release notes and changelog;" not in lower
    assert "production-safety claim" in lower


def test_v1_tasking_marks_final_release_without_stale_candidate_status(repo_root: Path):
    tasking = (repo_root / "docs" / "v1-release-tasking.md").read_text(
        encoding="utf-8"
    )
    lower = tasking.lower()

    assert "status: complete for v1.0 local cli release" in lower
    assert "v1.0 local cli release for governed capability acquisition" in lower
    assert "local v1 cli release candidate for governed capability acquisition" not in lower


def test_launch_proof_records_private_local_release_boundaries(repo_root: Path):
    proof = (repo_root / "docs" / "launch-proof-2026-06-07.md").read_text(
        encoding="utf-8"
    )
    lower = proof.lower()

    assert "status: private/local v1.0 release proof" in lower
    assert "e006ca815a5eba2e33b130386d5106fa5d7fb191" in proof
    assert "refs/tags/v1.0.0^{}" in proof
    assert "full pytest: `279 passed`" in lower
    assert "tag-required v1 smoke: passed" in lower
    assert "v1 release eval inside v1 smoke: `11/11`" in lower
    assert "coderabbit scoped review" in lower
    assert "public remote/tag proof is not included here" in lower
    assert "no hosted service proof" in lower
    assert "no true sandbox proof" in lower
    assert "no positive stable-routing proof" in lower


def test_ci_workflow_runs_visible_v1_launch_gate(repo_root: Path):
    workflow = (repo_root / ".github" / "workflows" / "tests.yml").read_text(
        encoding="utf-8"
    )

    assert "git diff --check" in workflow
    assert "skill-agent eval --suite evals/capgap_smoke.jsonl" in workflow
    assert "skill-agent eval --suite evals/skill_lifecycle_v0.jsonl" in workflow
    assert "skill-agent eval --suite evals/agent_diagnostic_v0.jsonl" in workflow
    assert "skill-agent eval --suite evals/v1_release.jsonl" in workflow
    assert "python -m compileall -q app" in workflow
    assert "bash scripts/v1_smoke.sh" in workflow
    assert "REQUIRE_V1_TAG=1" not in workflow


def test_launch_demo_transcript_preserves_public_boundaries(repo_root: Path):
    transcript = (repo_root / "docs" / "launch-demo-transcript.md").read_text(
        encoding="utf-8"
    )
    lower = transcript.lower()

    assert "local public-dev-preview demo" in lower
    assert "human review remains in the path" in lower
    assert "durable `skills/` admission remains disabled" in lower
    assert "stable routing remains disabled" in lower
    assert "not a hosted service" in lower
    assert "not production-safe" in lower
    assert "not a sandbox" in lower
    assert "does not provide a sandbox" in lower
    assert "does not autonomously promote candidates" in lower
    assert "does not enable positive stable routing" in lower


def test_public_preview_strategy_docs_match_source_and_scope(repo_root: Path):
    contributing = (repo_root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    review_pack = (repo_root / "docs" / "operator-summary-review-pack.md").read_text(
        encoding="utf-8"
    )
    design_partners = (repo_root / "docs" / "design-partner-feedback.md").read_text(
        encoding="utf-8"
    )
    feedback_log = (repo_root / "docs" / "design-partner-feedback-log.md").read_text(
        encoding="utf-8"
    )
    data_contracts = (repo_root / "docs" / "contracts" / "data-contracts.md").read_text(
        encoding="utf-8"
    )
    monetization = (
        repo_root / "docs" / "governance-monetization-principles.md"
    ).read_text(encoding="utf-8")
    roadmap = (repo_root / "docs" / "roadmap.md").read_text(encoding="utf-8")
    product_brief = (repo_root / "docs" / "product-brief.md").read_text(
        encoding="utf-8"
    )
    product_manager = (repo_root / "docs" / "product-manager.md").read_text(
        encoding="utf-8"
    )
    candidate_stable_rfc = (
        repo_root
        / "docs"
        / "plans"
        / "candidate-to-stable-and-durable-admission-rfc-2026-06-07.md"
    ).read_text(encoding="utf-8")
    governor_preflight = (
        repo_root
        / "docs"
        / "plans"
        / "active-governor-preflight-design-2026-06-07.md"
    ).read_text(encoding="utf-8")

    assert "MIT License" in (repo_root / "LICENSE").read_text(encoding="utf-8")
    assert "open source under the MIT License" in contributing
    assert "local CLI public-dev-preview workbench" in contributing
    assert "not a hosted product" in contributing
    assert "durable generated-skill admission into `skills/`" in contributing
    assert "skill-agent feedback-session-template" in contributing
    assert "does not append to the log" in contributing
    assert "update rollups" in contributing
    assert "grant new authority" in contributing
    assert "skill-agent feedback-session-append --dry-run" in contributing
    assert "updates only the selected feedback log" in contributing
    assert "Repeated setup or evidence-surface friction rollups remain manual" in " ".join(
        contributing.split()
    )

    assert "operator-summary" in review_pack
    assert "OPERATOR_DECISIONS" in review_pack
    assert "Candidate evidence means" in review_pack
    assert "not admission" in review_pack
    assert "No active governor steering" in review_pack

    assert "3 to 5 design partners" in design_partners
    assert "Operator Summary Review Pack" in design_partners
    assert "Design Partner Feedback Log" in design_partners
    assert "Operator-summary decision clarity" in design_partners
    assert "New-authority readiness confusion" in design_partners
    assert "setup friction" in design_partners.lower()
    assert "candidate-decision confusion" in design_partners.lower()
    assert "stable-routing deferral confusion" in design_partners.lower()
    assert "skill-agent feedback-session-template" in design_partners
    assert "skill-agent feedback-session-append --dry-run" in design_partners
    assert "feedback-session-append --no-dry-run" in design_partners
    assert "updates only the selected feedback log" in design_partners
    assert "objective rollup counters" in design_partners
    assert "grant authority" in design_partners
    assert "does not update repeated-friction synthesis rows" in design_partners
    assert "Status: active public-dev-preview evidence log" in feedback_log
    assert "Completed partner sessions | 0" in feedback_log
    assert "Next `OPERATOR_DECISIONS` action identified unaided" in feedback_log
    assert "`ready_to_enable_new_authority=false` understood" in feedback_log
    assert "Do not add durable generated-skill admission" in feedback_log
    assert "skill-agent feedback-session-template --json" in data_contracts
    assert "skill-agent feedback-session-append --json" in data_contracts
    assert "template_only_read_only" in data_contracts
    assert "does not append to the feedback log" in data_contracts
    assert "Every `mutation_boundary` flag must remain `false`" in data_contracts
    assert "defaults to dry-run preview" in data_contracts
    assert "only `mutation_boundary.feedback_log_appended`" in " ".join(
        data_contracts.split()
    )
    assert "repeated_friction_rollups_updated` remains `false`" in data_contracts

    assert "Do not lead with a public skill marketplace" in monetization
    assert "governance, evidence, approvals, auditability, and" in monetization
    assert "not current release claims" in monetization

    assert "MIT-licensed open source for the local CLI dev-preview" in roadmap
    assert "marketplace remains deferred" in roadmap.lower()
    assert "Go-To-Market Boundary" in product_brief
    assert "Public Preview Strategy Boundary" in product_manager
    assert "Operator Summary Review Pack" in product_manager
    assert "Design Partner Feedback Log" in product_manager
    assert "Candidate-To-Stable And Durable Admission RFC" in product_manager
    assert "Active Governor Preflight Design" in product_manager
    assert "skill-agent new-authority-readiness" in product_manager
    assert "ready_to_enable_new_authority=false" in product_manager
    assert "Status: design only" in candidate_stable_rfc
    assert "No positive stable routing." in candidate_stable_rfc
    assert "No active governor steering." in candidate_stable_rfc
    assert "Status: design only" in governor_preflight
    assert "No code path starts consulting the governor for new authority." in governor_preflight


def test_public_docs_do_not_add_positive_authority_claims(repo_root: Path):
    docs = [
        repo_root / "README.md",
        repo_root / "CONTRIBUTING.md",
        repo_root / "docs" / "operator-summary-review-pack.md",
        repo_root / "docs" / "contracts" / "data-contracts.md",
        repo_root
        / "docs"
        / "plans"
        / "candidate-to-stable-and-durable-admission-rfc-2026-06-07.md",
        repo_root
        / "docs"
        / "plans"
        / "active-governor-preflight-design-2026-06-07.md",
        repo_root / "docs" / "v1-release-notes.md",
        repo_root / "docs" / "v1-release-contract.md",
        repo_root / "docs" / "demo-suite.md",
        repo_root / "docs" / "launch-demo-transcript.md",
        repo_root / "docs" / "design-partner-feedback.md",
        repo_root / "docs" / "governance-monetization-principles.md",
        repo_root / "docs" / "product-brief.md",
        repo_root / "docs" / "product-manager.md",
    ]
    forbidden = [
        "production-ready self-improving agent framework",
        "production-grade public agent framework",
        "is a production-safe framework",
        "production-safe hosted framework",
        "hosted platform launch",
        "hosted service launch",
        "provides a true sandbox",
        "is a true sandbox",
        "stable routing enabled: yes",
        "stable routing is enabled",
        "automatically promotes",
        "autonomously promotes",
        "external skill marketplace support is included",
        "durable generated-skill admission is enabled",
    ]

    for path in docs:
        text = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden:
            assert phrase not in text, f"{path} contains positive authority claim: {phrase}"
