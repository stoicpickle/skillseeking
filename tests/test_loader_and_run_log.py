from __future__ import annotations

import json

import pytest

from app.loader import SkillLoadError, load_skill
from app.models import RunLog
from app.registry import SkillRegistry
from app.run_log import write_run_log


def test_loader_loads_selected_skill_body(seed_skills_dir):
    registry = SkillRegistry.load(seed_skills_dir)
    record = registry.get("extract-claims")
    assert record is not None

    loaded = load_skill(record, seed_skills_dir, "extract atomic factual claims", "test load")

    assert loaded.name == "extract-claims"
    assert "Turn source text into short" in loaded.markdown_body


def test_loader_rejects_tampered_path(seed_skills_dir):
    registry = SkillRegistry.load(seed_skills_dir)
    record = registry.get("extract-claims")
    assert record is not None
    tampered = record.model_copy(update={"path": seed_skills_dir.parent / "README.md"})

    with pytest.raises(SkillLoadError):
        load_skill(tampered, seed_skills_dir, "extract atomic factual claims", "test load")


def test_run_log_writes_json_without_markdown_body(tmp_path):
    run_log = RunLog(
        task_id="task_test",
        task="test",
        created_at="2026-05-29T10:00:00",
        plan=["extract atomic factual claims"],
        capability_decisions=[],
        skills_loaded=[],
        rejected_skills=[],
        trace=["PLANNING", "RUN_LOG_WRITTEN"],
    )

    path = write_run_log(run_log, tmp_path / "runs")
    data = json.loads(path.read_text(encoding="utf-8"))

    assert data["schema_version"] == 3
    assert data["run_id"] == run_log.run_id
    assert run_log.run_id in path.name
    assert data["task_id"] == "task_test"
    assert data["skill_repair_requests"] == []
    assert data["input_requests"] == []
    assert data["governor_decisions"] == []
    assert data["trace_events"] == []
    assert data["execution_summary"]["result_category"] == "success"
    assert data["result_quality"]["notes"] == "Route/request execution; quality scoring deferred."
    assert "markdown_body" not in path.read_text(encoding="utf-8")


def test_run_log_accepts_schema_v2_without_governor_decisions():
    run_log = RunLog.model_validate(
        {
            "schema_version": 2,
            "task_id": "task_legacy",
            "task": "legacy",
            "created_at": "2026-05-29T10:00:00",
            "plan": ["extract atomic factual claims"],
            "capability_decisions": [],
            "skills_loaded": [],
            "rejected_skills": [],
            "trace": ["PLANNING", "RUN_LOG_WRITTEN"],
        }
    )

    assert run_log.schema_version == 2
    assert run_log.governor_decisions == []
