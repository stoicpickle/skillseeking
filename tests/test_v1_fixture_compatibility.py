from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.models import (
    SCHEMA_VERSION,
    CandidateDecisionReport,
    EvidenceCheckpointLedger,
    InputRequestResolutionLedger,
    RunLog,
    SkillCandidateLedger,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "v1_contracts"


def _load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("fixture_name", "model_type", "expected_version", "required_keys"),
    [
        (
            "run_log.schema_v3.json",
            RunLog,
            SCHEMA_VERSION,
            {"run_id", "task_id", "result_category", "execution_summary", "trace_events"},
        ),
        (
            "skill_candidate_ledger.schema_v1.json",
            SkillCandidateLedger,
            1,
            {"entries", "updated_at"},
        ),
        (
            "input_resolution_ledger.schema_v1.json",
            InputRequestResolutionLedger,
            1,
            {"resolutions"},
        ),
        (
            "evidence_checkpoint_ledger.schema_v3.json",
            EvidenceCheckpointLedger,
            SCHEMA_VERSION,
            {"checkpoints"},
        ),
    ],
)
def test_v1_model_backed_fixtures_validate_and_round_trip(
    fixture_name: str,
    model_type: type,
    expected_version: int,
    required_keys: set[str],
):
    raw = _load_fixture(fixture_name)
    model = model_type.model_validate(raw)
    dumped = model.model_dump(mode="json")

    assert dumped["schema_version"] == expected_version
    assert required_keys <= set(dumped)
    model_type.model_validate(dumped)


def test_v1_candidate_decision_fixture_validates_and_preserves_authority_boundary():
    raw = _load_fixture("candidate_decision_report.v1.json")
    report = CandidateDecisionReport.model_validate(raw)
    dumped = report.model_dump(mode="json")

    assert dumped["candidate_id"] == "candidate_fixture_001"
    assert dumped["decision"] == "ask_human"
    assert dumped["next_command"] == "skill-agent stable-readiness candidate_fixture_001"
    assert dumped["stable_readiness"]["outcome"] == "ready_for_stable_review"
    assert dumped["stable_review_authorized"] is False
    assert dumped["stable_promotion_authorized"] is False
    assert dumped["stable_routing_enabled"] is False
    assert dumped["durable_skills_mutated"] is False
    assert dumped["registry_mutated"] is False
    CandidateDecisionReport.model_validate(dumped)


def test_v1_eval_report_fixture_keeps_public_json_shape():
    report = _load_fixture("eval_report.v1.json")

    assert report["suite"] == "evals/v1_release.jsonl"
    assert report["passed"] is True
    assert set(report) >= {
        "suite",
        "skills_dir",
        "runs_dir",
        "timestamp",
        "tasks",
        "aggregate",
        "passed",
        "json_report_path",
        "markdown_report_path",
    }
    assert report["aggregate"]["total"] == 1
    assert report["aggregate"]["passed"] == 1
    assert report["aggregate"]["failed"] == 0
    assert report["aggregate"]["diagnostic_dimensions"]["release_gate"]["pass_rate"] == 1.0
    assert len(report["tasks"]) == 1
    task = report["tasks"][0]
    assert set(task) >= {
        "id",
        "tags",
        "expected",
        "passed",
        "issues",
        "failure_categories",
        "run_id",
        "run_log_path",
        "result_category",
        "routing_decisions",
        "governor_decisions",
        "trace_complete",
    }
    assert task["passed"] is True
    assert task["trace_complete"] is True
    assert json.loads(json.dumps(report, sort_keys=True)) == report
