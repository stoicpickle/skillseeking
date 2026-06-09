from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from shutil import which


REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    checks = [
        (
            "bandit",
            [
                sys.executable,
                "-m",
                "bandit",
                "-c",
                "pyproject.toml",
                "-r",
                "app",
                "scripts",
            ],
        ),
        (
            "pip-audit",
            [sys.executable, "-m", "pip_audit", ".", "--progress-spinner", "off"],
        ),
    ]
    for name, command in checks:
        result = _run(name, command)
        if result != 0:
            return result

    return _run_detect_secrets()


def _run(name: str, command: list[str]) -> int:
    print(f"==> {name}")
    completed = subprocess.run(command, cwd=REPO_ROOT, check=False)
    return completed.returncode


def _run_detect_secrets() -> int:
    print("==> detect-secrets")
    baseline = REPO_ROOT / ".secrets.baseline"
    if not baseline.exists():
        print("missing .secrets.baseline; run detect-secrets scan > .secrets.baseline")
        return 1

    hook = str(Path(sys.executable).parent / "detect-secrets-hook")
    if not Path(hook).exists():
        hook = which("detect-secrets-hook")
    if hook is None:
        print("detect-secrets-hook is not installed")
        return 1
    git = which("git")
    if git is None:
        print("git is not installed")
        return 1

    files_result = subprocess.run(
        [git, "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
    )
    if files_result.returncode != 0:
        sys.stdout.buffer.write(files_result.stdout)
        sys.stderr.buffer.write(files_result.stderr)
        return files_result.returncode

    files = []
    for item in files_result.stdout.split(b"\0"):
        if not item:
            continue
        path = item.decode("utf-8")
        if path != baseline.name:
            files.append(path)
    if not files:
        return 0

    completed = subprocess.run(
        [hook, "--baseline", str(baseline), *files],
        cwd=REPO_ROOT,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
