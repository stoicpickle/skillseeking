from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
from shutil import copytree, which
import subprocess
import sys
import tempfile
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    name: str
    args: list[str]
    expected_exit_code: int = 0
    stdout_contains: tuple[str, ...] = ()
    json_assertions: tuple[tuple[str, Any], ...] = ()


@dataclass
class CheckResult:
    name: str
    command: list[str]
    expected_exit_code: int
    exit_code: int | None
    status: str
    issues: list[str] = field(default_factory=list)
    stdout_tail: str = ""
    stderr_tail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "command": self.command,
            "expected_exit_code": self.expected_exit_code,
            "exit_code": self.exit_code,
            "status": self.status,
            "issues": self.issues,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
        }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run a quick skill-agent CLI doctor and report operator-facing issues."
    )
    parser.add_argument(
        "--skill-agent-bin",
        type=Path,
        default=None,
        help="skill-agent executable to run. Defaults to .venv/bin/skill-agent, PATH, or python -m app.cli.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a machine-readable report.",
    )
    parser.add_argument(
        "--keep-workspace",
        action="store_true",
        help="Keep the temporary doctor workspace for manual inspection.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="Per-command timeout in seconds.",
    )
    args = parser.parse_args()

    skill_agent_cmd = _resolve_skill_agent_cmd(args.skill_agent_bin)
    workspace = Path(tempfile.mkdtemp(prefix="skill-agent-cli-doctor."))
    try:
        results = run_cli_doctor(
            skill_agent_cmd=skill_agent_cmd,
            workspace=workspace,
            timeout=args.timeout,
        )
        report = {
            "status": "passed" if all(result.status == "passed" for result in results) else "failed",
            "workspace": workspace.as_posix(),
            "skill_agent_command": skill_agent_cmd,
            "checks": [result.to_dict() for result in results],
            "issue_count": sum(len(result.issues) for result in results),
        }
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            _print_human_report(report)
        if report["status"] != "passed":
            raise SystemExit(1)
    finally:
        if args.keep_workspace:
            print(f"Doctor workspace kept: {workspace}", file=sys.stderr)
        else:
            _remove_workspace(workspace)


def run_cli_doctor(
    *,
    skill_agent_cmd: list[str],
    workspace: Path,
    timeout: float,
) -> list[CheckResult]:
    skills_dir = workspace / "skills"
    runs_dir = workspace / "runs"
    copytree(REPO_ROOT / "skills", skills_dir)
    runs_dir.mkdir(parents=True, exist_ok=True)

    checks = [
        Check(
            name="banner renders compactly",
            args=["banner", "--no-color"],
            stdout_contains=(
                "Skill-Seeking Agent",
                "local CLI | evidence first | no hidden authority",
            ),
        ),
        Check(
            name="top-level help is available",
            args=["--help"],
            stdout_contains=("run", "eval", "operator-summary"),
        ),
        Check(
            name="existing-skill run succeeds",
            args=[
                "run",
                "Extract claims from this article and write a structured summary with source-quality notes.",
                "--skills-dir",
                skills_dir.as_posix(),
                "--runs-dir",
                runs_dir.as_posix(),
            ],
            stdout_contains=("ROUTE_COMPLETE", "RESULT", "Exit code: 0"),
        ),
        Check(
            name="temporary-skill run succeeds",
            args=[
                "run",
                "Cluster arguments from these sources.",
                "--skills-dir",
                skills_dir.as_posix(),
                "--runs-dir",
                runs_dir.as_posix(),
            ],
            stdout_contains=(
                "BLOCKED_MISSING_SKILL",
                "VALIDATION_PASSED",
                "LOADING_TEMP_SKILL",
                "Exit code: 0",
            ),
        ),
        Check(
            name="blocked missing skill reports issue",
            args=[
                "run",
                "Extract claims from these two sources and identify contradictions.",
                "--no-temporary-skills",
                "--skills-dir",
                skills_dir.as_posix(),
                "--runs-dir",
                runs_dir.as_posix(),
            ],
            expected_exit_code=1,
            stdout_contains=(
                "REQUESTING_SKILL",
                "Missing capability: detect contradictions",
                "Exit code: 1",
            ),
        ),
        Check(
            name="registry json is parseable",
            args=["registry", "--json", "--skills-dir", skills_dir.as_posix()],
            json_assertions=(("accepted", list), ("rejected", list)),
        ),
        Check(
            name="health json is parseable",
            args=[
                "health",
                "--json",
                "--skills-dir",
                skills_dir.as_posix(),
                "--runs-dir",
                runs_dir.as_posix(),
            ],
            json_assertions=(("accepted_skills", int), ("run_logs_read", int)),
        ),
        Check(
            name="operator summary json is parseable",
            args=["operator-summary", "--json", "--runs-dir", runs_dir.as_posix()],
            json_assertions=(("advisory_only", True), ("run_logs_mutated", False)),
        ),
        Check(
            name="v1 local-use boundary is intact",
            args=["v1-local-use", "--json"],
            json_assertions=(
                ("primary_command", "shadow-managed-write"),
                ("stable_routing_policy", "deferred_for_v1"),
            ),
        ),
        Check(
            name="new-authority readiness remains advisory",
            args=["new-authority-readiness", "--json"],
            json_assertions=(("ready_for_authority_planning", True), ("ready_to_enable_new_authority", False)),
        ),
    ]

    return [
        _run_check(check, skill_agent_cmd=skill_agent_cmd, timeout=timeout)
        for check in checks
    ]


def _resolve_skill_agent_cmd(skill_agent_bin: Path | None) -> list[str]:
    if skill_agent_bin is not None:
        return [skill_agent_bin.as_posix()]
    venv_bin = REPO_ROOT / ".venv" / "bin" / "skill-agent"
    if venv_bin.exists():
        return [venv_bin.as_posix()]
    path_bin = which("skill-agent")
    if path_bin:
        return [path_bin]
    return [sys.executable, "-m", "app.cli"]


def _run_check(check: Check, *, skill_agent_cmd: list[str], timeout: float) -> CheckResult:
    command = [*skill_agent_cmd, *check.args]
    try:
        completed = subprocess.run(  # noqa: S603 - command is repo-local or caller supplied.
            command,
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return CheckResult(
            name=check.name,
            command=command,
            expected_exit_code=check.expected_exit_code,
            exit_code=None,
            status="failed",
            issues=[f"command timed out after {timeout:g}s"],
            stdout_tail=_tail(exc.stdout or ""),
            stderr_tail=_tail(exc.stderr or ""),
        )

    issues: list[str] = []
    if completed.returncode != check.expected_exit_code:
        issues.append(
            f"expected exit code {check.expected_exit_code}, got {completed.returncode}"
        )
    for needle in check.stdout_contains:
        if needle not in completed.stdout:
            issues.append(f"stdout missing {needle!r}")
    if check.json_assertions:
        issues.extend(_json_issues(completed.stdout, check.json_assertions))

    return CheckResult(
        name=check.name,
        command=command,
        expected_exit_code=check.expected_exit_code,
        exit_code=completed.returncode,
        status="failed" if issues else "passed",
        issues=issues,
        stdout_tail=_tail(completed.stdout),
        stderr_tail=_tail(completed.stderr),
    )


def _json_issues(stdout: str, assertions: tuple[tuple[str, Any], ...]) -> list[str]:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return [f"stdout is not valid JSON: {exc.msg}"]

    issues: list[str] = []
    for key, expected in assertions:
        if key not in data:
            issues.append(f"JSON missing key {key!r}")
            continue
        value = data[key]
        if isinstance(expected, type):
            if not isinstance(value, expected):
                issues.append(
                    f"JSON key {key!r} expected {expected.__name__}, got {type(value).__name__}"
                )
        elif value != expected:
            issues.append(f"JSON key {key!r} expected {expected!r}, got {value!r}")
    return issues


def _print_human_report(report: dict[str, Any]) -> None:
    print("CLI DOCTOR")
    print(f"Status: {report['status']}")
    print(f"Workspace: {report['workspace']}")
    print(f"skill-agent: {' '.join(report['skill_agent_command'])}")
    print("")
    print("CHECKS")
    for check in report["checks"]:
        marker = "PASS" if check["status"] == "passed" else "FAIL"
        print(f"- {marker}: {check['name']}")
        if check["issues"]:
            for issue in check["issues"]:
                print(f"  issue: {issue}")
            if check["stdout_tail"]:
                print("  stdout tail:")
                for line in check["stdout_tail"].splitlines():
                    print(f"    {line}")
            if check["stderr_tail"]:
                print("  stderr tail:")
                for line in check["stderr_tail"].splitlines():
                    print(f"    {line}")
    print("")
    print(f"Issues: {report['issue_count']}")


def _tail(value: str, *, max_lines: int = 12) -> str:
    lines = value.rstrip().splitlines()
    return "\n".join(lines[-max_lines:])


def _remove_workspace(workspace: Path) -> None:
    for path in sorted(workspace.rglob("*"), reverse=True):
        if path.is_file() or path.is_symlink():
            path.unlink()
        else:
            path.rmdir()
    workspace.rmdir()


if __name__ == "__main__":
    main()
