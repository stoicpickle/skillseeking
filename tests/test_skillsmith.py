from __future__ import annotations

from app.models import SkillRequest
from app.registry import SkillRegistry
from app.skillsmith import draft_temporary_skill


def test_draft_low_risk_temporary_skill_writes_and_validates_markdown(tmp_path):
    skills_dir = tmp_path / "skills"
    request = SkillRequest(
        id="skillreq_test",
        task_id="task_test",
        missing_capability="format research notes",
        reason="No existing skill met threshold.",
        desired_skill_name="format-research-notes",
        input_schema={"notes": "array"},
        output_schema={"formatted_notes": "string", "confidence": "number"},
        success_criteria=["Formats notes consistently"],
        failure_modes=["Returns empty output for empty notes"],
        risk_level="low",
    )

    result = draft_temporary_skill(request, skills_dir)

    assert result.validation_passed
    assert result.skill_name == "format-research-notes"
    assert result.skill_path.exists()
    assert not (result.skill_path.parent / "scripts").exists()
    registry = SkillRegistry.load(skills_dir)
    record = registry.get("format-research-notes")
    assert record is not None
    assert record.validation_status == "temporary"


def test_medium_risk_temporary_skill_is_written_then_rejected_and_cleaned_up(tmp_path):
    skills_dir = tmp_path / "skills"
    request = SkillRequest(
        id="skillreq_test",
        task_id="task_test",
        missing_capability="detect contradictions",
        reason="No existing skill met threshold.",
        desired_skill_name="detect-contradictions",
        input_schema={"claims": "array"},
        output_schema={"contradictions": "array", "confidence": "number"},
        success_criteria=["Finds direct contradiction"],
        failure_modes=["Returns none for unrelated claims"],
        risk_level="medium",
    )

    result = draft_temporary_skill(request, skills_dir)

    assert not result.validation_passed
    assert any("non-scripted skills must be low risk" in reason for reason in result.validation_reasons)
    assert not result.skill_path.exists()
    assert not result.skill_path.parent.exists()


def test_failed_temporary_skill_validation_cleans_up_generated_file(tmp_path):
    skills_dir = tmp_path / "skills"
    request = SkillRequest(
        id="skillreq_test",
        task_id="task_test",
        missing_capability="make invalid skill",
        reason="No existing skill met threshold.",
        desired_skill_name="invalid_name",
        input_schema={"input": "object"},
        output_schema={"result": "object"},
        success_criteria=["Fails validation because the name is invalid"],
        failure_modes=[],
        risk_level="low",
    )

    result = draft_temporary_skill(request, skills_dir)

    assert not result.validation_passed
    assert not result.skill_path.exists()
    assert not result.skill_path.parent.exists()
