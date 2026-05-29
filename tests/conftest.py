from __future__ import annotations

from pathlib import Path
from shutil import copytree

import pytest


@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture
def seed_skills_dir(repo_root: Path) -> Path:
    return repo_root / "skills"


@pytest.fixture
def fixture_skills_dir(repo_root: Path) -> Path:
    return repo_root / "tests" / "fixtures" / "skills"


@pytest.fixture
def copied_seed_skills(tmp_path: Path, seed_skills_dir: Path) -> Path:
    target = tmp_path / "skills"
    copytree(seed_skills_dir, target)
    return target

