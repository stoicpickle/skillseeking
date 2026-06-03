from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.models import (
    InputRequest,
    InputRequestKind,
    InputRequestQueueItem,
    InputRequestSource,
    SkillCandidateLedgerEntry,
)
from app.input_resolution_ledger import (
    InputResolutionLedgerError,
    input_request_resolution_ledger_path,
    latest_input_request_resolutions,
    load_input_request_resolution_ledger,
)
from app.skill_candidate_ledger import (
    SkillCandidateLedgerError,
    candidate_review_queue_names,
    ledger_path,
    load_candidate_ledger,
)


def safety_input_request(
    decision: dict[str, Any],
    run_id: str | None = None,
    created_at: datetime | None = None,
) -> InputRequest:
    capability = str(decision.get("capability") or "human approval")
    return InputRequest(
        id=_input_request_id("safety_approval", run_id, capability),
        kind="safety_approval",
        title=f"Approve safety boundary for {capability}",
        reason=str(decision.get("reason") or "This action requires human approval."),
        blocked_scope="current run execution",
        requested_decision="Approve a human-controlled workflow, change the task, or defer.",
        options=["approve_workflow", "revise_task", "defer"],
        recommended_option="approve_workflow",
        evidence_refs=[run_id] if run_id else [],
        next_commands=["Review the run log, then rerun only with explicit approval."],
        related_run_id=run_id,
        created_at=created_at or datetime.now(),
    )


def repair_input_request(
    repair: dict[str, Any],
    run_id: str | None = None,
    created_at: datetime | None = None,
) -> InputRequest:
    skill_name = str(repair.get("skill_name") or "temporary skill")
    request_id = repair.get("skill_request_id")
    reasons = repair.get("failure_reasons") or []
    reason = "; ".join(str(item) for item in reasons) or "Temporary skill repair is required."
    return InputRequest(
        id=_input_request_id("repair_review", run_id, request_id, skill_name),
        kind="repair_review",
        title=f"Review repair for {skill_name}",
        reason=reason,
        blocked_scope="temporary skill reuse and durable promotion",
        requested_decision="Repair, reject, or defer this candidate.",
        options=["repair_candidate", "reject_candidate", "defer"],
        recommended_option="repair_candidate",
        evidence_refs=[value for value in [run_id, str(request_id) if request_id else None] if value],
        next_commands=["Inspect the failed temporary SKILL.md and repair requirements."],
        related_run_id=run_id,
        related_skill_request_id=str(request_id) if request_id else None,
        created_at=created_at or datetime.now(),
    )


def candidate_input_requests(entry: SkillCandidateLedgerEntry) -> list[InputRequest]:
    requests: list[InputRequest] = []
    queues = set(candidate_review_queue_names(entry))
    if "promotion_ready" in queues:
        requests.append(
            _candidate_request(
                entry,
                kind="promotion_approval",
                title=f"Review {entry.skill_name} for candidate promotion",
                reason="Temporary evidence is ready for human promotion review.",
                blocked_scope="durable promotion only",
                requested_decision="Approve, repair, reject, or defer candidate promotion.",
                options=["approve_promotion", "repair_candidate", "reject_candidate", "defer"],
                recommended_option="approve_promotion",
                next_commands=[
                    f"skill-agent promote-candidate {entry.candidate_id} --reviewer <name> --notes <notes>"
                ],
            )
        )
    if "repair_needed" in queues:
        requests.append(
            _candidate_request(
                entry,
                kind="repair_review",
                title=f"Review repairs for {entry.skill_name}",
                reason="Candidate has validation failures or repair requirements.",
                blocked_scope="durable promotion and candidate admission",
                requested_decision="Repair, reject, or defer this candidate.",
                options=["repair_candidate", "reject_candidate", "defer"],
                recommended_option="repair_candidate",
                next_commands=["Inspect candidate repair requirements and source evidence."],
            )
        )
    if "duplicate_merge_needed" in queues:
        requests.append(
            _candidate_request(
                entry,
                kind="ambiguity_resolution",
                title=f"Resolve duplicate candidate {entry.skill_name}",
                reason=f"Candidate duplicates {entry.duplicate_of}.",
                blocked_scope="candidate merge and durable promotion",
                requested_decision="Merge, keep separate, reject, or defer.",
                options=["merge_candidate", "keep_separate", "reject_candidate", "defer"],
                recommended_option="merge_candidate",
                next_commands=["Inspect duplicate evidence before promotion review."],
            )
        )
    return requests


def admission_input_request(
    *,
    candidate_id: str,
    skill_name: str | None,
    outcome: str,
    blockers: list[str],
    evidence_refs: list[str],
) -> InputRequest | None:
    if outcome == "ready_for_durable_review":
        return InputRequest(
            id=_input_request_id("durable_admission_review", candidate_id, outcome),
            kind="durable_admission_review",
            title=f"Review durable admission for {skill_name or candidate_id}",
            reason="Candidate evidence is ready for human durable admission review.",
            blocked_scope="durable skill install/copy",
            requested_decision="Approve durable admission review, request repair, block, or defer.",
            options=["approve_review", "repair_candidate", "block", "defer"],
            recommended_option="approve_review",
            evidence_refs=evidence_refs,
            next_commands=["Prepare human durable admission review."],
            related_candidate_id=candidate_id,
        )
    if outcome == "needs_promotion_approval":
        return InputRequest(
            id=_input_request_id("promotion_approval", candidate_id, outcome),
            kind="promotion_approval",
            title=f"Approve candidate promotion for {skill_name or candidate_id}",
            reason="Promotion approval is required before durable admission review.",
            blocked_scope="durable admission review",
            requested_decision="Approve, repair, reject, or defer candidate promotion.",
            options=["approve_promotion", "repair_candidate", "reject_candidate", "defer"],
            recommended_option="approve_promotion",
            evidence_refs=evidence_refs,
            next_commands=[
                f"skill-agent promote-candidate {candidate_id} --reviewer <name> --notes <notes>"
            ],
            related_candidate_id=candidate_id,
        )
    if blockers:
        kind: InputRequestKind = (
            "missing_evidence" if outcome == "evidence_incomplete" else "durable_admission_review"
        )
        return InputRequest(
            id=_input_request_id(kind, candidate_id, *blockers),
            kind=kind,
            status="blocked",
            title=f"Resolve durable admission blockers for {skill_name or candidate_id}",
            reason="; ".join(blockers),
            blocked_scope="durable skill install/copy",
            requested_decision="Resolve blockers before durable admission review.",
            options=["repair_candidate", "recover_evidence", "block", "defer"],
            recommended_option="repair_candidate",
            evidence_refs=evidence_refs,
            next_commands=["Resolve blockers and rerun skill-agent admission-plan."],
            related_candidate_id=candidate_id,
        )
    return None


def collect_input_requests(runs_dir: Path) -> list[InputRequest]:
    return [item.request for item in collect_input_request_queue(runs_dir)]


def collect_input_request_queue(runs_dir: Path) -> list[InputRequestQueueItem]:
    items: list[InputRequestQueueItem] = []
    for path, log in _load_run_log_records(runs_dir):
        for request in input_requests_from_run_log(log):
            run_id = str(log.get("run_id") or "") or None
            items.append(
                InputRequestQueueItem(
                    request=request,
                    sources=[
                        InputRequestSource(
                            source_type="run_log",
                            source_path=str(path),
                            source_detail=run_id,
                        )
                    ],
                )
            )

    try:
        ledger = load_candidate_ledger(runs_dir)
    except SkillCandidateLedgerError:
        ledger = None
    if ledger is not None:
        path = str(ledger_path(runs_dir))
        for entry in ledger.entries:
            for request in candidate_input_requests(entry):
                items.append(
                    InputRequestQueueItem(
                        request=request,
                        sources=[
                            InputRequestSource(
                                source_type="candidate_ledger",
                                source_path=path,
                                source_detail=entry.candidate_id,
                            )
                        ],
                    )
                )

    return _apply_resolution_ledger(_dedupe_queue_items(items), runs_dir)


def input_request_source_warnings(runs_dir: Path) -> list[str]:
    warnings: list[str] = []
    try:
        load_candidate_ledger(runs_dir)
    except SkillCandidateLedgerError as exc:
        warnings.append(f"candidate ledger unavailable: {exc}")
    try:
        load_input_request_resolution_ledger(runs_dir)
    except InputResolutionLedgerError as exc:
        warnings.append(f"resolution ledger unavailable: {exc}")
    return warnings


def input_request_kind_counts(requests: list[InputRequest]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for request in requests:
        counts[request.kind] = counts.get(request.kind, 0) + 1
    return dict(sorted(counts.items()))


def input_requests_from_run_log(log: dict[str, Any]) -> list[InputRequest]:
    run_id = str(log.get("run_id") or "") or None
    created_at = _parse_datetime(log.get("created_at"))
    parsed: list[InputRequest] = []
    for item in log.get("input_requests") or []:
        if isinstance(item, dict):
            try:
                parsed.append(InputRequest.model_validate(item))
            except ValidationError:
                continue

    for decision in log.get("capability_decisions") or []:
        if isinstance(decision, dict) and decision.get("decision") == "ASK_HUMAN":
            parsed.append(safety_input_request(decision, run_id, created_at))
    for repair in log.get("skill_repair_requests") or []:
        if isinstance(repair, dict):
            parsed.append(repair_input_request(repair, run_id, created_at))
    return _dedupe_requests(parsed)


def _candidate_request(
    entry: SkillCandidateLedgerEntry,
    *,
    kind: InputRequestKind,
    title: str,
    reason: str,
    blocked_scope: str,
    requested_decision: str,
    options: list[str],
    recommended_option: str,
    next_commands: list[str],
) -> InputRequest:
    return InputRequest(
        id=_input_request_id(kind, entry.candidate_id),
        kind=kind,
        title=title,
        reason=reason,
        blocked_scope=blocked_scope,
        requested_decision=requested_decision,
        options=options,
        recommended_option=recommended_option,
        evidence_refs=list(entry.evidence_run_ids),
        next_commands=next_commands,
        related_candidate_id=entry.candidate_id,
        created_at=entry.updated_at,
    )


def _load_run_log_records(runs_dir: Path) -> list[tuple[Path, dict[str, Any]]]:
    logs: list[tuple[Path, dict[str, Any]]] = []
    if not runs_dir.exists():
        return logs
    for path in sorted(runs_dir.rglob("run_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict):
            logs.append((path, data))
    return logs


def _dedupe_requests(requests: list[InputRequest]) -> list[InputRequest]:
    deduped: dict[str, InputRequest] = {}
    for request in requests:
        deduped.setdefault(request.id, request)
    return sorted(deduped.values(), key=lambda item: (item.kind, item.id))


def _dedupe_queue_items(items: list[InputRequestQueueItem]) -> list[InputRequestQueueItem]:
    deduped: dict[str, InputRequestQueueItem] = {}
    for item in items:
        existing = deduped.get(item.request.id)
        if existing is None:
            deduped[item.request.id] = item
            continue
        known = {
            (source.source_type, source.source_path, source.source_detail)
            for source in existing.sources
        }
        for source in item.sources:
            key = (source.source_type, source.source_path, source.source_detail)
            if key not in known:
                existing.sources.append(source)
                known.add(key)
    return sorted(deduped.values(), key=lambda item: (item.request.kind, item.request.id))


def _apply_resolution_ledger(
    items: list[InputRequestQueueItem],
    runs_dir: Path,
) -> list[InputRequestQueueItem]:
    try:
        ledger = load_input_request_resolution_ledger(runs_dir)
    except InputResolutionLedgerError:
        return items
    latest = latest_input_request_resolutions(ledger)
    if not latest:
        return items

    source_path = str(input_request_resolution_ledger_path(runs_dir))
    for item in items:
        resolution = latest.get(item.request.id)
        if resolution is None:
            continue
        item.request.status = resolution.status
        item.sources.append(
            InputRequestSource(
                source_type="resolution_ledger",
                source_path=source_path,
                source_detail=resolution.decision,
            )
        )
    return items


def _input_request_id(*parts: object) -> str:
    text = "|".join(str(part) for part in parts if part is not None)
    return f"inputreq_{hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]}"


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
