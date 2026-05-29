from __future__ import annotations

from pathlib import Path

import yaml

from app.models import SkillRequest, TemporarySkillResult
from app.skill_parser import parse_skill_file
from app.skill_validator import validate_parsed_skill


class SkillsmithError(ValueError):
    pass


def draft_temporary_skill(request: SkillRequest, skills_dir: Path) -> TemporarySkillResult:
    skill_dir = _safe_skill_dir(skills_dir, request.desired_skill_name)
    skill_file = skill_dir / "SKILL.md"
    if skill_file.exists():
        raise SkillsmithError(f"temporary skill already exists: {skill_file}")

    skill_dir.mkdir(parents=True, exist_ok=False)
    skill_file.write_text(_render_skill_markdown(request), encoding="utf-8")

    parsed = parse_skill_file(skill_file)
    validation = validate_parsed_skill(parsed, skills_dir)
    if not validation.accepted:
        skill_file.unlink(missing_ok=True)
        try:
            skill_dir.rmdir()
        except OSError:
            pass

    return TemporarySkillResult(
        skill_name=request.desired_skill_name,
        skill_path=skill_file,
        validation_passed=validation.accepted,
        validation_reasons=validation.reasons,
    )


def _safe_skill_dir(skills_dir: Path, skill_name: str) -> Path:
    root = skills_dir.resolve()
    skill_dir = (root / skill_name).resolve()
    try:
        skill_dir.relative_to(root)
    except ValueError as exc:
        raise SkillsmithError("temporary skill path escaped skills directory") from exc
    return skill_dir


def _render_skill_markdown(request: SkillRequest) -> str:
    frontmatter = {
        "name": request.desired_skill_name,
        "description": f"Temporary Markdown skill for {request.missing_capability}.",
        "tags": ["temporary", "generated", "research"],
        "metadata": {
            "version": "0.1.0",
            "owner": "skillsmith",
            "status": "candidate",
        },
        "risk_level": request.risk_level,
        "compatibility": {"python": ">=3.11"},
        "allowed_tools": [],
        "permissions": {
            "read_files": False,
            "write_files": False,
            "network": False,
            "secrets": False,
            "execute_code": False,
        },
        "input_schema": request.input_schema,
        "output_schema": request.output_schema,
        "validation": {
            "status": "temporary",
            "notes": f"Generated from {request.id} for one-run provisional use.",
        },
    }
    yaml_text = yaml.safe_dump(frontmatter, sort_keys=False)
    success = "\n".join(f"- {item}" for item in request.success_criteria)
    failures = "\n".join(f"- {item}" for item in request.failure_modes)
    return f"""---
{yaml_text}---

# {request.desired_skill_name}

## What This Skill Does

{request.missing_capability}

## Inputs

Use the input schema declared in the frontmatter.

## Output

Return the output schema declared in the frontmatter.

## Procedure

1. Read the task context and provided inputs.
2. Apply the minimum repeatable procedure described by the missing capability.
3. Return only the declared output shape.
4. Mark uncertainty clearly when evidence is insufficient.

## Success Criteria

{success}

## Failure Cases

{failures}
"""
