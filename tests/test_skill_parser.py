from __future__ import annotations

import pytest

from app.skill_parser import SkillParseError, parse_skill_file


def test_parse_valid_skill(fixture_skills_dir):
    parsed = parse_skill_file(fixture_skills_dir / "valid-skill" / "SKILL.md")

    assert parsed.frontmatter["name"] == "valid-skill"
    assert "Valid Skill" in parsed.body_text_for_scan_only


@pytest.mark.parametrize(
    "fixture_name",
    ["missing-frontmatter", "invalid-yaml"],
)
def test_rejects_malformed_skill_files(fixture_skills_dir, fixture_name):
    with pytest.raises(SkillParseError):
        parse_skill_file(fixture_skills_dir / fixture_name / "SKILL.md")

