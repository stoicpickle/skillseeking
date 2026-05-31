from __future__ import annotations

import json
import subprocess
import sys

from app.env_utils import safe_env
from app.models import ScriptExecutionLog, SkillRecord


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
        return ScriptExecutionLog(
            skill_name=skill.name,
            command=command,
            returncode=result.returncode,
            stdout=result.stdout.strip(),
            stderr=result.stderr.strip(),
        )
    except subprocess.TimeoutExpired as exc:
        return ScriptExecutionLog(
            skill_name=skill.name,
            command=command,
            returncode=124,
            stdout=(exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            stderr=(exc.stderr or "").strip() if isinstance(exc.stderr, str) else "",
            timed_out=True,
        )
