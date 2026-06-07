from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.evidence_checkpoint import (
    EvidenceCheckpointError,
    build_evidence_checkpoint_report,
    collect_evidence_files,
    load_evidence_checkpoint_ledger,
)
from app.input_focus import (
    collect_input_request_queue,
    input_request_kind_counts,
    input_request_source_warnings,
)
from app.models import (
    CandidateReviewQueueItem,
    EvidenceCheckpointFile,
    InputRequestQueueItem,
    NegativeEvidenceItem,
    OperatorCheckpointSummary,
    OperatorDecisionItem,
    OperatorSummarySection,
    OperatorSummarySeverity,
    OperatorSummaryItem,
    OperatorSummaryReport,
)
from app.negative_evidence import build_negative_evidence_report
from app.skill_candidate_ledger import (
    SkillCandidateLedgerError,
    candidate_review_queue_counts,
    candidate_review_queues,
    ledger_path,
    load_candidate_ledger,
)

_SEVERITY_RANK = {"blocker": 0, "warning": 1, "info": 2}


def build_operator_summary_report(*, runs_dir: Path) -> OperatorSummaryReport:
    active_queue = [
        item
        for item in collect_input_request_queue(runs_dir)
        if item.request.status != "resolved"
    ]
    human_input_items = [_input_request_item(item) for item in active_queue]
    blocked_items = [
        _input_request_item(item, section="blocked", severity="blocker")
        for item in active_queue
        if item.request.status == "blocked"
    ]
    missing_evidence_items = [
        _input_request_item(item, section="missing_evidence")
        for item in active_queue
        if item.request.kind == "missing_evidence"
    ]
    unsafe_or_negative_items = [
        _input_request_item(
            item,
            section="unsafe_or_negative",
            severity="blocker" if item.request.status == "blocked" else "warning",
        )
        for item in active_queue
        if item.request.kind == "safety_approval"
    ]

    warnings = input_request_source_warnings(runs_dir)
    candidate_count = 0
    candidate_status_counts: dict[str, int] = {}
    queue_counts: dict[str, int] = {}
    promotion_ready_items: list[OperatorSummaryItem] = []
    try:
        ledger = load_candidate_ledger(runs_dir)
    except SkillCandidateLedgerError as exc:
        ledger = None
        warnings.append(f"candidate ledger unavailable: {exc}")

    if ledger is not None:
        candidate_count = len(ledger.entries)
        for entry in ledger.entries:
            candidate_status_counts[entry.status] = candidate_status_counts.get(entry.status, 0) + 1
            if entry.safety_flags:
                unsafe_or_negative_items.append(
                    OperatorSummaryItem(
                        section="unsafe_or_negative",
                        severity="warning",
                        id=f"candidate_safety_flags:{entry.candidate_id}",
                        title=f"Safety flags for {entry.skill_name}",
                        reason="; ".join(entry.safety_flags),
                        status=entry.status,
                        source_type="candidate_queue",
                        source_path=str(ledger_path(runs_dir)),
                        source_detail=entry.candidate_id,
                        candidate_id=entry.candidate_id,
                        skill_name=entry.skill_name,
                        evidence_refs=list(entry.evidence_run_ids),
                        warnings=list(entry.safety_flags),
                        created_at=entry.updated_at,
                    )
                )

        queues = candidate_review_queues(ledger)
        queue_counts = dict(candidate_review_queue_counts(ledger))
        promotion_ready_items = [
            _candidate_queue_item(item, section="promotion_ready")
            for item in queues["promotion_ready"]
        ]
        blocked_items.extend(
            _candidate_queue_item(item, section="blocked", severity="blocker")
            for item in queues["blocked_or_quarantined"]
        )
        blocked_items.extend(
            _candidate_queue_item(item, section="blocked", severity="warning")
            for item in queues["repair_needed"]
        )
        blocked_items.extend(
            _candidate_queue_item(item, section="blocked", severity="warning")
            for item in queues["duplicate_merge_needed"]
        )
        missing_evidence_items.extend(
            _candidate_queue_item(item, section="missing_evidence", severity="warning")
            for item in queues["repeated_requested_gap"]
        )

    negative_report = build_negative_evidence_report(runs_dir=runs_dir)
    negative_items = [_negative_evidence_item(item) for item in negative_report.items]
    unsafe_or_negative_items.extend(negative_items)
    blocked_items.extend(
        _negative_evidence_item(item, section="blocked", severity="blocker")
        for item in negative_report.items
        if item.evidence_type in {"resolution_block", "candidate_blocked"}
    )
    unsafe_or_negative_items.extend(_unsafe_abort_items(runs_dir))

    checkpoint, checkpoint_items, checkpoint_warnings = _checkpoint_summary(runs_dir)
    warnings.extend(checkpoint_warnings)

    blocked_items = _sort_items(blocked_items)
    human_input_items = _sort_items(human_input_items)
    promotion_ready_items = _sort_items(promotion_ready_items)
    missing_evidence_items = _sort_items(missing_evidence_items)
    unsafe_or_negative_items = _sort_items(unsafe_or_negative_items)
    checkpoint_items = _sort_items(checkpoint_items)
    operator_decisions = _operator_decisions(
        runs_dir=runs_dir,
        blocked_items=blocked_items,
        human_input_items=human_input_items,
        promotion_ready_items=promotion_ready_items,
        missing_evidence_items=missing_evidence_items,
        unsafe_or_negative_items=unsafe_or_negative_items,
        checkpoint_items=checkpoint_items,
        checkpoint=checkpoint,
    )

    return OperatorSummaryReport(
        runs_dir=str(runs_dir),
        input_request_count=len(active_queue),
        input_request_kind_counts=input_request_kind_counts([item.request for item in active_queue]),
        candidate_count=candidate_count,
        candidate_status_counts=dict(sorted(candidate_status_counts.items())),
        candidate_review_queue_counts=dict(sorted(queue_counts.items())),
        negative_evidence_count=negative_report.evidence_count,
        negative_evidence_counts_by_type=negative_report.counts_by_type,
        blocked_items=blocked_items,
        human_input_items=human_input_items,
        promotion_ready_candidates=promotion_ready_items,
        missing_evidence_items=missing_evidence_items,
        unsafe_or_negative_items=unsafe_or_negative_items,
        checkpoint_change_items=checkpoint_items,
        checkpoint=checkpoint,
        operator_decisions=operator_decisions,
        warnings=sorted(set(warnings)),
        next_steps=_next_steps(
            runs_dir=runs_dir,
            blocked_items=blocked_items,
            human_input_items=human_input_items,
            promotion_ready_items=promotion_ready_items,
            missing_evidence_items=missing_evidence_items,
            unsafe_or_negative_items=unsafe_or_negative_items,
            checkpoint=checkpoint,
        ),
    )


def _input_request_item(
    item: InputRequestQueueItem,
    *,
    section: OperatorSummarySection = "human_input",
    severity: OperatorSummarySeverity = "warning",
) -> OperatorSummaryItem:
    request = item.request
    source = item.sources[0] if item.sources else None
    return OperatorSummaryItem(
        section=section,
        severity=severity,
        id=f"{section}:{request.id}",
        title=request.title,
        reason=request.reason,
        status=request.status,
        source_type="input_request",
        source_path=source.source_path if source else None,
        source_detail=source.source_detail if source else None,
        candidate_id=request.related_candidate_id,
        input_request_id=request.id,
        evidence_refs=list(request.evidence_refs),
        next_commands=list(request.next_commands),
        blockers=[request.blocked_scope] if request.status == "blocked" else [],
        created_at=request.created_at,
    )


def _candidate_queue_item(
    item: CandidateReviewQueueItem,
    *,
    section: OperatorSummarySection,
    severity: OperatorSummarySeverity = "warning",
) -> OperatorSummaryItem:
    return OperatorSummaryItem(
        section=section,
        severity=severity,
        id=f"{section}:{item.queue}:{item.candidate_id}",
        title=f"{item.skill_name} in {item.queue}",
        reason=item.reason,
        status=item.status,
        source_type="candidate_queue",
        source_path=None,
        source_detail=item.queue,
        candidate_id=item.candidate_id,
        skill_name=item.skill_name,
        evidence_refs=list(item.evidence_run_ids),
        next_commands=[f"skill-agent candidate-decision {item.candidate_id}"],
        blockers=[item.reason] if severity == "blocker" else [],
    )


def _negative_evidence_item(
    item: NegativeEvidenceItem,
    *,
    section: OperatorSummarySection = "unsafe_or_negative",
    severity: OperatorSummarySeverity = "warning",
) -> OperatorSummaryItem:
    return OperatorSummaryItem(
        section=section,
        severity=severity,
        id=f"{section}:{item.id}",
        title=item.evidence_type,
        reason=item.reason,
        status=item.status,
        source_type="negative_evidence",
        source_path=item.source,
        source_detail=item.evidence_type,
        candidate_id=item.candidate_id,
        skill_name=item.skill_name,
        input_request_id=item.input_request_id,
        evidence_refs=list(item.evidence_refs),
        blockers=[item.remaining_blocked_scope] if item.remaining_blocked_scope else [],
        warnings=[item.notes] if item.notes else [],
        created_at=item.created_at,
    )


def _unsafe_abort_items(runs_dir: Path) -> list[OperatorSummaryItem]:
    if not runs_dir.exists():
        return []
    items: list[OperatorSummaryItem] = []
    for path in sorted(runs_dir.rglob("run_*.json")):
        if not path.is_file():
            continue
        try:
            log = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        run_id = str(log.get("run_id") or path.stem)
        if log.get("result_category") == "unsafe_aborted":
            items.append(
                OperatorSummaryItem(
                    section="unsafe_or_negative",
                    severity="blocker",
                    id=f"run_log_unsafe:{run_id}",
                    title="Unsafe run aborted",
                    reason="Run result category is unsafe_aborted.",
                    status="unsafe_aborted",
                    source_type="run_log",
                    source_path=str(path),
                    source_detail=run_id,
                    evidence_refs=[run_id],
                    next_commands=[f"skill-agent explain {path}"],
                )
            )
        for index, decision in enumerate(log.get("capability_decisions") or []):
            if isinstance(decision, dict) and decision.get("decision") == "ABORT_UNSAFE":
                reason = str(decision.get("reason") or "Capability decision aborted as unsafe.")
                items.append(
                    OperatorSummaryItem(
                        section="unsafe_or_negative",
                        severity="blocker",
                        id=f"run_log_abort_unsafe:{run_id}:{index}",
                        title="Unsafe capability decision",
                        reason=reason,
                        status="ABORT_UNSAFE",
                        source_type="run_log",
                        source_path=str(path),
                        source_detail=run_id,
                        evidence_refs=[run_id],
                        next_commands=[f"skill-agent explain {path}"],
                    )
                )
    return items


def _checkpoint_summary(
    runs_dir: Path,
) -> tuple[OperatorCheckpointSummary, list[OperatorSummaryItem], list[str]]:
    try:
        verify_report = build_evidence_checkpoint_report(runs_dir=runs_dir, verify=True)
        ledger = load_evidence_checkpoint_ledger(runs_dir)
        current_files = collect_evidence_files(runs_dir)
    except EvidenceCheckpointError as exc:
        return (
            OperatorCheckpointSummary(
                status="checkpoint_unavailable",
                blockers=[str(exc)],
                warnings=[str(exc)],
            ),
            [
                OperatorSummaryItem(
                    section="checkpoint_change",
                    severity="blocker",
                    id="checkpoint_unavailable",
                    title="Checkpoint unavailable",
                    reason=str(exc),
                    status="checkpoint_unavailable",
                    source_type="checkpoint",
                    source_path=str(runs_dir / "evidence_checkpoints.json"),
                    source_detail="checkpoint_unavailable",
                    blockers=[str(exc)],
                    next_commands=[
                        f"skill-agent evidence-checkpoint --runs-dir {runs_dir} --verify"
                    ],
                )
            ],
            [f"checkpoint unavailable: {exc}"],
        )

    latest = ledger.checkpoints[-1] if ledger.checkpoints else None
    added: list[str] = []
    changed: list[str] = []
    removed: list[str] = []
    if latest is None:
        status = "no_checkpoint"
        added = sorted(file.path for file in current_files)
    else:
        added, changed, removed = _checkpoint_file_diffs(
            current_files=current_files,
            checkpoint_files=latest.evidence_files,
        )
        if any(blocker != "current_evidence_differs_from_latest_checkpoint" for blocker in verify_report.blockers):
            status = "checkpoint_blocked"
        elif added or changed or removed:
            status = "differs_from_latest"
        else:
            status = "matches_latest"

    items = [
        *_checkpoint_file_items("added", added),
        *_checkpoint_file_items("changed", changed),
        *_checkpoint_file_items("removed", removed),
    ]
    summary = OperatorCheckpointSummary(
        status=status,  # type: ignore[arg-type]
        latest_checkpoint_present=latest is not None,
        latest_checkpoint_id=latest.id if latest is not None else None,
        latest_checkpoint_hash=latest.checkpoint_hash if latest is not None else None,
        checkpoint_count=len(ledger.checkpoints),
        chain_valid=verify_report.chain_valid,
        current_evidence_matches_latest=verify_report.current_evidence_matches_latest,
        current_evidence_file_count=len(current_files),
        checkpoint_evidence_file_count=latest.evidence_file_count if latest is not None else 0,
        added_count=len(added),
        changed_count=len(changed),
        removed_count=len(removed),
        added_files=added,
        changed_files=changed,
        removed_files=removed,
        blockers=list(verify_report.blockers),
        warnings=list(verify_report.warnings),
    )
    return summary, items, list(verify_report.warnings)


def _checkpoint_file_diffs(
    *,
    current_files: list[EvidenceCheckpointFile],
    checkpoint_files: list[EvidenceCheckpointFile],
) -> tuple[list[str], list[str], list[str]]:
    current_by_path = {file.path: file for file in current_files}
    checkpoint_by_path = {file.path: file for file in checkpoint_files}
    current_paths = set(current_by_path)
    checkpoint_paths = set(checkpoint_by_path)
    added = sorted(current_paths - checkpoint_paths)
    removed = sorted(checkpoint_paths - current_paths)
    changed = sorted(
        path
        for path in current_paths & checkpoint_paths
        if current_by_path[path].sha256 != checkpoint_by_path[path].sha256
    )
    return added, changed, removed


def _checkpoint_file_items(change_type: str, paths: list[str]) -> list[OperatorSummaryItem]:
    severity: OperatorSummarySeverity = "info" if change_type == "added" else "warning"
    return [
        OperatorSummaryItem(
            section="checkpoint_change",
            severity=severity,
            id=f"checkpoint_{change_type}:{path}",
            title=f"Checkpoint evidence {change_type}",
            reason=f"{path} is {change_type} since the latest checkpoint.",
            status=change_type,
            source_type="checkpoint",
            source_path=path,
            source_detail=change_type,
            evidence_refs=[path],
        )
        for path in paths
    ]


def _operator_decisions(
    *,
    runs_dir: Path,
    blocked_items: list[OperatorSummaryItem],
    human_input_items: list[OperatorSummaryItem],
    promotion_ready_items: list[OperatorSummaryItem],
    missing_evidence_items: list[OperatorSummaryItem],
    unsafe_or_negative_items: list[OperatorSummaryItem],
    checkpoint_items: list[OperatorSummaryItem],
    checkpoint: OperatorCheckpointSummary,
) -> list[OperatorDecisionItem]:
    runs_arg = f"--runs-dir {runs_dir}"
    decisions: list[OperatorDecisionItem] = []

    blocker_items = [
        item for item in blocked_items + unsafe_or_negative_items if item.severity == "blocker"
    ]
    checkpoint_unavailable_items = [
        item for item in checkpoint_items if item.status == "checkpoint_unavailable"
    ]
    if blocker_items or checkpoint.status == "checkpoint_unavailable":
        support_commands = [
            *(command for item in blocker_items for command in item.next_commands),
            *(command for item in checkpoint_unavailable_items for command in item.next_commands),
        ]
        if human_input_items:
            support_commands.append(f"skill-agent input-requests {runs_arg}")
        if checkpoint.status == "checkpoint_unavailable":
            support_commands.append(
                f"skill-agent evidence-checkpoint {runs_arg} --verify"
            )
        primary_command = _first_command(
            [
                *(item.next_commands for item in blocker_items if item.source_type == "run_log"),
                *(item.next_commands for item in checkpoint_unavailable_items),
                *(item.next_commands for item in blocker_items if item.source_type != "run_log"),
                [f"skill-agent input-requests {runs_arg}"] if human_input_items else [],
                [f"skill-agent evidence-checkpoint {runs_arg} --verify"]
                if checkpoint.status == "checkpoint_unavailable"
                else [],
            ]
        )
        decisions.append(
            OperatorDecisionItem(
                priority=10,
                severity="blocker",
                decision="resolve_blockers",
                title="Resolve unsafe or blocked evidence",
                reason="Unsafe, blocked, or unavailable evidence must be resolved before promotion or stable-use review.",
                primary_command=primary_command,
                supporting_commands=_unique(support_commands),
                source_item_ids=[item.id for item in blocker_items + checkpoint_unavailable_items],
                blockers=_unique(
                    [
                        *(blocker for item in blocker_items for blocker in item.blockers),
                        *(blocker for item in checkpoint_unavailable_items for blocker in item.blockers),
                    ]
                ),
            )
        )

    if missing_evidence_items:
        decisions.append(
            OperatorDecisionItem(
                priority=20,
                severity="warning",
                decision="recover_missing_evidence",
                title="Recover missing evidence",
                reason="One or more requests or candidates need evidence before review can progress.",
                primary_command=f"skill-agent input-requests {runs_arg}",
                supporting_commands=_unique(
                    [command for item in missing_evidence_items for command in item.next_commands]
                ),
                source_item_ids=[item.id for item in missing_evidence_items],
                blockers=_unique(
                    [blocker for item in missing_evidence_items for blocker in item.blockers]
                ),
            )
        )

    if promotion_ready_items:
        decisions.append(
            OperatorDecisionItem(
                priority=30,
                severity="warning",
                decision="review_candidate_promotion_evidence",
                title="Review candidate promotion evidence",
                reason="Promotion-ready candidates still require human review; candidate evidence is not durable admission.",
                primary_command=f"skill-agent candidates {runs_arg}",
                supporting_commands=_unique(
                    [command for item in promotion_ready_items for command in item.next_commands]
                ),
                source_item_ids=[item.id for item in promotion_ready_items],
            )
        )

    non_run_negative_items = [
        item for item in unsafe_or_negative_items if item.source_type != "run_log"
    ]
    if non_run_negative_items:
        decisions.append(
            OperatorDecisionItem(
                priority=40,
                severity="warning",
                decision="review_negative_evidence",
                title="Review negative or safety evidence",
                reason="Negative, safety, repair, or unfavorable evidence should be reviewed before any promotion decision.",
                primary_command=f"skill-agent negative-evidence {runs_arg}",
                supporting_commands=_unique(
                    [command for item in non_run_negative_items for command in item.next_commands]
                ),
                source_item_ids=[item.id for item in non_run_negative_items],
                blockers=_unique(
                    [blocker for item in non_run_negative_items for blocker in item.blockers]
                ),
                warnings=_unique(
                    [warning for item in non_run_negative_items for warning in item.warnings]
                ),
            )
        )

    if checkpoint.status in {"no_checkpoint", "differs_from_latest", "checkpoint_blocked"}:
        severity: OperatorSummarySeverity = "info"
        if checkpoint.status == "checkpoint_blocked":
            severity = "blocker"
        elif checkpoint.status == "differs_from_latest":
            severity = "warning"
        decisions.append(
            OperatorDecisionItem(
                priority=50,
                severity=severity,
                decision="verify_or_checkpoint_evidence",
                title="Verify or checkpoint evidence",
                reason=f"Evidence checkpoint status is {checkpoint.status}.",
                primary_command=f"skill-agent evidence-checkpoint {runs_arg} --verify",
                source_item_ids=[item.id for item in checkpoint_items],
                blockers=list(checkpoint.blockers),
                warnings=list(checkpoint.warnings),
            )
        )

    if not decisions:
        decisions.append(
            OperatorDecisionItem(
                priority=90,
                severity="info",
                decision="no_active_operator_action",
                title="No active operator action",
                reason="No blockers, missing evidence, unsafe evidence, promotion-ready candidates, or checkpoint changes are surfaced by current local evidence.",
            )
        )

    return sorted(decisions, key=lambda item: (item.priority, _SEVERITY_RANK[item.severity]))


def _first_command(command_groups: list[list[str]]) -> str | None:
    for commands in command_groups:
        for command in commands:
            if command:
                return command
    return None


def _next_steps(
    *,
    runs_dir: Path,
    blocked_items: list[OperatorSummaryItem],
    human_input_items: list[OperatorSummaryItem],
    promotion_ready_items: list[OperatorSummaryItem],
    missing_evidence_items: list[OperatorSummaryItem],
    unsafe_or_negative_items: list[OperatorSummaryItem],
    checkpoint: OperatorCheckpointSummary,
) -> list[str]:
    steps: list[str] = []
    runs_arg = f"--runs-dir {runs_dir}"
    if human_input_items:
        steps.append(f"skill-agent input-requests {runs_arg}")
    if promotion_ready_items:
        steps.append(f"skill-agent candidates {runs_arg}")
    run_log_unsafe_items = [
        item
        for item in unsafe_or_negative_items
        if item.source_type == "run_log" and item.source_path
    ]
    if any(item.source_type != "run_log" for item in unsafe_or_negative_items):
        steps.append(f"skill-agent negative-evidence {runs_arg}")
    for item in run_log_unsafe_items:
        steps.extend(item.next_commands)
    if checkpoint.status in {
        "no_checkpoint",
        "differs_from_latest",
        "checkpoint_blocked",
        "checkpoint_unavailable",
    }:
        steps.append(f"skill-agent evidence-checkpoint {runs_arg} --verify")
    if blocked_items or missing_evidence_items:
        steps.append("Resolve blockers or missing evidence, then rerun skill-agent operator-summary.")
    if not steps:
        steps.append("No active operator action surfaced by current local evidence.")
    return _unique(steps)


def _sort_items(items: list[OperatorSummaryItem]) -> list[OperatorSummaryItem]:
    return sorted(
        items,
        key=lambda item: (
            _SEVERITY_RANK[item.severity],
            item.source_type,
            item.created_at is None,
            item.created_at,
            item.id,
        ),
    )


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique
