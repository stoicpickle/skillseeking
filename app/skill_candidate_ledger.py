from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from app.models import (
    RunLog,
    SkillCandidateLedger,
    SkillCandidateLedgerEntry,
    SkillCandidateStatus,
)
from app.skill_requester import PROMOTION_EVIDENCE

LEDGER_FILENAME = "skill_candidate_ledger.json"
LOCK_FILENAME = "skill_candidate_ledger.lock"

_STATUS_RANK: dict[SkillCandidateStatus, int] = {
    "requested": 0,
    "draft": 1,
    "temporary": 2,
    "candidate": 3,
    "stable": 4,
    "deprecated": 4,
    "blocked": 99,
}


class SkillCandidateLedgerError(RuntimeError):
    pass


def ledger_path(runs_dir: Path) -> Path:
    return runs_dir / LEDGER_FILENAME


def load_candidate_ledger(runs_dir: Path) -> SkillCandidateLedger:
    path = ledger_path(runs_dir)
    if not path.exists():
        return SkillCandidateLedger()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return SkillCandidateLedger.model_validate(data)
    except OSError as exc:
        raise SkillCandidateLedgerError(f"could not read skill candidate ledger: {path}") from exc
    except (json.JSONDecodeError, ValueError) as exc:
        raise SkillCandidateLedgerError(f"invalid skill candidate ledger: {path}") from exc


def write_candidate_ledger(ledger: SkillCandidateLedger, runs_dir: Path) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    ledger.entries = sorted(ledger.entries, key=lambda entry: entry.candidate_id)
    path = ledger_path(runs_dir)
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


def record_run_in_candidate_ledger(run_log: RunLog, runs_dir: Path) -> Path | None:
    with _ledger_lock(runs_dir):
        ledger = load_candidate_ledger(runs_dir)
        changed = update_candidate_ledger_from_run(ledger, run_log)
        if not changed:
            return None
        return write_candidate_ledger(ledger, runs_dir)


def approve_candidate_promotion(
    runs_dir: Path,
    candidate_id: str,
    reviewer: str,
    notes: str,
) -> SkillCandidateLedgerEntry:
    reviewer = reviewer.strip()
    notes = notes.strip()
    if not reviewer:
        raise SkillCandidateLedgerError("promotion reviewer is required")
    if not notes:
        raise SkillCandidateLedgerError("promotion notes are required")

    with _ledger_lock(runs_dir):
        ledger = load_candidate_ledger(runs_dir)
        entry = next((item for item in ledger.entries if item.candidate_id == candidate_id), None)
        if entry is None:
            raise SkillCandidateLedgerError(f"candidate not found: {candidate_id}")
        _validate_promotion_eligibility(entry)
        now = datetime.now()
        entry.status = "candidate"
        entry.human_approval_required = False
        entry.promotion_approved_by = reviewer
        entry.promotion_approved_at = now
        entry.promotion_approval_notes = notes
        entry.updated_at = now
        ledger.updated_at = now
        write_candidate_ledger(ledger, runs_dir)
        return entry


def _validate_promotion_eligibility(entry: SkillCandidateLedgerEntry) -> None:
    if entry.status == "blocked":
        raise SkillCandidateLedgerError("blocked candidates cannot be promoted")
    if entry.quarantine_reason or entry.block_reason:
        raise SkillCandidateLedgerError("quarantined or blocked candidates cannot be promoted")
    if entry.duplicate_of:
        raise SkillCandidateLedgerError("duplicate candidates require manual merge before promotion")
    if entry.status != "temporary":
        raise SkillCandidateLedgerError("only temporary candidates can be promoted in this workflow")
    if entry.validation_pass_count < 1:
        raise SkillCandidateLedgerError("candidate promotion requires at least one validation pass")
    if entry.successful_temporary_uses < 1:
        raise SkillCandidateLedgerError("candidate promotion requires at least one successful temporary use")
    if entry.validation_failure_count > 0 or entry.repair_requirements:
        raise SkillCandidateLedgerError("candidate promotion requires unresolved repair evidence to be cleared")


def update_candidate_ledger_from_run(ledger: SkillCandidateLedger, run_log: RunLog) -> bool:
    changed = False
    now = run_log.created_at
    entries_by_id = {entry.candidate_id: entry for entry in ledger.entries}
    ledger_entry_ids = {entry.candidate_id for entry in ledger.entries}
    requests_by_id: dict[str, dict[str, Any]] = {}

    for request in run_log.skill_requests:
        if not isinstance(request, dict):
            continue
        skill_name = str(request.get("desired_skill_name") or "requested-skill")
        capability = str(request.get("missing_capability") or skill_name)
        entry = _entry_for(entries_by_id, skill_name, capability, now)
        if entry.candidate_id not in ledger_entry_ids:
            ledger.entries.append(entry)
            ledger_entry_ids.add(entry.candidate_id)
            changed = True

        request_id = str(request.get("id") or "")
        if request_id:
            requests_by_id[request_id] = request

        run_added = _touch_entry(entry, run_log.run_id, now)
        if run_added:
            entry.request_count += 1
            changed = True

        changed = _set_value(entry, "input_schema", _string_dict(request.get("input_schema"))) or changed
        changed = _set_value(entry, "output_schema", _string_dict(request.get("output_schema"))) or changed
        promotion_requirements = _unique(
            entry.promotion_requirements + _promotion_requirements(request)
        )
        changed = _set_value(entry, "promotion_requirements", promotion_requirements) or changed
        changed = _set_value(entry, "human_approval_required", True) or changed
        governor_summary = _governor_summary(request.get("control_summary"))
        if governor_summary:
            changed = _set_value(entry, "governor_summary", governor_summary) or changed

        control_summary = request.get("control_summary") or {}
        if isinstance(control_summary, dict):
            changed = _record_control_summary(entry, control_summary) or changed

        if bool(request.get("approval_required")):
            changed = _append_unique(entry.safety_flags, "request_requires_approval") or changed

        temporary = request.get("temporary_skill")
        if isinstance(temporary, dict):
            changed = _promote_status(entry, "draft") or changed
            if run_added:
                if temporary.get("validation_passed"):
                    entry.validation_pass_count += 1
                else:
                    entry.validation_failure_count += 1
                if temporary.get("loaded"):
                    entry.successful_temporary_uses += 1
                changed = True
            if temporary.get("validation_passed"):
                changed = _promote_status(entry, "temporary") or changed
            else:
                changed = _record_repair_requirement(
                    entry,
                    temporary.get("validation_reasons") or ["temporary skill validation failed"],
                ) or changed
        elif request.get("temporary_skill_error"):
            if run_added:
                entry.validation_failure_count += 1
                changed = True
            changed = _record_repair_requirement(entry, [str(request["temporary_skill_error"])]) or changed

    for repair in run_log.skill_repair_requests:
        if not isinstance(repair, dict):
            continue
        request = requests_by_id.get(str(repair.get("skill_request_id") or ""))
        skill_name = str(repair.get("skill_name") or (request or {}).get("desired_skill_name") or "requested-skill")
        capability = str(
            repair.get("failed_capability")
            or (request or {}).get("missing_capability")
            or skill_name
        )
        entry = _entry_for(entries_by_id, skill_name, capability, now)
        if entry.candidate_id not in ledger_entry_ids:
            ledger.entries.append(entry)
            ledger_entry_ids.add(entry.candidate_id)
            changed = True
        changed = _touch_entry(entry, run_log.run_id, now) or changed
        changed = _promote_status(entry, "draft") or changed
        changed = _record_repair_requirement(entry, repair.get("failure_reasons") or []) or changed
        repair_id = repair.get("id")
        if repair_id:
            changed = _append_unique(entry.repair_requirements, f"repair request recorded: {repair_id}") or changed
        objective = repair.get("repair_objective")
        if objective:
            changed = _append_unique(entry.repair_requirements, str(objective)) or changed
        for constraint in repair.get("constraints") or []:
            changed = _append_unique(entry.repair_requirements, str(constraint)) or changed

    for rejection in run_log.rejected_skills:
        if not isinstance(rejection, dict):
            continue
        skill_name = _rejected_skill_name(rejection)
        capability = str(rejection.get("capability") or skill_name)
        entry = _entry_for(entries_by_id, skill_name, capability, now)
        if entry.candidate_id not in ledger_entry_ids:
            ledger.entries.append(entry)
            ledger_entry_ids.add(entry.candidate_id)
            changed = True
        changed = _touch_entry(entry, run_log.run_id, now) or changed
        reasons = [str(reason) for reason in rejection.get("reasons") or []]
        reason_text = "; ".join(reasons) or "skill rejected by validator"
        changed = _set_value(entry, "quarantine_reason", reason_text) or changed
        changed = _set_value(entry, "block_reason", reason_text) or changed
        changed = _append_unique(entry.safety_flags, "rejected_skill") or changed
        for reason in reasons:
            changed = _append_unique(entry.safety_flags, f"validator:{reason}") or changed
        changed = _promote_status(entry, "blocked") or changed

    if _mark_duplicate_contracts(ledger):
        changed = True

    if changed:
        ledger.entries = sorted(ledger.entries, key=lambda entry: entry.candidate_id)
        ledger.updated_at = now
    return changed


def candidate_id_for(skill_name: str, capability: str) -> str:
    normalized = f"{_normalize_key(skill_name)}:{_normalize_key(capability)}"
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]
    return f"candidate_{digest}"


def _entry_for(
    entries_by_id: dict[str, SkillCandidateLedgerEntry],
    skill_name: str,
    capability: str,
    now: datetime,
) -> SkillCandidateLedgerEntry:
    candidate_id = candidate_id_for(skill_name, capability)
    entry = entries_by_id.get(candidate_id)
    if entry is None:
        entry = SkillCandidateLedgerEntry(
            candidate_id=candidate_id,
            skill_name=skill_name,
            capability=capability,
            status="requested",
            promotion_requirements=list(PROMOTION_EVIDENCE),
            human_approval_required=True,
            created_at=now,
            updated_at=now,
        )
        entries_by_id[candidate_id] = entry
    return entry


def _touch_entry(entry: SkillCandidateLedgerEntry, run_id: str, now: datetime) -> bool:
    if run_id in entry.evidence_run_ids:
        return False
    if entry.first_seen_run_id is None:
        entry.first_seen_run_id = run_id
    entry.last_seen_run_id = run_id
    entry.evidence_run_ids.append(run_id)
    entry.updated_at = now
    return True


def _promote_status(entry: SkillCandidateLedgerEntry, status: SkillCandidateStatus) -> bool:
    if status == "blocked":
        return _set_value(entry, "status", "blocked")
    if entry.status == "blocked":
        return False
    if _STATUS_RANK[status] > _STATUS_RANK[entry.status]:
        return _set_value(entry, "status", status)
    return False


def _record_control_summary(entry: SkillCandidateLedgerEntry, control_summary: dict[str, Any]) -> bool:
    changed = False
    gate = control_summary.get("approval_gate")
    risk_level = control_summary.get("risk_level")
    if gate and gate != "none":
        changed = _append_unique(entry.safety_flags, f"approval_gate:{gate}") or changed
    if risk_level in {"medium", "high"}:
        changed = _append_unique(entry.safety_flags, f"risk:{risk_level}") or changed
    if control_summary.get("approval_required"):
        changed = _append_unique(entry.safety_flags, "governor_requires_approval") or changed
    blocked_reason = control_summary.get("blocked_reason")
    if blocked_reason:
        changed = _set_value(entry, "block_reason", str(blocked_reason)) or changed
        changed = _promote_status(entry, "blocked") or changed
    return changed


def _promotion_requirements(request: dict[str, Any]) -> list[str]:
    control_summary = request.get("control_summary")
    if isinstance(control_summary, dict):
        requirements = control_summary.get("evidence_to_promote")
        if isinstance(requirements, list) and requirements:
            return [str(requirement) for requirement in requirements]
    return list(PROMOTION_EVIDENCE)


def _governor_summary(control_summary: Any) -> dict[str, Any]:
    if not isinstance(control_summary, dict):
        return {}
    keys = [
        "governor_decision",
        "dominant_signal",
        "confidence",
        "risk_level",
        "reversibility",
        "approval_required",
        "approval_gate",
        "blocked_reason",
    ]
    return {key: control_summary[key] for key in keys if key in control_summary}


def _record_repair_requirement(entry: SkillCandidateLedgerEntry, reasons: Any) -> bool:
    changed = False
    reason_list = reasons if isinstance(reasons, list) else [reasons]
    for reason in reason_list:
        if reason:
            changed = _append_unique(entry.repair_requirements, f"repair required: {reason}") or changed
    return changed


def _rejected_skill_name(rejection: dict[str, Any]) -> str:
    if rejection.get("name"):
        return str(rejection["name"])
    path = rejection.get("path")
    if path:
        try:
            return Path(str(path)).parent.name or Path(str(path)).stem
        except ValueError:
            return str(path)
    return "rejected-skill"


def _mark_duplicate_contracts(ledger: SkillCandidateLedger) -> bool:
    desired_of: dict[str, str | None] = {
        entry.candidate_id: None for entry in ledger.entries
    }
    desired_evidence: dict[str, list[str]] = {
        entry.candidate_id: [] for entry in ledger.entries
    }
    grouped: dict[str, list[SkillCandidateLedgerEntry]] = defaultdict(list)
    for entry in ledger.entries:
        if not entry.input_schema or not entry.output_schema:
            continue
        key = json.dumps(
            {"input": entry.input_schema, "output": entry.output_schema},
            sort_keys=True,
        )
        grouped[key].append(entry)

    for entries in grouped.values():
        if len(entries) < 2:
            continue
        entries = sorted(entries, key=lambda item: item.candidate_id)
        original = entries[0]
        for duplicate in entries[1:]:
            desired_of[duplicate.candidate_id] = original.candidate_id
            desired_evidence[duplicate.candidate_id] = [
                f"matches input/output contract for {original.skill_name}"
            ]

    changed = False
    for entry in ledger.entries:
        changed = _set_value(entry, "duplicate_of", desired_of[entry.candidate_id]) or changed
        changed = _set_value(
            entry,
            "duplicate_evidence",
            desired_evidence[entry.candidate_id],
        ) or changed
    return changed


def _string_dict(value: Any) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _append_unique(values: list[str], value: str) -> bool:
    if value in values:
        return False
    values.append(value)
    return True


def _set_value(obj: Any, attr: str, value: Any) -> bool:
    if getattr(obj, attr) == value:
        return False
    setattr(obj, attr, value)
    return True


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _normalize_key(value: str) -> str:
    return " ".join(value.strip().lower().split()) or "unknown"


@contextmanager
def _ledger_lock(runs_dir: Path, timeout_seconds: float = 10.0) -> Iterator[None]:
    runs_dir.mkdir(parents=True, exist_ok=True)
    path = runs_dir / LOCK_FILENAME
    start = time.monotonic()
    fd: int | None = None
    while fd is None:
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"pid={os.getpid()}\n".encode("utf-8"))
        except FileExistsError:
            if _remove_stale_lock(path, stale_after_seconds=timeout_seconds):
                continue
            if time.monotonic() - start >= timeout_seconds:
                raise SkillCandidateLedgerError(
                    f"timed out waiting for skill candidate ledger lock: {path}"
                ) from None
            time.sleep(0.05)
        except OSError:
            if fd is not None:
                os.close(fd)
                _unlink_lock(path)
            raise
    try:
        yield
    finally:
        if fd is not None:
            os.close(fd)
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _remove_stale_lock(path: Path, *, stale_after_seconds: float) -> bool:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    except OSError:
        content = ""

    pid = _lock_pid(content)
    if pid is not None and not _pid_is_alive(pid):
        return _unlink_lock(path)

    try:
        age_seconds = time.time() - path.stat().st_mtime
    except OSError:
        return False
    if age_seconds >= stale_after_seconds:
        return _unlink_lock(path)
    return False


def _lock_pid(content: str) -> int | None:
    for line in content.splitlines():
        if not line.startswith("pid="):
            continue
        try:
            pid = int(line.removeprefix("pid=").strip())
        except ValueError:
            return None
        return pid if pid > 0 else None
    return None


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _unlink_lock(path: Path) -> bool:
    try:
        path.unlink()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True
