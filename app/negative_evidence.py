from __future__ import annotations

from pathlib import Path

from app.input_resolution_ledger import (
    InputResolutionLedgerError,
    input_request_resolution_ledger_path,
    load_input_request_resolution_ledger,
)
from app.models import NegativeEvidenceItem, NegativeEvidenceReport
from app.skill_candidate_ledger import (
    SkillCandidateLedgerError,
    ledger_path,
    load_candidate_ledger,
)


NEGATIVE_RESOLUTION_CLASSES: set[str] = {"reject", "defer", "block", "repair"}


def build_negative_evidence_report(
    *,
    runs_dir: Path,
    candidate_id: str | None = None,
) -> NegativeEvidenceReport:
    items: list[NegativeEvidenceItem] = []
    items.extend(_candidate_items(runs_dir, candidate_id))
    items.extend(_resolution_items(runs_dir, candidate_id))
    items.sort(key=lambda item: (item.created_at is None, item.created_at, item.id))
    counts: dict[str, int] = {}
    for item in items:
        counts[item.evidence_type] = counts.get(item.evidence_type, 0) + 1
    return NegativeEvidenceReport(
        runs_dir=str(runs_dir),
        candidate_id=candidate_id,
        evidence_count=len(items),
        counts_by_type=dict(sorted(counts.items())),
        items=items,
    )


def _candidate_items(
    runs_dir: Path,
    candidate_id: str | None,
) -> list[NegativeEvidenceItem]:
    try:
        ledger = load_candidate_ledger(runs_dir)
    except SkillCandidateLedgerError:
        return []
    source = str(ledger_path(runs_dir))
    items: list[NegativeEvidenceItem] = []
    for entry in ledger.entries:
        if candidate_id and entry.candidate_id != candidate_id:
            continue
        evidence_refs = list(entry.evidence_run_ids)
        if entry.status == "blocked" or entry.block_reason or entry.quarantine_reason:
            reason = entry.block_reason or entry.quarantine_reason or "Candidate is blocked."
            items.append(
                NegativeEvidenceItem(
                    id=f"candidate_blocked:{entry.candidate_id}",
                    evidence_type="candidate_blocked",
                    candidate_id=entry.candidate_id,
                    skill_name=entry.skill_name,
                    status=entry.status,
                    reason=reason,
                    notes=entry.quarantine_reason,
                    source=source,
                    evidence_refs=evidence_refs,
                    remaining_blocked_scope="durable promotion",
                    created_at=entry.updated_at,
                )
            )
        if entry.validation_failure_count > 0 or entry.repair_requirements:
            items.append(
                NegativeEvidenceItem(
                    id=f"candidate_repair_required:{entry.candidate_id}",
                    evidence_type="candidate_repair_required",
                    candidate_id=entry.candidate_id,
                    skill_name=entry.skill_name,
                    status=entry.status,
                    reason="Candidate has validation failures or repair requirements.",
                    notes="; ".join(entry.repair_requirements) or None,
                    source=source,
                    evidence_refs=evidence_refs,
                    remaining_blocked_scope="candidate repair",
                    created_at=entry.updated_at,
                )
            )
        if entry.duplicate_of or entry.duplicate_evidence:
            items.append(
                NegativeEvidenceItem(
                    id=f"candidate_duplicate:{entry.candidate_id}",
                    evidence_type="candidate_duplicate",
                    candidate_id=entry.candidate_id,
                    skill_name=entry.skill_name,
                    status=entry.status,
                    reason="Candidate duplicates or overlaps existing evidence.",
                    notes=entry.duplicate_of,
                    source=source,
                    evidence_refs=[*evidence_refs, *entry.duplicate_evidence],
                    remaining_blocked_scope="candidate merge review",
                    created_at=entry.updated_at,
                )
            )
    return items


def _resolution_items(
    runs_dir: Path,
    candidate_id: str | None,
) -> list[NegativeEvidenceItem]:
    try:
        ledger = load_input_request_resolution_ledger(runs_dir)
    except InputResolutionLedgerError:
        return []
    source = str(input_request_resolution_ledger_path(runs_dir))
    items: list[NegativeEvidenceItem] = []
    for record in ledger.resolutions:
        related_candidate_id = record.source_request.related_candidate_id
        if candidate_id and related_candidate_id != candidate_id:
            continue
        if record.resolution_class not in NEGATIVE_RESOLUTION_CLASSES:
            continue
        items.append(
            NegativeEvidenceItem(
                id=record.id,
                evidence_type=f"resolution_{record.resolution_class}",
                candidate_id=related_candidate_id,
                input_request_id=record.input_request_id,
                decision=record.decision,
                resolution_class=record.resolution_class,
                status=record.status,
                reason=record.source_request.reason,
                notes=record.notes,
                source=source,
                evidence_refs=list(record.source_request.evidence_refs),
                remaining_blocked_scope=record.remaining_blocked_scope,
                created_at=record.created_at,
            )
        )
    return items
