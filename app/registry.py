from __future__ import annotations

from pathlib import Path

from app.models import RejectedSkill, SkillLifecycle, SkillRecord
from app.skill_parser import SkillParseError, parse_skill_file
from app.skill_validator import validate_parsed_skill


class SkillRegistry:
    def __init__(self, records: list[SkillRecord], rejections: list[RejectedSkill]) -> None:
        self._records = sorted(records, key=lambda record: record.name)
        self._rejections = sorted(rejections, key=lambda rejection: str(rejection.path))

    @classmethod
    def load(
        cls,
        skills_dir: Path,
        allow_scripts: bool = False,
        temporary_skill_roots: list[Path] | None = None,
        run_id: str | None = None,
    ) -> "SkillRegistry":
        records_by_name: dict[str, SkillRecord] = {}
        rejections: list[RejectedSkill] = []

        cls._load_root(
            skills_dir,
            records_by_name,
            rejections,
            allow_scripts=allow_scripts,
            lifecycle=SkillLifecycle(stage="durable", source="registry", temporary=False),
        )

        for temporary_root in temporary_skill_roots or []:
            cls._load_root(
                temporary_root,
                records_by_name,
                rejections,
                allow_scripts=allow_scripts,
                lifecycle=SkillLifecycle(
                    stage="temporary",
                    source="skillsmith",
                    run_id=run_id,
                    temporary=True,
                    notes="Run-scoped temporary registry overlay.",
                ),
            )

        return cls(list(records_by_name.values()), rejections)

    @staticmethod
    def _load_root(
        skill_root: Path,
        records_by_name: dict[str, SkillRecord],
        rejections: list[RejectedSkill],
        *,
        allow_scripts: bool,
        lifecycle: SkillLifecycle,
    ) -> None:
        if not skill_root.exists():
            return

        for skill_file in sorted(skill_root.glob("*/SKILL.md")):
            try:
                parsed = parse_skill_file(skill_file)
            except SkillParseError as exc:
                rejections.append(RejectedSkill(path=skill_file, reasons=[str(exc)]))
                continue

            result = validate_parsed_skill(
                parsed,
                skill_root,
                allow_scripts=allow_scripts,
                lifecycle=lifecycle,
            )
            if result.accepted and result.normalized_record is not None:
                # Later roots are explicit overlays for this process/run and may shadow durable names.
                records_by_name[result.normalized_record.name] = result.normalized_record
            else:
                rejections.append(result.rejected_skill(skill_file))

    def list_records(self) -> list[SkillRecord]:
        return list(self._records)

    def get(self, name: str) -> SkillRecord | None:
        for record in self._records:
            if record.name == name:
                return record
        return None

    def rejections(self) -> list[RejectedSkill]:
        return list(self._rejections)
