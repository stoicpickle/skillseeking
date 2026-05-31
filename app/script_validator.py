from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app.env_utils import safe_env

TEST_OUTPUT_LIMIT = 8192


def validate_script_tests(skill_dir: Path, timeout_seconds: int = 10) -> tuple[bool, str]:
    tests_dir = (skill_dir / "tests").resolve()
    if not tests_dir.exists():
        return False, "scripted skills must include tests/"

    env = safe_env(include_home=True)
    env["PYTHONPATH"] = str(skill_dir)
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", str(tests_dir)],
            cwd=skill_dir,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = (exc.stdout or "").strip() if isinstance(exc.stdout, str) else ""
        stderr = (exc.stderr or "").strip() if isinstance(exc.stderr, str) else ""
        output = "\n".join(part for part in [stdout, stderr] if part)
        return False, _cap_output(output or f"pytest timed out after {timeout_seconds}s")

    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
    return result.returncode == 0, _cap_output(output or f"pytest exited {result.returncode}")


def _cap_output(output: str) -> str:
    if len(output) <= TEST_OUTPUT_LIMIT:
        return output
    return output[:TEST_OUTPUT_LIMIT] + f"\n...[truncated to {TEST_OUTPUT_LIMIT} chars]"
