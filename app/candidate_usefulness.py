from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.admission_plan import AdmissionPlanError, build_admission_plan
from app.models import (
    CandidateUsefulnessComparison,
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
    baseline_run_id: str | None = None,
    treatment_run_id: str | None = None,
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
    comparison_requested = baseline_run_id is not None or treatment_run_id is not None
    comparison = _comparison(
        entry,
        run_logs,
        baseline_run_id=baseline_run_id,
        treatment_run_id=(
            treatment_run_id
            or (successful_run_ids[0] if comparison_requested and successful_run_ids else None)
        ),
    )
    if comparison is None:
        warnings.append("baseline_comparison_missing")
    elif comparison.blockers:
        warnings.append("baseline_comparison_invalid")

    admission_plan_outcome = None
    admission_plan_ready = False
    try:
        admission = build_admission_plan(candidate_id, runs_dir=runs_dir, skills_dir=skills_dir)
        admission_plan_outcome = admission.outcome
        admission_plan_ready = admission.ready_for_durable_review
    except AdmissionPlanError as exc:
        warnings.append(f"admission_plan_unavailable:{exc}")

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
        baseline_comparison_available=bool(comparison and not comparison.blockers),
        comparison=comparison,
        admission_plan_outcome=admission_plan_outcome,
        admission_plan_ready=admission_plan_ready,
        blockers=blockers,
        warnings=_unique(warnings),
        next_steps=_next_steps(outcome, admission_plan_ready),
    )


def _comparison(
    entry: SkillCandidateLedgerEntry,
    run_logs: dict[str, dict[str, Any]],
    *,
    baseline_run_id: str | None,
    treatment_run_id: str | None,
) -> CandidateUsefulnessComparison | None:
    if baseline_run_id is None and treatment_run_id is None:
        return None
    if baseline_run_id is None or treatment_run_id is None:
        missing_id = baseline_run_id or treatment_run_id or ""
        return CandidateUsefulnessComparison(
            baseline_run_id=baseline_run_id or "",
            treatment_run_id=treatment_run_id or "",
            outcome="invalid_comparison",
            blockers=["baseline_and_treatment_run_ids_required"],
            summary=(
                "Pinned baseline and treatment run IDs are required for paired "
                f"comparison; only {missing_id or 'no run ID'} was provided."
            ),
        )

    baseline = _run_observation(entry, baseline_run_id, run_logs)
    treatment = _run_observation(entry, treatment_run_id, run_logs)
    blockers: list[str] = []
    warnings: list[str] = []

    if not baseline["found"]:
        blockers.append("baseline_run_log_missing")
    if not treatment["found"]:
        blockers.append("treatment_run_log_missing")
    if baseline["temporary_skill_present"]:
        blockers.append("baseline_uses_candidate_skill")
    if baseline["found"] and not baseline["matches_candidate_request"]:
        blockers.append("baseline_run_not_matching_candidate")
    if treatment["found"] and not treatment["matches_candidate_request"]:
        blockers.append("treatment_run_not_matching_candidate")
    if treatment["found"] and not treatment["temporary_skill_present"]:
        blockers.append("treatment_missing_candidate_temporary_skill")
    if treatment["found"] and not treatment["temporary_skill_loaded"]:
        blockers.append("treatment_missing_candidate_temporary_skill")
    if treatment["found"] and treatment["result_category"] != "success":
        blockers.append("treatment_not_successful")

    outcome = _comparison_outcome(baseline, treatment, blockers)
    return CandidateUsefulnessComparison(
        baseline_run_id=baseline_run_id,
        baseline_run_log_path=baseline["run_log_path"],
        baseline_result_category=baseline["result_category"],
        baseline_exit_code=baseline["exit_code"],
        baseline_matches_candidate_request=baseline["matches_candidate_request"],
        baseline_temporary_skill_present=baseline["temporary_skill_present"],
        baseline_temporary_skill_loaded=baseline["temporary_skill_loaded"],
        treatment_run_id=treatment_run_id,
        treatment_run_log_path=treatment["run_log_path"],
        treatment_result_category=treatment["result_category"],
        treatment_exit_code=treatment["exit_code"],
        treatment_matches_candidate_request=treatment["matches_candidate_request"],
        treatment_temporary_skill_present=treatment["temporary_skill_present"],
        treatment_temporary_skill_loaded=treatment["temporary_skill_loaded"],
        outcome=outcome,
        blockers=_unique(blockers),
        warnings=_unique(warnings),
        summary=_comparison_summary(outcome, baseline, treatment, blockers),
    )


def _run_observation(
    entry: SkillCandidateLedgerEntry,
    run_id: str,
    run_logs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    record = run_logs.get(run_id)
    if record is None:
        return {
            "found": False,
            "run_log_path": None,
            "result_category": None,
            "exit_code": None,
            "matches_candidate_request": False,
            "temporary_skill_present": False,
            "temporary_skill_loaded": False,
        }

    data = record["data"]
    matches_candidate_request = False
    temporary_skill_present = False
    temporary_skill_loaded = False
    for request in data.get("skill_requests") or []:
        if not isinstance(request, dict) or not _request_matches_entry(request, entry):
            continue
        matches_candidate_request = True
        temporary = request.get("temporary_skill")
        if isinstance(temporary, dict):
            temporary_skill_present = True
            if bool(temporary.get("loaded")):
                temporary_skill_loaded = True

    return {
        "found": True,
        "run_log_path": record["path"],
        "result_category": (
            str(data["result_category"])
            if data.get("result_category") is not None
            else None
        ),
        "exit_code": int(data["exit_code"]) if data.get("exit_code") is not None else None,
        "matches_candidate_request": matches_candidate_request,
        "temporary_skill_present": temporary_skill_present,
        "temporary_skill_loaded": temporary_skill_loaded,
    }


def _comparison_outcome(
    baseline: dict[str, Any],
    treatment: dict[str, Any],
    blockers: list[str],
) -> str:
    if blockers:
        return "invalid_comparison"
    baseline_result = baseline["result_category"]
    treatment_result = treatment["result_category"]
    if baseline_result != "success" and treatment_result == "success":
        return "improved"
    if baseline_result == "success" and treatment_result != "success":
        return "regressed"
    return "no_clear_improvement"


def _comparison_summary(
    outcome: str,
    baseline: dict[str, Any],
    treatment: dict[str, Any],
    blockers: list[str],
) -> str:
    if blockers:
        return "Comparison is unavailable until blockers are resolved."
    if outcome == "improved":
        return (
            "Treatment succeeded with the candidate temporary skill while the "
            f"baseline ended as {baseline['result_category'] or 'unknown'}."
        )
    if outcome == "regressed":
        return (
            "Treatment did not preserve the baseline success result; do not use "
            "this pair as admission evidence."
        )
    return (
        "Baseline and treatment do not show clear causal improvement from this "
        "single pinned pair."
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
