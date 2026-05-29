from __future__ import annotations

from pathlib import Path

import yaml

from app.models import ParsedSkill


class SkillParseError(ValueError):
    pass


def parse_skill_file(path: Path) -> ParsedSkill:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise SkillParseError("missing YAML frontmatter")

    parts = text.split("---\n", 2)
    if len(parts) < 3:
        raise SkillParseError("unterminated YAML frontmatter")

    raw_frontmatter = parts[1]
    body = parts[2].strip()
    if not body:
        raise SkillParseError("empty SKILL.md body")

    try:
        frontmatter = yaml.safe_load(raw_frontmatter)
    except yaml.YAMLError as exc:
        raise SkillParseError(f"invalid YAML frontmatter: {exc}") from exc

    if not isinstance(frontmatter, dict):
        raise SkillParseError("frontmatter must be a mapping")

    return ParsedSkill(frontmatter=frontmatter, body_text_for_scan_only=body, path=path)

