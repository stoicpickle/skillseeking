from __future__ import annotations

import pytest

from app.skill_parser import SkillParseError, parse_skill_file
from app.skill_validator import validate_parsed_skill


def _validate(fixture_skills_dir, fixture_name):
    parsed = parse_skill_file(fixture_skills_dir / fixture_name / "SKILL.md")
    return validate_parsed_skill(parsed, fixture_skills_dir)


def test_accepts_valid_skill(fixture_skills_dir):
    result = _validate(fixture_skills_dir, "valid-skill")

    assert result.accepted
    assert result.normalized_record is not None
    assert result.normalized_record.name == "valid-skill"


@pytest.mark.parametrize(
    ("fixture_name", "reason_part"),
    [
        ("missing-risk", "invalid manifest"),
        ("name-mismatch", "directory name must match"),
        ("invalid_name", "invalid skill name"),
        ("malicious-body", "suspicious text"),
        ("network-skill", "network permission"),
        ("scripted-skill", "scripts/"),
    ],
)
def test_rejects_invalid_or_unsafe_skills(fixture_skills_dir, fixture_name, reason_part):
    result = _validate(fixture_skills_dir, fixture_name)

    assert not result.accepted
    assert any(reason_part in reason for reason in result.reasons)


def test_parser_error_is_separate_from_validator(fixture_skills_dir):
    with pytest.raises(SkillParseError):
        parse_skill_file(fixture_skills_dir / "missing-frontmatter" / "SKILL.md")

