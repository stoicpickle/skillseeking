from __future__ import annotations

from pathlib import Path

from app.input_focus import collect_input_request_queue
from app.input_resolution_ledger import InputResolutionLedgerError, append_input_request_resolution
from app.models import (
    InputRequest,
    InputRequestQueueItem,
    InputRequestResolutionClass,
    InputRequestResolutionDryRun,
    InputRequestStatus,
)


class InputResolutionError(ValueError):
    pass


DECISION_CLASS_BY_OPTION: dict[str, InputRequestResolutionClass] = {
    "approve_workflow": "approve",
    "revise_task": "revise",
    "approve_promotion": "approve",
    "approve_review": "approve",
    "repair_candidate": "repair",
    "reject_candidate": "reject",
    "defer": "defer",
    "block": "block",
    "recover_evidence": "recover",
    "merge_candidate": "merge",
    "keep_separate": "keep_separate",
}


def resolve_input_request(
    input_request_id: str,
    *,
    runs_dir: Path,
    decision: str,
    reviewer: str,
    notes: str,
    dry_run: bool = True,
) -> InputRequestResolutionDryRun:
    report = build_input_resolution_dry_run(
        input_request_id,
        runs_dir=runs_dir,
        decision=decision,
        reviewer=reviewer,
        notes=notes,
    )
    if dry_run:
        return report

    try:
        append_input_request_resolution(report, runs_dir)
    except InputResolutionLedgerError as exc:
        raise InputResolutionError(str(exc)) from exc
    return report.model_copy(
        update={
            "dry_run": False,
            "resolution_ledger_mutated": True,
        }
    )


def build_input_resolution_dry_run(
    input_request_id: str,
    *,
    runs_dir: Path,
    decision: str,
    reviewer: str,
    notes: str,
) -> InputRequestResolutionDryRun:
    if not decision.strip():
        raise InputResolutionError("decision is required for dry-run resolution")
    if not reviewer.strip():
        raise InputResolutionError("reviewer is required for dry-run resolution")
    if not notes.strip():
        raise InputResolutionError("notes are required for dry-run resolution")

    item = _find_input_request(input_request_id, runs_dir)
    request = item.request
    if decision not in request.options:
        allowed = ", ".join(request.options) if request.options else "-"
        raise InputResolutionError(
            f"decision {decision!r} is not valid for {input_request_id}; allowed: {allowed}"
        )

    resolution_class = DECISION_CLASS_BY_OPTION.get(decision)
    if resolution_class is None:
        raise InputResolutionError(f"decision {decision!r} is not supported")

    proposed_status = _proposed_status(resolution_class)
    return InputRequestResolutionDryRun(
        dry_run=True,
        input_request_id=input_request_id,
        decision=decision,
        resolution_class=resolution_class,
        proposed_status=proposed_status,
        reviewer=reviewer,
        notes=notes,
        request=request,
        sources=list(item.sources),
        remaining_blocked_scope=_remaining_blocked_scope(request, resolution_class),
        next_steps=_resolution_next_steps(request, decision),
    )


def _find_input_request(input_request_id: str, runs_dir: Path) -> InputRequestQueueItem:
    for item in collect_input_request_queue(runs_dir):
        if item.request.id == input_request_id:
            return item
    raise InputResolutionError(f"input request not found: {input_request_id}")


def _proposed_status(
    resolution_class: InputRequestResolutionClass,
) -> InputRequestStatus:
    return "open" if resolution_class == "defer" else "resolved"


def _remaining_blocked_scope(
    request: InputRequest,
    resolution_class: InputRequestResolutionClass,
) -> str | None:
    if resolution_class in {"approve", "recover", "merge", "keep_separate"}:
        return None
    return request.blocked_scope


def _resolution_next_steps(
    request: InputRequest,
    decision: str,
) -> list[str]:
    if decision == "approve_promotion" and request.related_candidate_id:
        return [
            f"Run skill-agent promote-candidate {request.related_candidate_id} with reviewer notes.",
            "Rerun skill-agent input-requests to inspect remaining gates.",
        ]
    if decision == "approve_review":
        return [
            "Record durable admission review evidence in the future resolution ledger.",
            "Do not copy or install durable skills in this dry-run slice.",
        ]
    if decision == "repair_candidate":
        return ["Repair the candidate evidence, then rerun the originating command."]
    if decision == "recover_evidence":
        return ["Recover missing evidence, then rerun skill-agent admission-plan."]
    if decision == "revise_task":
        return ["Revise the task and rerun only after the new request is explicit."]
    if decision == "reject_candidate":
        return ["Keep the candidate out of durable promotion."]
    if decision == "block":
        return ["Leave this gate blocked until a future review changes it."]
    if decision == "defer":
        return ["Leave this gate open for later human review."]
    return list(request.next_commands)
