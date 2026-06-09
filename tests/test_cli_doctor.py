from __future__ import annotations

import json
import subprocess
import sys


def test_cli_doctor_reports_passing_cli_surface(repo_root):
    result = subprocess.run(  # noqa: S603 - args are controlled by the test.
        [
            sys.executable,
            "scripts/cli_doctor.py",
            "--json",
        ],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=40,
    )

    assert result.returncode == 0, result.stderr + result.stdout
    data = json.loads(result.stdout)
    assert data["status"] == "passed"
    assert data["issue_count"] == 0
    check_names = {check["name"] for check in data["checks"]}
    assert "banner renders compactly" in check_names
    assert "blocked missing skill reports issue" in check_names
    assert "operator summary json is parseable" in check_names
