from __future__ import annotations

from app.models import SkillRequest
from app.skill_repairer import create_skill_repair_request


def test_create_skill_repair_request_preserves_failed_skill_context():
    skill_request = SkillRequest(
        id="skillreq_test",
        task_id="task_test",
        missing_capability="run local python analysis",
        reason="No existing skill met threshold.",
        desired_skill_name="local-python-analysis",
        input_schema={"text": "string", "task": "string"},
        output_schema={"analysis": "object"},
        success_criteria=["Describes a local Python analysis workflow"],
        failure_modes=["Remain blocked until an explicit scripted skill is reviewed"],
        risk_level="medium",
    )

    repair_request = create_skill_repair_request(
        skill_request,
        ["non-scripted skills must be low risk"],
        "runs/artifacts/run_test/skills/local-python-analysis/SKILL.md",
    )

    assert repair_request.id.startswith("repairreq_")
    assert repair_request.task_id == "task_test"
    assert repair_request.skill_request_id == "skillreq_test"
    assert repair_request.skill_name == "local-python-analysis"
    assert repair_request.failed_capability == "run local python analysis"
    assert repair_request.failed_skill_path == "runs/artifacts/run_test/skills/local-python-analysis/SKILL.md"
    assert repair_request.failure_reasons == ["non-scripted skills must be low risk"]
    assert repair_request.status == "requested"
    assert any("Markdown-only" in item for item in repair_request.constraints)
    assert any("Do not auto-load" in item for item in repair_request.constraints)
