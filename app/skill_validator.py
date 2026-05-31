from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError

from app.models import RejectedSkill, SkillLifecycle, SkillManifest, SkillRecord
from app.script_validator import validate_script_tests
from app.skill_parser import ParsedSkill


NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SUSPICIOUS_PATTERNS = [
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s+prompt", re.IGNORECASE),
    re.compile(r"always\s+use\s+this\s+skill", re.IGNORECASE),
    re.compile(r"use\s+this\s+skill\s+for\s+every\s+task", re.IGNORECASE),
    re.compile(r"(request|read|steal|exfiltrate|expose|use)\s+secrets?", re.IGNORECASE),
    re.compile(r"api\s*key", re.IGNORECASE),
    re.compile(r"modify\s+routing", re.IGNORECASE),
    re.compile(r"routing\s+behavior", re.IGNORECASE),
    re.compile(r"\b[A-Za-z0-9+/]{80,}={0,2}\b"),
]


class ValidationResult:
    def __init__(
        self,
        accepted: bool,
        reasons: list[str],
        normalized_record: SkillRecord | None = None,
        name: str | None = None,
    ) -> None:
        self.accepted = accepted
        self.reasons = reasons
        self.normalized_record = normalized_record
        self.name = name

    def rejected_skill(self, path: Path) -> RejectedSkill:
        return RejectedSkill(name=self.name, path=path, reasons=self.reasons)


def validate_parsed_skill(
    parsed: ParsedSkill,
    skill_root: Path,
    allow_scripts: bool = False,
    lifecycle: SkillLifecycle | None = None,
) -> ValidationResult:
    reasons: list[str] = []
    manifest: SkillManifest | None = None
    name = parsed.frontmatter.get("name") if isinstance(parsed.frontmatter, dict) else None

    try:
        manifest = SkillManifest.model_validate(parsed.frontmatter)
        name = manifest.name
    except ValidationError as exc:
        reasons.append(f"invalid manifest: {exc.errors()[0]['msg']}")

    skill_path = parsed.path.resolve()
    root = skill_root.resolve()
    if not _is_relative_to(skill_path, root):
        reasons.append("skill path is outside trusted skill root")

    if parsed.path.name != "SKILL.md":
        reasons.append("skill file must be named SKILL.md")

    if manifest is not None:
        if not NAME_RE.match(manifest.name):
            reasons.append("invalid skill name format")

        if parsed.path.parent.name != manifest.name:
            reasons.append("skill directory name must match frontmatter name")

        scripts_dir = parsed.path.parent / "scripts"
        has_scripts = scripts_dir.exists()

        if has_scripts and not allow_scripts:
            reasons.append("M1 skills cannot include scripts/")

        if not has_scripts and manifest.script is not None:
            reasons.append("script metadata requires scripts/")

        if has_scripts and manifest.script is None:
            reasons.append("scripted skills must declare script metadata")

        if not has_scripts and manifest.risk_level != "low":
            reasons.append("non-scripted skills must be low risk")

        if allow_scripts and has_scripts and manifest.risk_level != "medium":
            reasons.append("scripted skills must be medium risk")

        if manifest.metadata.status not in {"candidate", "stable"}:
            reasons.append("M1 admits only candidate or stable skills")

        if has_scripts:
            if manifest.allowed_tools != ["python"]:
                reasons.append("scripted skills must declare only the python tool")
        elif manifest.allowed_tools:
            reasons.append("M1 skills cannot declare allowed tools")

        permissions = manifest.permissions
        if permissions.read_files:
            reasons.append("M1 skills cannot request file-read permission")
        if permissions.write_files:
            reasons.append("M1 skills cannot request file-write permission")
        if permissions.network:
            reasons.append("M1 skills cannot request network permission")
        if permissions.secrets:
            reasons.append("M1 skills cannot request secrets")
        if permissions.execute_code and not (allow_scripts and has_scripts):
            reasons.append("M1 skills cannot request code execution")
        if has_scripts and not permissions.execute_code:
            reasons.append("scripted skills must request code execution")

        if allow_scripts and has_scripts and manifest.script is not None:
            entrypoint = (parsed.path.parent / manifest.script.entrypoint).resolve()
            try:
                entrypoint.relative_to(parsed.path.parent.resolve())
            except ValueError:
                reasons.append("script entrypoint escaped skill directory")
            if not entrypoint.exists():
                reasons.append("script entrypoint does not exist")
            tests_passed, test_output = validate_script_tests(parsed.path.parent)
            if not tests_passed:
                reasons.append(f"script tests failed: {test_output}")

    scan_text = f"{_frontmatter_values_text(parsed.frontmatter)}\n{parsed.body_text_for_scan_only}"
    for pattern in SUSPICIOUS_PATTERNS:
        if pattern.search(scan_text):
            reasons.append(f"suspicious text matched: {pattern.pattern}")
            break

    if reasons or manifest is None:
        return ValidationResult(False, reasons, name=name)

    record = SkillRecord(
        name=manifest.name,
        version=manifest.metadata.version,
        description=manifest.description,
        tags=manifest.tags,
        status=manifest.metadata.status,
        owner=manifest.metadata.owner,
        risk_level=manifest.risk_level,
        input_schema=manifest.input_schema,
        output_schema=manifest.output_schema,
        allowed_tools=manifest.allowed_tools,
        permissions=manifest.permissions,
        compatibility=manifest.compatibility,
        validation_status=manifest.validation.status,
        path=parsed.path,
        source_root=root,
        script=manifest.script,
        lifecycle=lifecycle or SkillLifecycle(),
    )
    return ValidationResult(True, [], normalized_record=record, name=manifest.name)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _frontmatter_values_text(value: object) -> str:
    if isinstance(value, dict):
        return " ".join(_frontmatter_values_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_frontmatter_values_text(item) for item in value)
    if isinstance(value, str):
        return value
    return ""
