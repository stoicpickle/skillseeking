from __future__ import annotations

from pathlib import Path

from app.models import LoadedSkill, SkillRecord
from app.skill_parser import parse_skill_file


class SkillLoadError(ValueError):
    pass


def load_skill(
    skill_record: SkillRecord, skills_dir: Path, loaded_for_capability: str, load_reason: str
) -> LoadedSkill:
    skill_path = skill_record.path.resolve()
    root = skills_dir.resolve()
    try:
        skill_path.relative_to(root)
    except ValueError as exc:
        raise SkillLoadError("selected skill path is outside local skills directory") from exc

    if not skill_path.exists() or skill_path.name != "SKILL.md":
        raise SkillLoadError("selected SKILL.md does not exist")

    parsed = parse_skill_file(skill_path)
    if parsed.frontmatter.get("name") != skill_record.name:
        raise SkillLoadError("selected skill frontmatter no longer matches registry record")

    return LoadedSkill(
        name=skill_record.name,
        version=skill_record.version,
        path=skill_path,
        markdown_body=parsed.body_text_for_scan_only,
        frontmatter=parsed.frontmatter,
        loaded_for_capability=loaded_for_capability,
        load_reason=load_reason,
    )

