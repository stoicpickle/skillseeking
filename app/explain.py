from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ExplainError(ValueError):
    pass


def explain_run_log(path: Path) -> str:
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
