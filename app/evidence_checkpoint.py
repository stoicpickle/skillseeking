from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.models import (
    EvidenceCheckpointFile,
    EvidenceCheckpointLedger,
    EvidenceCheckpointRecord,
    EvidenceCheckpointReport,
    new_default_evidence_checkpoint_id,
)

LEDGER_FILENAME = "evidence_checkpoints.json"
SCOPE = "runs_core"


class EvidenceCheckpointError(RuntimeError):
    pass


def evidence_checkpoint_ledger_path(runs_dir: Path) -> Path:
    return runs_dir / LEDGER_FILENAME


def load_evidence_checkpoint_ledger(runs_dir: Path) -> EvidenceCheckpointLedger:
    path = evidence_checkpoint_ledger_path(runs_dir)
    if not path.exists():
        return EvidenceCheckpointLedger()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return EvidenceCheckpointLedger.model_validate(data)
    except OSError as exc:
        raise EvidenceCheckpointError(f"could not read evidence checkpoint ledger: {path}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise EvidenceCheckpointError(f"invalid evidence checkpoint ledger: {path}") from exc


def build_evidence_checkpoint_report(
    *,
    runs_dir: Path,
    dry_run: bool = True,
    verify: bool = False,
) -> EvidenceCheckpointReport:
    ledger = load_evidence_checkpoint_ledger(runs_dir)
    ledger_path = evidence_checkpoint_ledger_path(runs_dir)
    evidence_files = collect_evidence_files(runs_dir)
    chain_blockers, checkpoints_verified = _verify_checkpoint_chain(ledger)
    latest = ledger.checkpoints[-1] if ledger.checkpoints else None
    latest_hash = latest.checkpoint_hash if latest is not None else None

    if verify:
        blockers = list(chain_blockers)
        current_matches = False
        if latest is None:
            blockers.append("checkpoint_ledger_empty")
        else:
            current_matches = _evidence_files_equal(evidence_files, latest.evidence_files)
            if not current_matches:
                blockers.append("current_evidence_differs_from_latest_checkpoint")
        blockers = _unique(blockers)
        verified = not blockers
        return EvidenceCheckpointReport(
            runs_dir=str(runs_dir),
            ledger_path=str(ledger_path),
            mode="verify",
            outcome="verified" if verified else "blocked",
            dry_run=True,
            checkpoint_hash=latest_hash,
            previous_checkpoint_hash=(
                latest.previous_checkpoint_hash if latest is not None else None
            ),
            latest_checkpoint_hash=latest_hash,
            evidence_file_count=len(evidence_files),
            evidence_files=evidence_files,
            checkpoint_count=len(ledger.checkpoints),
            checkpoints_verified=checkpoints_verified,
            chain_valid=not chain_blockers and bool(ledger.checkpoints),
            current_evidence_matches_latest=current_matches,
            blockers=blockers,
            warnings=[],
            next_steps=_verify_next_steps(verified),
        )

    previous_hash = latest_hash
    record = _build_checkpoint_record(
        evidence_files=evidence_files,
        previous_checkpoint_hash=previous_hash,
    )
    blockers = list(chain_blockers)
    blockers = _unique(blockers)
    warnings: list[str] = []
    appended = False
    if not dry_run and not blockers:
        ledger.checkpoints.append(record)
        _write_evidence_checkpoint_ledger(ledger, runs_dir)
        appended = True
        checkpoints_verified = len(ledger.checkpoints)
    elif not dry_run and blockers:
        warnings = ["checkpoint was not appended because the existing chain is invalid"]

    return EvidenceCheckpointReport(
        runs_dir=str(runs_dir),
        ledger_path=str(ledger_path),
        mode="create",
        outcome="checkpoint_appended" if appended else "checkpoint_ready" if not blockers else "blocked",
        dry_run=dry_run,
        checkpoint_id=record.id,
        checkpoint_hash=record.checkpoint_hash,
        previous_checkpoint_hash=previous_hash,
        latest_checkpoint_hash=record.checkpoint_hash if appended else latest_hash,
        evidence_file_count=len(evidence_files),
        evidence_files=evidence_files,
        checkpoint_count=len(ledger.checkpoints),
        checkpoints_verified=checkpoints_verified,
        chain_valid=not chain_blockers,
        current_evidence_matches_latest=appended,
        blockers=blockers,
        warnings=warnings,
        next_steps=_create_next_steps(appended, dry_run, bool(blockers)),
        checkpoint_ledger_mutated=appended,
    )


def collect_evidence_files(runs_dir: Path) -> list[EvidenceCheckpointFile]:
    if not runs_dir.exists():
        return []
    files: list[EvidenceCheckpointFile] = []
    for path in sorted(runs_dir.rglob("*")):
        if not path.is_file() or _is_checkpoint_excluded(path, runs_dir):
            continue
        data = path.read_bytes()
        files.append(
            EvidenceCheckpointFile(
                path=path.relative_to(runs_dir).as_posix(),
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
            )
        )
    return files


def _build_checkpoint_record(
    *,
    evidence_files: list[EvidenceCheckpointFile],
    previous_checkpoint_hash: str | None,
) -> EvidenceCheckpointRecord:
    checkpoint_id = new_default_evidence_checkpoint_id()
    created_at = datetime.now()
    checkpoint_hash = _checkpoint_hash(
        checkpoint_id=checkpoint_id,
        created_at=created_at,
        previous_checkpoint_hash=previous_checkpoint_hash,
        evidence_files=evidence_files,
    )
    return EvidenceCheckpointRecord(
        id=checkpoint_id,
        created_at=created_at,
        scope=SCOPE,
        previous_checkpoint_hash=previous_checkpoint_hash,
        checkpoint_hash=checkpoint_hash,
        evidence_file_count=len(evidence_files),
        evidence_files=evidence_files,
    )


def _verify_checkpoint_chain(
    ledger: EvidenceCheckpointLedger,
) -> tuple[list[str], int]:
    blockers: list[str] = []
    previous_hash: str | None = None
    verified = 0
    chain_broken = False
    for index, record in enumerate(ledger.checkpoints):
        record_blocked = False
        if record.scope != SCOPE:
            blockers.append(f"checkpoint_scope_unsupported:{record.id}")
            record_blocked = True
        if record.previous_checkpoint_hash != previous_hash:
            blockers.append(f"checkpoint_previous_hash_mismatch:{record.id}")
            record_blocked = True
        if record.evidence_file_count != len(record.evidence_files):
            blockers.append(f"checkpoint_file_count_mismatch:{record.id}")
            record_blocked = True
        expected_hash = _checkpoint_hash(
            checkpoint_id=record.id,
            created_at=record.created_at,
            previous_checkpoint_hash=record.previous_checkpoint_hash,
            evidence_files=record.evidence_files,
        )
        if record.checkpoint_hash != expected_hash:
            blockers.append(f"checkpoint_hash_mismatch:{record.id}")
            record_blocked = True
        chain_broken = chain_broken or record_blocked
        if not chain_broken:
            verified = index + 1
        previous_hash = record.checkpoint_hash
    return _unique(blockers), verified


def _checkpoint_hash(
    *,
    checkpoint_id: str,
    created_at: datetime,
    previous_checkpoint_hash: str | None,
    evidence_files: list[EvidenceCheckpointFile],
) -> str:
    payload: dict[str, Any] = {
        "id": checkpoint_id,
        "created_at": created_at.isoformat(),
        "scope": SCOPE,
        "previous_checkpoint_hash": previous_checkpoint_hash,
        "evidence_files": [item.model_dump(mode="json") for item in evidence_files],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _write_evidence_checkpoint_ledger(
    ledger: EvidenceCheckpointLedger,
    runs_dir: Path,
) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = evidence_checkpoint_ledger_path(runs_dir)
    tmp_path = path.with_name(f".{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
    try:
        tmp_path.write_text(
            json.dumps(ledger.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp_path.replace(path)
    finally:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
    return path


def _is_checkpoint_excluded(path: Path, runs_dir: Path) -> bool:
    relative = path.relative_to(runs_dir)
    parts = relative.parts
    if not parts:
        return True
    if parts[0] == "evals":
        return True
    if relative.name == LEDGER_FILENAME:
        return True
    if relative.name.endswith(".lock"):
        return True
    if relative.name.startswith(f".{LEDGER_FILENAME}.") and relative.name.endswith(".tmp"):
        return True
    return False


def _evidence_files_equal(
    current: list[EvidenceCheckpointFile],
    checkpointed: list[EvidenceCheckpointFile],
) -> bool:
    return [item.model_dump(mode="json") for item in current] == [
        item.model_dump(mode="json") for item in checkpointed
    ]


def _create_next_steps(appended: bool, dry_run: bool, blocked: bool) -> list[str]:
    if appended:
        return [
            "Use this checkpoint hash as local tamper-evidence only.",
            "Rerun evidence-checkpoint --verify before relying on the current evidence bundle.",
        ]
    if blocked:
        return [
            "Repair or quarantine the checkpoint ledger before appending another checkpoint.",
            "Rerun evidence-checkpoint --verify to inspect chain blockers.",
        ]
    if dry_run:
        return [
            "Run with --no-dry-run to append this checkpoint to runs/evidence_checkpoints.json.",
            "Keep checkpoint evidence local; it is not durable admission approval.",
        ]
    return ["No checkpoint was appended."]


def _verify_next_steps(verified: bool) -> list[str]:
    if verified:
        return [
            "Current evidence matches the latest local checkpoint.",
            "This proves local consistency only; it is not durable admission approval.",
        ]
    return [
        "Inspect blockers before relying on this evidence bundle.",
        "Create a fresh checkpoint only after resolving unexpected evidence or chain changes.",
    ]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
