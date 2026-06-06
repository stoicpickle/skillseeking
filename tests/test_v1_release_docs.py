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
    ]

    for path in required_paths:
        assert path.exists(), f"missing release doc: {path}"
        assert path.read_text(encoding="utf-8").strip(), f"empty release doc: {path}"


def test_readme_positions_v1_as_local_cli_with_boundaries(repo_root: Path):
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    lower = readme.lower()
    opening = lower[:500]

    assert "local v1 cli release candidate" in lower
    assert "governed capability acquisition" in lower
    assert "not stamped or tagged as `1.0.0` yet" in lower
    assert "not a production agent framework" in lower
    assert "not a hosted platform" in lower
    assert "not production-safe" in lower
    assert "cli-first research prototype" not in opening
    assert "docs/v1-release-notes.md" in readme
    assert "CHANGELOG.md" in readme


def test_release_notes_are_honest_about_current_v1_state(repo_root: Path):
    notes = (repo_root / "docs" / "v1-release-notes.md").read_text(
        encoding="utf-8"
    )
    lower = notes.lower()

    assert "local v1 release candidate" in lower
    assert "not stamped or tagged as `1.0.0` yet" in lower
    assert "governed capability acquisition" in lower
    assert "stable routing is deferred for v1" in lower
    assert "not a true sandbox" in lower
    assert "not a hosted service" in lower
    assert "not provide an external skill marketplace" in lower
    assert "no `1.0.0` version stamp, tag, or published release" in lower
    assert "published release exists" not in lower


def test_changelog_is_ready_without_claiming_a_released_1_0_0(repo_root: Path):
    changelog = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8")
    pyproject = tomllib.loads(
        (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    )
    project_version = pyproject["project"]["version"]

    assert "## Unreleased" in changelog
    assert "local v1 cli release-candidate" in changelog.lower()
    assert "pyproject.toml` has not been stamped as `1.0.0`" in changelog
    released_1_0_0 = re.search(r"^## \[?1\.0\.0\]?", changelog, re.MULTILINE)
    if project_version != "1.0.0":
        assert released_1_0_0 is None


def test_release_contract_marks_docs_complete_but_keeps_final_gate(repo_root: Path):
    contract = (repo_root / "docs" / "v1-release-contract.md").read_text(
        encoding="utf-8"
    )
    lower = contract.lower()

    assert "release-candidate docs ready" in lower
    assert "changelog.md" in lower
    assert "docs/v1-release-notes.md" in lower
    assert "final `1.0.0` gate" in lower
    assert "- release notes and changelog;" not in lower
