from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.input_focus import input_requests_from_run_log
from app.skill_candidate_ledger import (
    SkillCandidateLedgerError,
    candidate_id_for,
    ledger_path,
    load_candidate_ledger,
)


class ExplainError(ValueError):
    pass


def explain_run_log(path: Path, include_candidates: bool = False) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ExplainError(f"Run log not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ExplainError(f"Run log is not valid JSON: {exc.msg}") from exc

    lines = [
        "RUN",
        f"Run ID: {data.get('run_id', '-')}",
        f"Task ID: {data.get('task_id', '-')}",
        f"Result: {data.get('result_category', '-')}",
        f"Task: {data.get('task', '-')}",
        "",
        "CAPABILITIES",
    ]
    for capability in data.get("plan") or []:
        lines.append(f"- {capability}")
    if not data.get("plan"):
        lines.append("- none recorded")

    lines.extend(["", "DECISIONS"])
    decisions = data.get("capability_decisions") or []
    for decision in decisions:
        lines.extend(_decision_lines(decision))
    if not decisions:
        lines.append("- none recorded")

    lines.extend(["", "GOVERNOR"])
    governor_decisions = data.get("governor_decisions") or []
    for governor in governor_decisions:
        lines.extend(_governor_lines(governor))
    if not governor_decisions:
        lines.append("- none recorded")

    lines.extend(["", "SKILL REQUESTS"])
    requests = data.get("skill_requests") or []
    for request in requests:
        lines.append(
            f"- {request.get('desired_skill_name', '-')} for {request.get('missing_capability', '-')}"
        )
        lines.append(f"  Risk: {request.get('risk_level', '-')}")
        if request.get("success_criteria"):
            lines.append(f"  Success: {request['success_criteria'][0]}")
    if not requests:
        lines.append("- none")

    lines.extend(["", "INPUT NEEDED"])
    input_requests = input_requests_from_run_log(data)
    for request in input_requests:
        lines.append(f"- {request.kind}: {request.title}")
        lines.append(f"  Status: {request.status}")
        lines.append(f"  Blocked scope: {request.blocked_scope}")
        lines.append(f"  Requested decision: {request.requested_decision}")
        if request.recommended_option:
            lines.append(f"  Recommended option: {request.recommended_option}")
        if request.next_commands:
            lines.append(f"  Suggested command: {request.next_commands[0]}")
    if not input_requests:
        lines.append("- none")

    if include_candidates:
        lines.extend(_candidate_ledger_lines(path, data))

    lines.extend(["", "SAFETY"])
    safety = [
        decision for decision in decisions if decision.get("decision") in {"ASK_HUMAN", "ABORT_UNSAFE"}
    ]
    for decision in safety:
        lines.append(f"- {decision.get('decision')}: {decision.get('reason')}")
    if not safety:
        lines.append("- no safety stop")

    lines.extend(["", "TRACE"])
    for stage in data.get("trace") or []:
        lines.append(f"- {stage}")
    if not data.get("trace"):
        lines.append("- none recorded")

    return "\n".join(lines) + "\n"


def _candidate_ledger_lines(run_log_path: Path, data: dict[str, Any]) -> list[str]:
    lines = ["", "CANDIDATE LEDGER"]
    try:
        ledger = load_candidate_ledger(run_log_path.parent)
    except SkillCandidateLedgerError as exc:
        return lines + [f"- unavailable: {exc}"]
    path = ledger_path(run_log_path.parent)
    lines.append(f"Ledger: {path}")
    entries_by_id = {entry.candidate_id: entry for entry in ledger.entries}
    run_id = str(data.get("run_id") or "")
    matched_ids: list[str] = []
    for request in data.get("skill_requests") or []:
        skill_name = str(request.get("desired_skill_name") or "requested-skill")
        capability = str(request.get("missing_capability") or skill_name)
        matched_ids.append(candidate_id_for(skill_name, capability))
    for entry in ledger.entries:
        if run_id and run_id in entry.evidence_run_ids:
            matched_ids.append(entry.candidate_id)
    matched = [entries_by_id[candidate_id] for candidate_id in dict.fromkeys(matched_ids) if candidate_id in entries_by_id]
    if not matched:
        lines.append("- no matching candidate entry")
        return lines
    for entry in matched:
        lines.append(f"- {entry.candidate_id}: {entry.skill_name} for {entry.capability}")
        lines.append(f"  Status: {entry.status}")
        lines.append(f"  Requests: {entry.request_count}")
        lines.append(
            "  Validation: "
            f"passed={entry.validation_pass_count} failed={entry.validation_failure_count} "
            f"temporary_uses={entry.successful_temporary_uses}"
        )
        if entry.quarantine_reason:
            lines.append(f"  Quarantine reason: {entry.quarantine_reason}")
        if entry.block_reason:
            lines.append(f"  Block reason: {entry.block_reason}")
        if entry.duplicate_of:
            lines.append(f"  Duplicate of: {entry.duplicate_of}")
        if entry.repair_requirements:
            lines.append(f"  Repair requirements: {'; '.join(entry.repair_requirements)}")
        if entry.promotion_requirements:
            lines.append(f"  Promotion requirements: {'; '.join(entry.promotion_requirements)}")
        lines.append(f"  Promotion approval required: {entry.human_approval_required}")
        if entry.promotion_approved_by:
            lines.append(f"  Promotion approved by: {entry.promotion_approved_by}")
        if entry.promotion_approved_at:
            lines.append(f"  Promotion approved at: {entry.promotion_approved_at.isoformat()}")
        if entry.promotion_approval_notes:
            lines.append(f"  Promotion approval notes: {entry.promotion_approval_notes}")
        lines.append(f"  Evidence runs: {', '.join(entry.evidence_run_ids) or '-'}")
    return lines



def _decision_lines(decision: dict[str, Any]) -> list[str]:
    selected = decision.get("selected_skill") or "-"
    lines = [
        f"- {decision.get('decision', '-')} {selected} :: {decision.get('capability', '-')}",
        f"  Reason: {decision.get('reason', '-')}",
    ]
    best = decision.get("best_match") or {}
    if best:
        lines.append(
            f"  Best match: {best.get('skill_name') or '-'} ({best.get('score', 0):.2f}, {best.get('coverage', '-')})"
        )
    candidates = decision.get("ranked_candidates") or []
    if candidates:
        lines.append("  Candidates:")
        for candidate in candidates[:5]:
            marker = "selected" if candidate.get("selected") else "considered"
            lines.append(
                f"  - {candidate.get('skill_name', '-')} {candidate.get('score', 0):.2f} {marker}"
            )
    return lines


def _governor_lines(governor: dict[str, Any]) -> list[str]:
    return [
        f"- {governor.get('decision', '-')} :: {governor.get('capability', '-')}",
        f"  Confidence: {governor.get('confidence', 0):.2f}",
        f"  Risk: {governor.get('risk_level', '-')}",
        f"  Approval required: {governor.get('approval_required', False)}",
        f"  Reversibility: {governor.get('reversibility', '-')}",
        f"  Dominant signal: {governor.get('dominant_signal', '-')}",
        f"  Reason: {governor.get('reason', '-')}",
    ]
