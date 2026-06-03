from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.admission_plan import AdmissionPlanError, build_admission_plan
from app.models import (
    CandidateUsefulnessEvidenceRun,
    CandidateUsefulnessOutcome,
    CandidateUsefulnessReport,
    SkillCandidateLedgerEntry,
)
from app.skill_candidate_ledger import (
    SkillCandidateLedgerError,
    candidate_id_for,
    load_candidate_ledger,
)


class CandidateUsefulnessError(RuntimeError):
    pass


def build_candidate_usefulness_report(
    candidate_id: str,
    *,
    runs_dir: Path,
    skills_dir: Path,
) -> CandidateUsefulnessReport:
    try:
        ledger = load_candidate_ledger(runs_dir)
    except SkillCandidateLedgerError as exc:
        raise CandidateUsefulnessError(str(exc)) from exc

    entry = next((item for item in ledger.entries if item.candidate_id == candidate_id), None)
    if entry is None:
        raise CandidateUsefulnessError(f"candidate not found: {candidate_id}")

    warnings: list[str] = []
    run_logs = _run_log_index(runs_dir, warnings)
    evidence_runs = [_evidence_run(entry, run_id, run_logs) for run_id in entry.evidence_run_ids]
    blockers = _blockers(entry, evidence_runs)
    outcome = _outcome(entry, blockers, evidence_runs)
    successful_run_ids = [
        run.run_id
        for run in evidence_runs
        if run.successful
    ]

    admission_plan_outcome = None
    admission_plan_ready = False
    try:
        admission = build_admission_plan(candidate_id, runs_dir=runs_dir, skills_dir=skills_dir)
        admission_plan_outcome = admission.outcome
        admission_plan_ready = admission.ready_for_durable_review
    except AdmissionPlanError as exc:
        warnings.append(f"admission_plan_unavailable:{exc}")

    if evidence_runs and not any(run.successful for run in evidence_runs):
        warnings.append("baseline_comparison_missing")
    elif successful_run_ids:
        warnings.append("baseline_comparison_missing")

    return CandidateUsefulnessReport(
        candidate_id=entry.candidate_id,
        skill_name=entry.skill_name,
        capability=entry.capability,
        outcome=outcome,
        usefulness_supported=outcome == "usefulness_supported",
        successful_temporary_uses=entry.successful_temporary_uses,
        validation_pass_count=entry.validation_pass_count,
        validation_failure_count=entry.validation_failure_count,
        matching_successful_run_ids=successful_run_ids,
        evidence_runs=evidence_runs,
        admission_plan_outcome=admission_plan_outcome,
        admission_plan_ready=admission_plan_ready,
        blockers=blockers,
        warnings=_unique(warnings),
        next_steps=_next_steps(outcome, admission_plan_ready),
    )


def _run_log_index(
    runs_dir: Path,
    warnings: list[str],
) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(runs_dir.glob("run_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            warnings.append(f"run_log_unreadable:{path}")
            continue
        run_id = data.get("run_id")
        if run_id:
            records[str(run_id)] = {"path": str(path), "data": data}
    return records


def _evidence_run(
    entry: SkillCandidateLedgerEntry,
    run_id: str,
    run_logs: dict[str, dict[str, Any]],
) -> CandidateUsefulnessEvidenceRun:
    record = run_logs.get(run_id)
    if record is None:
        return CandidateUsefulnessEvidenceRun(run_id=run_id)

    data = record["data"]
    matching_request_ids: list[str] = []
    temporary_skill_paths: list[str] = []
    validation_values: list[bool] = []
    loaded_values: list[bool] = []

    for request in data.get("skill_requests") or []:
        if not isinstance(request, dict) or not _request_matches_entry(request, entry):
            continue
        request_id = request.get("id")
        if request_id:
            matching_request_ids.append(str(request_id))
        temporary = request.get("temporary_skill")
        if not isinstance(temporary, dict):
            continue
        skill_path = temporary.get("skill_path")
        if skill_path:
            temporary_skill_paths.append(str(skill_path))
        if temporary.get("validation_passed") is not None:
            validation_values.append(bool(temporary.get("validation_passed")))
        if temporary.get("loaded") is not None:
            loaded_values.append(bool(temporary.get("loaded")))

    validation_passed = any(validation_values) if validation_values else None
    loaded = any(loaded_values) if loaded_values else None
    result_category = (
        str(data["result_category"])
        if data.get("result_category") is not None
        else None
    )
    return CandidateUsefulnessEvidenceRun(
        run_id=run_id,
        run_log_path=record["path"],
        found=True,
        result_category=result_category,
        matching_request_ids=_unique(matching_request_ids),
        temporary_skill_paths=_unique(temporary_skill_paths),
        validation_passed=validation_passed,
        loaded=loaded,
        successful=bool(validation_passed and loaded and result_category == "success"),
        repair_requested=bool(result_category == "repair_requested"),
    )


def _request_matches_entry(
    request: dict[str, Any],
    entry: SkillCandidateLedgerEntry,
) -> bool:
    skill_name = str(request.get("desired_skill_name") or "requested-skill")
    capability = str(request.get("missing_capability") or skill_name)
    if candidate_id_for(skill_name, capability) == entry.candidate_id:
        return True
    return skill_name == entry.skill_name and capability == entry.capability


def _blockers(
    entry: SkillCandidateLedgerEntry,
    evidence_runs: list[CandidateUsefulnessEvidenceRun],
) -> list[str]:
    blockers: list[str] = []
    if entry.block_reason or entry.quarantine_reason or entry.status == "blocked":
        blockers.append("candidate_blocked")
    if entry.duplicate_of:
        blockers.append("candidate_duplicate")
    if not evidence_runs:
        blockers.append("candidate_evidence_runs_missing")
    if any(not run.found for run in evidence_runs):
        blockers.append("evidence_run_log_missing")
    if evidence_runs and not any(run.matching_request_ids for run in evidence_runs):
        blockers.append("matching_request_missing")
    if entry.repair_requirements:
        blockers.append("candidate_repair_required")
    return _unique(blockers)


def _outcome(
    entry: SkillCandidateLedgerEntry,
    blockers: list[str],
    evidence_runs: list[CandidateUsefulnessEvidenceRun],
) -> CandidateUsefulnessOutcome:
    if "candidate_blocked" in blockers or "candidate_duplicate" in blockers:
        return "blocked"
    if (
        "candidate_evidence_runs_missing" in blockers
        or "evidence_run_log_missing" in blockers
        or "matching_request_missing" in blockers
    ):
        return "evidence_missing"
    if "candidate_repair_required" in blockers or entry.validation_failure_count > 0:
        return "repair_required"
    if entry.successful_temporary_uses > 0 and any(run.successful for run in evidence_runs):
        return "usefulness_supported"
    return "needs_successful_temporary_use"


def _next_steps(
    outcome: CandidateUsefulnessOutcome,
    admission_plan_ready: bool,
) -> list[str]:
    if outcome == "usefulness_supported" and admission_plan_ready:
        return [
            "Review admission-plan and durable admission preview before any future write-mode work.",
            "Keep durable install/copy disabled until explicit human approval evidence exists.",
        ]
    if outcome == "usefulness_supported":
        return [
            "Record human promotion review or resolve admission blockers.",
            "Rerun candidate-usefulness and admission-plan after review evidence changes.",
        ]
    if outcome == "repair_required":
        return ["Repair the candidate evidence before durable admission review."]
    if outcome == "evidence_missing":
        return ["Recover or rerun missing temporary-skill evidence before review."]
    if outcome == "blocked":
        return ["Keep the candidate out of durable admission until blockers are cleared."]
    return ["Run the task with temporary skills enabled to gather usefulness evidence."]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
