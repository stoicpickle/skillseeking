from __future__ import annotations

import re
import tomllib
from pathlib import Path


PUBLIC_FORBIDDEN = [
    "/" + "Users" + "/" + "russ",
    "skillseeking" + "-private",
    "private" + "/" + "codex",
    "stoicpickle" + "/" + "skillseeking" + "-private",
]


def test_v1_release_docs_exist_and_are_non_empty(repo_root: Path):
    required_paths = [
        repo_root / "README.md",
        repo_root / "CHANGELOG.md",
        repo_root / "CONTRIBUTING.md",
        repo_root / "docs" / "cli-reference.md",
        repo_root / "docs" / "start-here.md",
        repo_root / "docs" / "architecture.md",
        repo_root / "docs" / "skill-lifecycle.md",
        repo_root / "docs" / "safety-model.md",
        repo_root / "docs" / "evaluation-plan.md",
        repo_root / "docs" / "demo-suite.md",
        repo_root / "docs" / "contracts" / "data-contracts.md",
        repo_root / "docs" / "operator-summary-review-pack.md",
        repo_root / "docs" / "reviewer-feedback.md",
        repo_root / "docs" / "reviewer-feedback-log.md",
        repo_root / "docs" / "v1-release-contract.md",
        repo_root / "docs" / "v1-release-notes.md",
        repo_root / "docs" / "launch-demo-transcript.md",
        repo_root / "docs" / "launch-proof-2026-06-07.md",
        repo_root / "docs" / "internal" / "v1-release-tasking.md",
        repo_root / "docs" / "internal" / "general-public-readiness-tasking-2026-06-07.md",
        repo_root / "docs" / "internal" / "governance-and-commercial-boundaries.md",
        repo_root
        / "docs"
        / "internal"
        / "plans"
        / "candidate-to-stable-and-durable-admission-rfc-2026-06-07.md",
        repo_root
        / "docs"
        / "internal"
        / "plans"
        / "active-governor-preflight-design-2026-06-07.md",
    ]

    for path in required_paths:
        assert path.exists(), f"missing release doc: {path}"
        assert path.read_text(encoding="utf-8").strip(), f"empty release doc: {path}"


def test_public_surface_scrubs_local_private_references(repo_root: Path):
    paths = [
        repo_root / "README.md",
        repo_root / "AGENTS.md",
        repo_root / "CONTRIBUTING.md",
        *sorted((repo_root / "docs").rglob("*.md")),
        *sorted((repo_root / "app").rglob("*.py")),
        *sorted((repo_root / "scripts").rglob("*.py")),
        *sorted((repo_root / "scripts").rglob("*.sh")),
        *sorted((repo_root / "tests").rglob("*.py")),
    ]

    for path in paths:
        text = path.read_text(encoding="utf-8")
        for needle in PUBLIC_FORBIDDEN:
            assert needle not in text, f"{path} leaked {needle}"


def test_readme_is_curated_for_fast_review(repo_root: Path):
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    lower = readme.lower()
    line_count = len(readme.splitlines())

    assert line_count <= 170
    assert "what to inspect first" in lower[:1_500]
    assert "blocked -> requested_skill -> validated -> loaded -> continued" in lower
    assert "v1.0 local cli release" in lower
    assert "version `1.0.0` is the local cli compatibility stamp" in lower
    assert "git release tag is `v1.0.0`" in lower
    assert "not a production agent framework" in lower
    assert "not a hosted platform" in lower
    assert "not production-safe" in lower
    assert "docs/cli-reference.md" in readme
    assert "docs/internal/" in readme
    assert "docs/internal/dev-log.md" not in readme
    assert "docs/internal/general-public-readiness-tasking" not in readme
    assert "governance " + "monetization principles" not in lower
    assert "design" + "-partner" not in lower


def test_readme_front_images_are_present(repo_root: Path):
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    asset_paths = [
        "docs/assets/skillseeking-hero.png",
        "docs/assets/skillseeking-evidence-loop.png",
    ]

    for asset_path in asset_paths:
        assert asset_path in readme
        asset = repo_root / asset_path
        assert asset.exists(), f"missing README asset: {asset_path}"
        assert asset.stat().st_size > 100_000, f"unexpectedly tiny README asset: {asset_path}"


def test_internal_process_docs_are_out_of_public_top_level(repo_root: Path):
    assert not (repo_root / "docs" / "plans").exists()
    assert not (repo_root / "docs" / "reviews").exists()
    assert not (repo_root / "docs" / "dev-log.md").exists()
    assert not (repo_root / "docs" / "v1-release-tasking.md").exists()
    assert not (repo_root / "exports").exists()

    assert (repo_root / "docs" / "internal" / "plans").is_dir()
    assert (repo_root / "docs" / "internal" / "reviews").is_dir()
    assert (repo_root / "docs" / "internal" / "dev-log.md").exists()
    assert (repo_root / "docs" / "internal" / "v1-release-tasking.md").exists()


def test_cli_reference_carries_command_detail(repo_root: Path):
    reference = (repo_root / "docs" / "cli-reference.md").read_text(encoding="utf-8")

    for command in [
        "skill-agent registry",
        "skill-agent run",
        "skill-agent explain",
        "skill-agent eval",
        "skill-agent candidate-decision",
        "skill-agent shadow-managed-write",
        "skill-agent feedback-session-template",
        "skill-agent feedback-session-append",
        "skill-agent feedback-log-summary",
        "skill-agent new-authority-readiness",
    ]:
        assert command in reference
    assert "docs/reviewer-feedback-log.md" in reference


def test_start_here_keeps_public_first_run_path_simple(repo_root: Path):
    start_here = (repo_root / "docs" / "start-here.md").read_text(encoding="utf-8")
    lower = start_here.lower()

    assert "public-dev-preview first-run path" in lower
    assert "scripts/cli_doctor.py" in start_here
    assert "scripts/run_launch_demo.sh --keep-workspace" in start_here
    assert "operator-summary --runs-dir <demo-workspace>/runs" in start_here
    assert "candidate evidence is not durable admission" in lower
    assert "stable routing remains disabled" in lower
    assert "not a hosted service" in lower
    assert "not production-safe" in lower
    assert "not a true sandbox" in lower


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


def test_changelog_version_and_classifier_match_public_claim(repo_root: Path):
    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    pyproject = tomllib.loads(
        (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    project_version = pyproject["project"]["version"]

    assert "## Unreleased" in changelog
    assert "## [1.0.0] - 2026-06-06" in changelog
    assert project_version == "1.0.0"
    assert "Development Status :: 3 - Alpha" in pyproject["project"]["classifiers"]
    assert re.search(r"^## \[?1\.0\.0\]?", changelog, re.MULTILINE) is not None


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
    assert "production-safety claim" in lower


def test_v1_tasking_marks_final_release_without_stale_candidate_status(repo_root: Path):
    tasking = (
        repo_root / "docs" / "internal" / "v1-release-tasking.md"
    ).read_text(encoding="utf-8")
    lower = tasking.lower()

    assert "status: complete for v1.0 local cli release" in lower
    assert "v1.0 local cli release for governed capability acquisition" in lower
    assert "local v1 cli release candidate for governed capability acquisition" not in lower


def test_launch_proof_records_release_boundaries_without_private_remote(repo_root: Path):
    proof = (repo_root / "docs" / "launch-proof-2026-06-07.md").read_text(
        encoding="utf-8"
    )
    lower = proof.lower()

    assert "status: private/local v1.0 release proof" in lower
    assert "refs/tags/v1.0.0^{}" in proof
    assert "full pytest: `279 passed`" in lower
    assert "tag-required v1 smoke: passed" in lower
    assert "v1 release eval inside v1 smoke: `11/11`" in lower
    assert "no hosted service proof" in lower
    assert "no true sandbox proof" in lower
    assert "no positive stable-routing proof" in lower
    assert "skillseeking" + "-private" not in proof


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
    assert "python scripts/security_check.py" in workflow
    assert "bash scripts/v1_smoke.sh" in workflow
    assert "REQUIRE_V1_TAG=1" not in workflow


def test_launch_demo_transcript_preserves_public_boundaries(repo_root: Path):
    transcript = (repo_root / "docs" / "launch-demo-transcript.md").read_text(
        encoding="utf-8"
    )
    lower = transcript.lower()

    assert "local public-dev-preview demo" in lower
    assert "human review remains in the path" in lower
    assert "operator-summary" in lower
    assert "first inspection surface" in lower
    assert "durable `skills/` admission remains disabled" in lower
    assert "stable routing remains disabled" in lower
    assert "not a hosted service" in lower
    assert "not production-safe" in lower
    assert "not a sandbox" in lower
    assert "does not provide a sandbox" in lower
    assert "does not autonomously promote candidates" in lower
    assert "does not enable positive stable routing" in lower


def test_reviewer_feedback_surfaces_match_source_and_scope(repo_root: Path):
    contributing = (repo_root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    review_pack = (repo_root / "docs" / "operator-summary-review-pack.md").read_text(
        encoding="utf-8"
    )
    reviewers = (repo_root / "docs" / "reviewer-feedback.md").read_text(
        encoding="utf-8"
    )
    feedback_log = (repo_root / "docs" / "reviewer-feedback-log.md").read_text(
        encoding="utf-8"
    )
    data_contracts = (repo_root / "docs" / "contracts" / "data-contracts.md").read_text(
        encoding="utf-8"
    )
    candidate_stable_rfc = (
        repo_root
        / "docs"
        / "internal"
        / "plans"
        / "candidate-to-stable-and-durable-admission-rfc-2026-06-07.md"
    ).read_text(encoding="utf-8")
    governor_preflight = (
        repo_root
        / "docs"
        / "internal"
        / "plans"
        / "active-governor-preflight-design-2026-06-07.md"
    ).read_text(encoding="utf-8")

    assert "MIT License" in (repo_root / "LICENSE").read_text(encoding="utf-8")
    assert "open source under the MIT License" in contributing
    assert "local CLI public-dev-preview workbench" in contributing
    assert "not a hosted product" in contributing

    assert "operator-summary" in review_pack
    assert "OPERATOR_DECISIONS" in review_pack
    assert "Candidate evidence means" in review_pack
    assert "not admission" in review_pack
    assert "No active governor steering" in review_pack

    assert "3 to 5 reviewer sessions" in reviewers
    assert "Operator Summary Review Pack" in reviewers
    assert "Reviewer Feedback Log" in reviewers
    assert "skill-agent feedback-session-template" in reviewers
    assert "skill-agent feedback-session-append --dry-run" in reviewers
    assert "feedback-session-append --no-dry-run" in reviewers
    assert "skill-agent feedback-log-summary" in reviewers
    assert "grant authority" in reviewers

    assert "Status: active public-dev-preview evidence log" in feedback_log
    assert "Completed partner sessions | 0" in feedback_log
    assert "No reviewer sessions have been recorded yet." in feedback_log

    assert "skill-agent feedback-session-template --json" in data_contracts
    assert "skill-agent feedback-session-append --json" in data_contracts
    assert "skill-agent feedback-log-summary --json" in data_contracts
    assert "template_only_read_only" in data_contracts
    assert "ready_for_manual_synthesis" in data_contracts
    assert "ready_to_enable_new_authority` must remain `false`" in data_contracts

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
        repo_root / "docs" / "v1-release-notes.md",
        repo_root / "docs" / "v1-release-contract.md",
        repo_root / "docs" / "demo-suite.md",
        repo_root / "docs" / "launch-demo-transcript.md",
        repo_root / "docs" / "reviewer-feedback.md",
        repo_root / "docs" / "product-brief.md",
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
        "dependency installation is enabled",
        "installs candidate dependencies",
        "automatically installs dependencies",
        "dependency installer is available",
        "provider api is enabled",
        "hosted api is enabled",
    ]

    for path in docs:
        text = path.read_text(encoding="utf-8").lower()
        for phrase in forbidden:
            assert phrase not in text, f"{path} contains positive authority claim: {phrase}"
