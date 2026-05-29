from __future__ import annotations

import hashlib

from app.models import SkillRepairRequest, SkillRequest


def create_skill_repair_request(
    skill_request: SkillRequest,
    failure_reasons: list[str],
    failed_skill_path: str | None,
) -> SkillRepairRequest:
    return SkillRepairRequest(
        id=_repair_request_id(skill_request.id, failure_reasons),
        task_id=skill_request.task_id,
        skill_request_id=skill_request.id,
        skill_name=skill_request.desired_skill_name,
        failed_capability=skill_request.missing_capability,
        failed_skill_path=failed_skill_path,
        failure_reasons=failure_reasons or ["temporary skill validation failed"],
        repair_objective=(
            "Revise the temporary Markdown skill so it satisfies the validator "
            "while preserving the requested capability contract."
        ),
        constraints=[
            "Keep the repair Markdown-only.",
            "Do not add scripts, dependencies, network access, secrets, or code execution.",
            "Do not auto-load the repaired skill without a fresh validation pass.",
        ],
    )


def _repair_request_id(skill_request_id: str, failure_reasons: list[str]) -> str:
    reason_text = "|".join(failure_reasons)
    digest = hashlib.sha1(f"{skill_request_id}:{reason_text}".encode("utf-8")).hexdigest()[:10]
    return f"repairreq_{digest}"
