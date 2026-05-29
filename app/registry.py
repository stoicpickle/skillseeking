from __future__ import annotations

from pathlib import Path

from app.models import RejectedSkill, SkillRecord
from app.skill_parser import SkillParseError, parse_skill_file
from app.skill_validator import validate_parsed_skill


class SkillRegistry:
    def __init__(self, records: list[SkillRecord], rejections: list[RejectedSkill]) -> None:
        self._records = sorted(records, key=lambda record: record.name)
        self._rejections = sorted(rejections, key=lambda rejection: str(rejection.path))

    @classmethod
    def load(cls, skills_dir: Path, allow_scripts: bool = False) -> "SkillRegistry":
        records: list[SkillRecord] = []
        rejections: list[RejectedSkill] = []

        if not skills_dir.exists():
            return cls(records, rejections)

        for skill_file in sorted(skills_dir.glob("*/SKILL.md")):
            try:
                parsed = parse_skill_file(skill_file)
            except SkillParseError as exc:
                rejections.append(RejectedSkill(path=skill_file, reasons=[str(exc)]))
                continue

            result = validate_parsed_skill(parsed, skills_dir, allow_scripts=allow_scripts)
            if result.accepted and result.normalized_record is not None:
                records.append(result.normalized_record)
            else:
                rejections.append(result.rejected_skill(skill_file))

        return cls(records, rejections)

    def list_records(self) -> list[SkillRecord]:
        return list(self._records)

    def get(self, name: str) -> SkillRecord | None:
        for record in self._records:
            if record.name == name:
                return record
        return None

    def rejections(self) -> list[RejectedSkill]:
        return list(self._rejections)
