from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from app.cli import app


CANONICAL_FIELDS = [
    "Partner alias:",
    "Date:",
    "Workflow type:",
    "Local environment:",
    "Session source:",
    "Launch-demo completed: yes/no",
    "`operator-summary` inspected first: yes/no",
    "Next `OPERATOR_DECISIONS` action identified unaided: yes/no",
    "Candidate evidence confused with durable admission: yes/no",
    "Stable-readiness confused with stable routing: yes/no",
    "`ready_to_enable_new_authority=false` understood: yes/no",
    "Setup friction:",
    "Operator-summary decision clarity:",
    "Evidence-surface confusion:",
    "Candidate-decision confusion:",
    "Safety-boundary confusion:",
    "Stable-routing deferral confusion:",
    "New-authority readiness confusion:",
    "Most useful proof surface:",
    "Least useful or most confusing proof surface:",
    "Desired next action:",
    "Captured issue/doc note:",
    "Follow-up priority: none/docs/operator-summary/demo/readiness/other",
]


def test_feedback_session_template_outputs_canonical_markdown_block():
    runner = CliRunner()

    result = runner.invoke(app, ["feedback-session-template"])

    assert result.exit_code == 0
    assert "FEEDBACK_SESSION_TEMPLATE" in result.stdout
    assert "Status: template_only_read_only" in result.stdout
    assert "Source doc: docs/design-partner-feedback-log.md" in result.stdout
    assert "Durable record target: docs/design-partner-feedback-log.md" in result.stdout
    assert "Feedback log appended: false" in result.stdout
    assert "Rollups updated: false" in result.stdout
    assert "## Session YYYY-MM-DD Partner Alias" in result.stdout
    for field in CANONICAL_FIELDS:
        assert f"- {field}" in result.stdout
    assert "- Durable admission granted: false" in result.stdout
    assert "- Stable routing enabled: false" in result.stdout
    assert "- Governor steering enabled: false" in result.stdout
    assert "- Dependencies installed: false" in result.stdout
    assert "- Permissions widened: false" in result.stdout
    assert "- Hosted behavior enabled: false" in result.stdout
    assert "- Marketplace behavior enabled: false" in result.stdout
    assert "durable generated-skill admission" in result.stdout
    assert "positive stable routing" in result.stdout
    assert "active governor steering" in result.stdout


def test_feedback_session_template_json_is_template_only_and_ordered():
    runner = CliRunner()

    result = runner.invoke(app, ["feedback-session-template", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["status"] == "template_only_read_only"
    assert data["template_name"] == "design_partner_session_entry"
    assert data["source_doc"] == "docs/design-partner-feedback-log.md"
    assert data["durable_record_target"] == "docs/design-partner-feedback-log.md"
    assert data["heading"] == "## Session YYYY-MM-DD Partner Alias"
    assert data["fields"] == CANONICAL_FIELDS
    assert data["template_only"] is True
    assert data["feedback_log_appended"] is False
    assert data["rollups_updated"] is False
    assert data["authority_granted"] is False
    assert data["follow_up_priority_options"] == [
        "none",
        "docs",
        "operator-summary",
        "demo",
        "readiness",
        "other",
    ]
    assert all(value is False for value in data["mutation_boundary"].values())
    for boundary in [
        "feedback-log append",
        "summary rollup update",
        "durable generated-skill admission into skills/",
        "positive stable routing",
        "active governor steering",
        "dependency installation",
        "permission widening",
        "hosted service behavior",
        "marketplace behavior",
        "true sandboxing claims",
    ]:
        assert boundary in data["excluded_authority"]


def test_feedback_session_append_dry_run_previews_without_writing(tmp_path: Path):
    feedback_log = tmp_path / "feedback-log.md"
    feedback_log.write_text(_feedback_log_text(), encoding="utf-8")
    before = feedback_log.read_text(encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "feedback-session-append",
            "--feedback-log",
            str(feedback_log),
            "--partner-alias",
            "alpha",
            "--date",
            "2026-06-07",
            "--workflow-type",
            "launch demo",
            "--operator-decision-identified-unaided",
            "yes",
            "--ready-to-enable-new-authority-false-understood",
            "yes",
            "--json",
        ],
    )

    assert result.exit_code == 0
    assert feedback_log.read_text(encoding="utf-8") == before
    data = json.loads(result.stdout)
    assert data["status"] == "dry_run_preview"
    assert data["dry_run"] is True
    assert data["feedback_log_appended"] is False
    assert data["rollups_updated"] is False
    assert data["authority_granted"] is False
    assert "## Session 2026-06-07 alpha" in data["session_entry"]
    assert data["rollup_increments"][
        "Partners who identified the next `operator-summary` decision unaided"
    ] == 1
    assert data["rollup_increments"][
        "Partners who understood `ready_to_enable_new_authority=false`"
    ] == 1
    assert all(value is False for value in data["mutation_boundary"].values())


def test_feedback_session_append_no_dry_run_records_session_and_rollups(tmp_path: Path):
    feedback_log = tmp_path / "feedback-log.md"
    feedback_log.write_text(_feedback_log_text(), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "feedback-session-append",
            "--feedback-log",
            str(feedback_log),
            "--partner-alias",
            "alpha",
            "--date",
            "2026-06-07",
            "--workflow-type",
            "launch demo",
            "--local-environment",
            "macOS local venv",
            "--session-source",
            "design call",
            "--launch-demo-completed",
            "yes",
            "--operator-summary-inspected-first",
            "yes",
            "--operator-decision-identified-unaided",
            "yes",
            "--candidate-evidence-confused-with-durable-admission",
            "no",
            "--stable-readiness-confused-with-stable-routing",
            "no",
            "--ready-to-enable-new-authority-false-understood",
            "yes",
            "--setup-friction",
            "none",
            "--operator-summary-decision-clarity",
            "clear",
            "--evidence-surface-confusion",
            "none",
            "--candidate-decision-confusion",
            "none",
            "--safety-boundary-confusion",
            "none",
            "--stable-routing-deferral-confusion",
            "none",
            "--new-authority-readiness-confusion",
            "none",
            "--most-useful-proof-surface",
            "operator-summary",
            "--least-useful-or-most-confusing-proof-surface",
            "raw ledger",
            "--desired-next-action",
            "record another session",
            "--captured-issue-doc-note",
            "none",
            "--follow-up-priority",
            "none",
            "--no-dry-run",
            "--json",
        ],
    )

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["status"] == "feedback_session_appended"
    assert data["dry_run"] is False
    assert data["feedback_log_appended"] is True
    assert data["rollups_updated"] is True
    assert data["authority_granted"] is False
    assert data["mutation_boundary"]["feedback_log_appended"] is True
    assert data["mutation_boundary"]["rollups_updated"] is True
    assert data["mutation_boundary"]["durable_skills_mutated"] is False
    assert data["mutation_boundary"]["stable_routing_enabled"] is False
    assert data["mutation_boundary"]["governor_steering_enabled"] is False
    assert "durable generated-skill admission into skills/" in data["excluded_authority"]
    assert "positive stable routing" in data["excluded_authority"]

    updated = feedback_log.read_text(encoding="utf-8")
    assert "| Completed partner sessions | 1 |" in updated
    assert (
        "| Partners who identified the next `operator-summary` decision unaided | 1 |"
        in updated
    )
    assert "| Partners who confused candidate evidence with durable admission | 0 |" in updated
    assert "| Partners who confused stable-readiness with stable routing | 0 |" in updated
    assert "| Partners who understood `ready_to_enable_new_authority=false` | 1 |" in updated
    assert "No design-partner sessions have been recorded yet." not in updated
    assert "## Session 2026-06-07 alpha" in updated
    assert "- Launch-demo completed: yes" in updated
    assert "- Follow-up priority: none" in updated


def test_feedback_session_append_requires_partner_and_date_for_write(tmp_path: Path):
    feedback_log = tmp_path / "feedback-log.md"
    feedback_log.write_text(_feedback_log_text(), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "feedback-session-append",
            "--feedback-log",
            str(feedback_log),
            "--no-dry-run",
        ],
    )

    assert result.exit_code != 0
    assert "--partner-alias and --date are required" in result.output
    assert "No design-partner sessions have been recorded yet." in feedback_log.read_text(
        encoding="utf-8"
    )


def test_feedback_session_append_rejects_invalid_yes_no(tmp_path: Path):
    feedback_log = tmp_path / "feedback-log.md"
    feedback_log.write_text(_feedback_log_text(), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "feedback-session-append",
            "--feedback-log",
            str(feedback_log),
            "--launch-demo-completed",
            "maybe",
        ],
    )

    assert result.exit_code != 0
    assert "must be blank, 'yes', or 'no'" in result.output


def _feedback_log_text() -> str:
    return """# Design Partner Feedback Log

Status: active public-dev-preview evidence log

## Summary Rollup

| Metric | Current Count |
| --- | ---: |
| Completed partner sessions | 0 |
| Partners who identified the next `operator-summary` decision unaided | 0 |
| Partners who confused candidate evidence with durable admission | 0 |
| Partners who confused stable-readiness with stable routing | 0 |
| Partners who understood `ready_to_enable_new_authority=false` | 0 |
| Repeated setup friction items | 0 |
| Repeated evidence-surface confusion items | 0 |

## Current Sessions

No design-partner sessions have been recorded yet.

## Synthesis Checklist

After 3 to 5 sessions, summarize.
"""
