from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.input_focus import admission_input_request
from app.models import (
    AdmissionDurableRegistrySummary,
    AdmissionCheckResult,
    AdmissionEvidenceRun,
    AdmissionPlanCheck,
    AdmissionPlanOutcome,
    AdmissionPlanReport,
    AdmissionSourceArtifact,
    SkillCandidateLedgerEntry,
    SkillManifest,
)
from app.registry import SkillRegistry
from app.skill_candidate_ledger import (
    SkillCandidateLedgerError,
    candidate_id_for,
    ledger_path,
    load_candidate_ledger,
)
from app.skill_parser import SkillParseError, parse_skill_file
from app.skill_validator import validate_parsed_skill


class AdmissionPlanError(RuntimeError):
    pass


def build_admission_plan(
    candidate_id: str,
    *,
    runs_dir: Path,
    skills_dir: Path,
) -> AdmissionPlanReport:
    try:
        ledger = load_candidate_ledger(runs_dir)
    except SkillCandidateLedgerError as exc:
        raise AdmissionPlanError(str(exc)) from exc

    entry = next((item for item in ledger.entries if item.candidate_id == candidate_id), None)
    if entry is None:
        raise AdmissionPlanError(f"candidate not found: {candidate_id}")

    checks: list[AdmissionPlanCheck] = []
    run_logs = _run_log_index(runs_dir, checks)
    evidence_runs = _evidence_runs(entry, run_logs, checks)
    source_paths = _source_paths(evidence_runs, runs_dir)
    source_artifacts = [
        _inspect_source_artifact(path, runs_dir, checks)
        for path in source_paths
    ]
    if not source_paths:
        _add_check(
            checks,
            "source_skill_path_missing",
            "blocker",
            "No explicit temporary SKILL.md path was found in matching run-log evidence.",
        )

    selected_source = _selected_source_artifact(source_artifacts)
    registry_summary = _durable_registry_summary(
        skills_dir,
        selected_source,
        source_artifacts,
        checks,
    )

    _candidate_checks(entry, checks)
    blockers = [check.code for check in checks if check.result == "blocker"]
    warnings = [check.code for check in checks if check.result == "warning"]
    outcome = _outcome(entry, blockers)
    input_request = admission_input_request(
        candidate_id=entry.candidate_id,
        skill_name=entry.skill_name,
        outcome=outcome,
        blockers=blockers,
        evidence_refs=_unique(
            [run.run_id for run in evidence_runs]
            + [artifact.skill_path for artifact in source_artifacts]
        ),
    )

    return AdmissionPlanReport(
        candidate_id=entry.candidate_id,
        ledger_path=str(ledger_path(runs_dir)),
        skills_dir=str(skills_dir),
        runs_dir=str(runs_dir),
        ready_for_durable_review=outcome == "ready_for_durable_review",
        outcome=outcome,
        candidate=entry.model_dump(mode="json"),
        promotion_requirements=list(entry.promotion_requirements),
        evidence_runs=evidence_runs,
        source_artifacts=source_artifacts,
        selected_source_artifact=(
            selected_source.skill_path if selected_source is not None else None
        ),
        durable_registry=registry_summary,
        checks=checks,
        blockers=blockers,
        warnings=warnings,
        next_steps=_next_steps(outcome),
        input_request=input_request,
    )


def _run_log_index(
    runs_dir: Path,
    checks: list[AdmissionPlanCheck],
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    seen_paths: dict[str, list[str]] = defaultdict(list)
    if not runs_dir.exists():
        return indexed

    for path in sorted(runs_dir.rglob("run_*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        run_id = data.get("run_id")
        if not run_id:
            continue
        run_id_text = str(run_id)
        seen_paths[run_id_text].append(str(path))
        indexed.setdefault(run_id_text, {"path": str(path), "data": data})

    for run_id, paths in sorted(seen_paths.items()):
        if len(paths) > 1:
            _add_check(
                checks,
                "duplicate_run_log_id",
                "warning",
                f"Multiple run logs were found for run ID {run_id}; using {paths[0]}.",
                {"run_id": run_id, "paths": paths},
            )
    return indexed


def _evidence_runs(
    entry: SkillCandidateLedgerEntry,
    run_logs: dict[str, dict[str, Any]],
    checks: list[AdmissionPlanCheck],
) -> list[AdmissionEvidenceRun]:
    evidence: list[AdmissionEvidenceRun] = []
    for run_id in entry.evidence_run_ids:
        record = run_logs.get(run_id)
        if record is None:
            _add_check(
                checks,
                "evidence_run_log_missing",
                "blocker",
                f"No run log was found for evidence run {run_id}.",
                {"run_id": run_id},
            )
            evidence.append(AdmissionEvidenceRun(run_id=run_id))
            continue

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
            if isinstance(temporary, dict):
                skill_path = temporary.get("skill_path")
                if skill_path:
                    temporary_skill_paths.append(str(skill_path))
                if temporary.get("validation_passed") is not None:
                    validation_values.append(bool(temporary.get("validation_passed")))
                if temporary.get("loaded") is not None:
                    loaded_values.append(bool(temporary.get("loaded")))

        if not matching_request_ids:
            _add_check(
                checks,
                "matching_request_missing",
                "blocker",
                f"Run log {run_id} did not include a matching skill request.",
                {"run_id": run_id},
            )

        evidence.append(
            AdmissionEvidenceRun(
                run_id=run_id,
                run_log_path=record["path"],
                found=True,
                result_category=(
                    str(data["result_category"])
                    if data.get("result_category") is not None
                    else None
                ),
                matching_request_ids=matching_request_ids,
                temporary_skill_paths=_unique(temporary_skill_paths),
                # Ledger-level validation counters still decide readiness; this
                # run-level summary only records whether matching evidence exists.
                validation_passed=any(validation_values) if validation_values else None,
                loaded=any(loaded_values) if loaded_values else None,
            )
        )
    return evidence


def _request_matches_entry(request: dict[str, Any], entry: SkillCandidateLedgerEntry) -> bool:
    skill_name = str(request.get("desired_skill_name") or "requested-skill")
    capability = str(request.get("missing_capability") or skill_name)
    if candidate_id_for(skill_name, capability) == entry.candidate_id:
        return True
    return skill_name == entry.skill_name and capability == entry.capability


def _source_paths(evidence_runs: list[AdmissionEvidenceRun], runs_dir: Path) -> list[Path]:
    values: list[str] = []
    for run in evidence_runs:
        values.extend(run.temporary_skill_paths)
    return [_normalize_source_path(value, runs_dir) for value in _unique(values)]


def _normalize_source_path(raw_value: str, runs_dir: Path) -> Path:
    path = Path(raw_value)
    if path.is_absolute():
        return path
    if path.parts and path.parts[0] == runs_dir.name:
        return runs_dir.parent / path
    return runs_dir / path


def _inspect_source_artifact(
    path: Path,
    runs_dir: Path,
    checks: list[AdmissionPlanCheck],
) -> AdmissionSourceArtifact:
    source_root = path.parent.parent if path.name == "SKILL.md" else path.parent
    resolved_path = path.resolve()
    resolved_runs = runs_dir.resolve()
    try:
        resolved_path.relative_to(resolved_runs)
    except ValueError:
        _add_check(
            checks,
            "source_path_outside_runs",
            "blocker",
            f"Source skill path is outside runs_dir: {path}",
            {"skill_path": str(path), "runs_dir": str(runs_dir)},
        )
        return AdmissionSourceArtifact(
            skill_path=str(path),
            exists=False,
            source_root=str(source_root),
        )

    if not path.exists():
        _add_check(
            checks,
            "source_skill_missing",
            "blocker",
            f"Source SKILL.md does not exist: {path}",
            {"skill_path": str(path)},
        )
        return AdmissionSourceArtifact(
            skill_path=str(path),
            exists=False,
            source_root=str(source_root),
        )

    try:
        parsed = parse_skill_file(path)
    except (OSError, SkillParseError) as exc:
        _add_check(
            checks,
            "source_skill_parse_failed",
            "blocker",
            f"Source SKILL.md could not be parsed: {exc}",
            {"skill_path": str(path)},
        )
        return AdmissionSourceArtifact(
            skill_path=str(path),
            exists=True,
            source_root=str(source_root),
            validation_reasons=[str(exc)],
        )

    manifest = _manifest(parsed.frontmatter)
    validation = validate_parsed_skill(parsed, source_root)
    if not validation.accepted:
        _add_check(
            checks,
            "source_validation_failed",
            "blocker",
            "Source SKILL.md no longer passes admission validation.",
            {"skill_path": str(path), "reasons": list(validation.reasons)},
        )

    permissions = (
        manifest.permissions.model_dump(mode="json") if manifest is not None else {}
    )
    permission_widening = [name for name, enabled in permissions.items() if enabled]
    for name in permission_widening:
        _add_check(
            checks,
            "source_permission_widening",
            "blocker",
            f"Source candidate requests permission {name}; durable admission planning is Markdown-only in this slice.",
            {"skill_path": str(path), "permission": name},
        )

    scripts_dir = path.parent / "scripts"
    scripted = bool(
        (manifest is not None and manifest.script is not None)
        or scripts_dir.exists()
        or permissions.get("execute_code")
        or (manifest is not None and manifest.allowed_tools)
    )
    if scripted:
        _add_check(
            checks,
            "source_scripted_unsupported",
            "blocker",
            "Scripted candidate admission is not supported in this dry-run slice.",
            {"skill_path": str(path)},
        )

    return AdmissionSourceArtifact(
        skill_path=str(path),
        exists=True,
        parsed=True,
        source_root=str(source_root),
        validation_accepted=validation.accepted,
        validation_reasons=list(validation.reasons),
        skill_name=manifest.name if manifest is not None else validation.name,
        risk_level=manifest.risk_level if manifest is not None else None,
        permissions={str(key): bool(value) for key, value in permissions.items()},
        input_schema=(
            {str(key): str(value) for key, value in manifest.input_schema.items()}
            if manifest is not None
            else {}
        ),
        output_schema=(
            {str(key): str(value) for key, value in manifest.output_schema.items()}
            if manifest is not None
            else {}
        ),
        scripted=scripted,
    )


def _manifest(frontmatter: dict[str, Any]) -> SkillManifest | None:
    try:
        return SkillManifest.model_validate(frontmatter)
    except ValidationError:
        return None


def _selected_source_artifact(
    artifacts: list[AdmissionSourceArtifact],
) -> AdmissionSourceArtifact | None:
    for artifact in reversed(artifacts):
        if artifact.exists and artifact.validation_accepted:
            return artifact
    return artifacts[0] if artifacts else None


def _durable_registry_summary(
    skills_dir: Path,
    selected_source: AdmissionSourceArtifact | None,
    source_artifacts: list[AdmissionSourceArtifact],
    checks: list[AdmissionPlanCheck],
) -> AdmissionDurableRegistrySummary:
    registry = SkillRegistry.load(skills_dir, allow_scripts=False)
    accepted = registry.list_records()
    rejected = registry.rejections()
    source = selected_source or (source_artifacts[0] if source_artifacts else None)
    name_collision: dict[str, Any] | None = None
    rejected_name_collision: list[dict[str, Any]] = []
    contract_overlaps: list[dict[str, Any]] = []
    permission_widening: list[str] = []
    risk_or_status_differences: list[str] = []
    scripted_implications: list[str] = []

    if source is not None and source.skill_name:
        existing = registry.get(source.skill_name)
        if existing is not None:
            name_collision = {
                "skill_name": existing.name,
                "path": str(existing.path),
                "status": existing.status,
                "risk_level": existing.risk_level,
            }
            _add_check(
                checks,
                "durable_name_collision",
                "blocker",
                f"Durable skill already exists with name {existing.name}.",
                name_collision,
            )
            if source.risk_level and source.risk_level != existing.risk_level:
                risk_or_status_differences.append(
                    f"risk:{existing.risk_level}->{source.risk_level}"
                )
            if source.permissions:
                for name, enabled in source.permissions.items():
                    current = bool(getattr(existing.permissions, name, False))
                    if enabled and not current:
                        permission_widening.append(name)

        for record in accepted:
            if record.name == source.skill_name:
                continue
            if (
                source.input_schema
                and source.output_schema
                and record.input_schema == source.input_schema
                and record.output_schema == source.output_schema
            ):
                overlap = {
                    "skill_name": record.name,
                    "path": str(record.path),
                }
                contract_overlaps.append(overlap)
                _add_check(
                    checks,
                    "durable_contract_overlap",
                    "warning",
                    f"Durable skill {record.name} has the same input/output contract.",
                    overlap,
                )

        for rejection in rejected:
            rejection_name = rejection.name or rejection.path.parent.name
            if rejection_name == source.skill_name:
                payload = {
                    "skill_name": rejection_name,
                    "path": str(rejection.path),
                    "reasons": list(rejection.reasons),
                }
                rejected_name_collision.append(payload)
                exact_durable_dir = (skills_dir / source.skill_name).exists()
                _add_check(
                    checks,
                    "durable_rejected_name_collision",
                    "blocker" if exact_durable_dir else "warning",
                    f"Durable registry has a rejected same-name record for {source.skill_name}.",
                    payload,
                )

    for artifact in source_artifacts:
        permission_widening.extend(
            name for name, enabled in artifact.permissions.items() if enabled
        )
        if artifact.scripted:
            scripted_implications.append(artifact.skill_path)

    return AdmissionDurableRegistrySummary(
        durable_registry_accepted_count=len(accepted),
        durable_registry_rejected_count=len(rejected),
        name_collision=name_collision,
        rejected_name_collision=rejected_name_collision,
        contract_overlaps=contract_overlaps,
        permission_widening=sorted(set(permission_widening)),
        risk_or_status_differences=sorted(set(risk_or_status_differences)),
        scripted_implications=sorted(set(scripted_implications)),
    )


def _candidate_checks(
    entry: SkillCandidateLedgerEntry,
    checks: list[AdmissionPlanCheck],
) -> None:
    if entry.status not in {"temporary", "candidate"}:
        _add_check(
            checks,
            "candidate_status_not_admissible",
            "blocker",
            f"Candidate status {entry.status} is not eligible for durable admission planning.",
        )
    if entry.status == "temporary":
        _add_check(
            checks,
            "promotion_approval_missing",
            "blocker",
            "Temporary candidate needs human promotion approval before durable review.",
        )
    if entry.status == "candidate" and (
        not entry.promotion_approved_by or entry.promotion_approved_at is None
    ):
        _add_check(
            checks,
            "promotion_approval_missing",
            "blocker",
            "Candidate status requires recorded reviewer and approval timestamp.",
        )
    if entry.block_reason:
        _add_check(checks, "candidate_blocked", "blocker", entry.block_reason)
    if entry.quarantine_reason:
        _add_check(checks, "candidate_quarantined", "blocker", entry.quarantine_reason)
    if entry.duplicate_of:
        _add_check(
            checks,
            "candidate_duplicate",
            "blocker",
            f"Candidate duplicates {entry.duplicate_of}.",
        )
    if entry.validation_failure_count > 0:
        _add_check(
            checks,
            "candidate_validation_failures",
            "blocker",
            f"Candidate has {entry.validation_failure_count} validation failure(s).",
        )
    if entry.repair_requirements:
        _add_check(
            checks,
            "candidate_repair_required",
            "blocker",
            "Candidate has unresolved repair requirements.",
            {"repair_requirements": list(entry.repair_requirements)},
        )
    if entry.validation_pass_count < 1:
        _add_check(
            checks,
            "candidate_validation_pass_missing",
            "blocker",
            "Candidate needs at least one validation pass.",
        )
    if entry.successful_temporary_uses < 1:
        _add_check(
            checks,
            "candidate_temporary_use_missing",
            "blocker",
            "Candidate needs at least one successful temporary use.",
        )
    if not entry.promotion_requirements:
        _add_check(
            checks,
            "promotion_requirements_missing",
            "warning",
            "Candidate has no recorded promotion requirements.",
        )


def _outcome(
    entry: SkillCandidateLedgerEntry,
    blockers: list[str],
) -> AdmissionPlanOutcome:
    if not blockers:
        return "ready_for_durable_review"
    if set(blockers) == {"promotion_approval_missing"} and entry.status in {"temporary", "candidate"}:
        return "needs_promotion_approval"
    if any(
        code
        in {
            "evidence_run_log_missing",
            "matching_request_missing",
            "source_skill_path_missing",
            "source_skill_missing",
            "source_skill_parse_failed",
            "source_validation_failed",
        }
        for code in blockers
    ):
        return "evidence_incomplete"
    return "blocked"


def _next_steps(outcome: AdmissionPlanOutcome) -> list[str]:
    if outcome == "ready_for_durable_review":
        return [
            "Prepare human durable admission review.",
            "Copy/install remains intentionally out of scope for this command.",
        ]
    if outcome == "needs_promotion_approval":
        return [
            "Run promote-candidate with reviewer and notes before durable admission review.",
            "Re-run admission-plan after promotion approval is recorded.",
        ]
    if outcome == "evidence_incomplete":
        return [
            "Recover missing run-log or source SKILL.md evidence.",
            "Re-run the original temporary-skill task if evidence cannot be recovered.",
        ]
    return [
        "Resolve blockers before durable admission review.",
        "Do not copy or install this candidate while blockers remain.",
    ]


def _add_check(
    checks: list[AdmissionPlanCheck],
    code: str,
    result: AdmissionCheckResult,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    checks.append(
        AdmissionPlanCheck(
            code=code,
            result=result,
            message=message,
            details=details or {},
        )
    )


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
