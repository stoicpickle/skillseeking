from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path


def _tree_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hashes[str(path.relative_to(root))] = digest
    return hashes


def test_launch_demo_shows_wedge_and_preserves_durable_skills(repo_root: Path):
    durable_skills = repo_root / "skills"
    before = _tree_hashes(durable_skills)
    env = os.environ.copy()
    env["PYTHON_BIN"] = sys.executable

    result = subprocess.run(
        ["bash", "scripts/run_launch_demo.sh"],
        cwd=repo_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )

    after = _tree_hashes(durable_skills)
    assert after == before
    assert result.returncode == 0, result.stdout
    for landmark in [
        "LAUNCH DEMO",
        "BLOCKED_MISSING_SKILL",
        "REQUESTING_SKILL",
        "DRAFTING_TEMP_SKILL",
        "VALIDATION_PASSED",
        "LOADING_TEMP_SKILL",
        "ROUTE_COMPLETE",
        "Candidate decision",
        "Human review required: yes",
        "Durable skills mutated: no",
        "Stable routing enabled: no",
        "Hosted service used: no",
        "Sandbox provided: no",
    ]:
        assert landmark in result.stdout
