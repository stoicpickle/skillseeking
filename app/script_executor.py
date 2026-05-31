from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from app.env_utils import safe_env
from app.models import ScriptExecutionLog, SkillRecord

STDOUT_LIMIT = 8192
STDERR_LIMIT = 8192


def execute_scripted_skill(skill: SkillRecord, payload: dict) -> ScriptExecutionLog:
    if skill.script is None:
        raise ValueError(f"skill is not scripted: {skill.name}")

    skill_dir = skill.path.parent
    entrypoint = (skill_dir / skill.script.entrypoint).resolve()
    try:
        entrypoint.relative_to(skill_dir.resolve())
    except ValueError as exc:
        raise ValueError("script entrypoint escaped skill directory") from exc

    command = [sys.executable, str(entrypoint)]
    try:
        result = subprocess.run(
            command,
            cwd=skill_dir,
            env=safe_env(),
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=skill.script.timeout_seconds,
            check=False,
        )
        stdout_too_large = len(result.stdout or "") > STDOUT_LIMIT
        stderr_too_large = len(result.stderr or "") > STDERR_LIMIT
        stdout = _cap_text(result.stdout.strip(), STDOUT_LIMIT)
        stderr = _cap_text(result.stderr.strip(), STDERR_LIMIT)
        failure_category = None
        parsed_stdout = None
        output_validated = False

        if stdout_too_large or stderr_too_large:
            failure_category = "output_too_large"
        elif result.returncode != 0:
            failure_category = "nonzero_exit"
        else:
            try:
                parsed_stdout = json.loads(stdout or "null")
            except json.JSONDecodeError:
                failure_category = "invalid_json"
            else:
                output_validated = _matches_schema(parsed_stdout, skill.output_schema)
                if not output_validated:
                    failure_category = "output_schema_mismatch"

        return ScriptExecutionLog(
            skill_name=skill.name,
            command=command,
            returncode=result.returncode,
            stdout=stdout,
            stderr=stderr,
            parsed_stdout=parsed_stdout,
            output_validated=output_validated,
            failure_category=failure_category,
        )
    except subprocess.TimeoutExpired as exc:
        return ScriptExecutionLog(
            skill_name=skill.name,
            command=command,
            returncode=124,
            stdout=_cap_text((exc.stdout or "").strip() if isinstance(exc.stdout, str) else "", STDOUT_LIMIT),
            stderr=_cap_text((exc.stderr or "").strip() if isinstance(exc.stderr, str) else "", STDERR_LIMIT),
            timed_out=True,
            failure_category="timeout",
        )


def _cap_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n...[truncated to {limit} chars]"


def _matches_schema(value: Any, schema: dict[str, str]) -> bool:
    if not schema:
        return True
    if not isinstance(value, dict):
        return False
    for key, expected_type in schema.items():
        if key not in value:
            return False
        if not _matches_type(value[key], expected_type):
            return False
    return True


def _matches_type(value: Any, expected_type: str) -> bool:
    normalized = expected_type.lower()
    if normalized in {"string", "str"}:
        return isinstance(value, str)
    if normalized in {"integer", "int"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if normalized in {"number", "float"}:
        return (isinstance(value, int | float) and not isinstance(value, bool))
    if normalized in {"array", "list"}:
        return isinstance(value, list)
    if normalized in {"object", "dict"}:
        return isinstance(value, dict)
    if normalized in {"boolean", "bool"}:
        return isinstance(value, bool)
    return True
