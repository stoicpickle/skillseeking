from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from app.models import (
    InputRequestResolutionDryRun,
    InputRequestResolutionLedger,
    InputRequestResolutionRecord,
)

LEDGER_FILENAME = "input_request_resolutions.json"


class InputResolutionLedgerError(RuntimeError):
    pass


def input_request_resolution_ledger_path(runs_dir: Path) -> Path:
    return runs_dir / LEDGER_FILENAME


def load_input_request_resolution_ledger(runs_dir: Path) -> InputRequestResolutionLedger:
    path = input_request_resolution_ledger_path(runs_dir)
    if not path.exists():
        return InputRequestResolutionLedger()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return InputRequestResolutionLedger.model_validate(data)
    except OSError as exc:
        raise InputResolutionLedgerError(f"could not read input request resolution ledger: {path}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise InputResolutionLedgerError(f"invalid input request resolution ledger: {path}") from exc


def append_input_request_resolution(
    report: InputRequestResolutionDryRun,
    runs_dir: Path,
) -> InputRequestResolutionRecord:
    ledger = load_input_request_resolution_ledger(runs_dir)
    record = InputRequestResolutionRecord(
        input_request_id=report.input_request_id,
        decision=report.decision,
        resolution_class=report.resolution_class,
        status=report.proposed_status,
        reviewer=report.reviewer,
        notes=report.notes,
        source_request=report.request,
        sources=list(report.sources),
        remaining_blocked_scope=report.remaining_blocked_scope,
        next_steps=list(report.next_steps),
    )
    ledger.resolutions.append(record)
    _write_input_request_resolution_ledger(ledger, runs_dir)
    return record


def latest_input_request_resolutions(
    ledger: InputRequestResolutionLedger,
) -> dict[str, InputRequestResolutionRecord]:
    latest: dict[str, InputRequestResolutionRecord] = {}
    for record in ledger.resolutions:
        latest[record.input_request_id] = record
    return latest


def _write_input_request_resolution_ledger(
    ledger: InputRequestResolutionLedger,
    runs_dir: Path,
) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = input_request_resolution_ledger_path(runs_dir)
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
