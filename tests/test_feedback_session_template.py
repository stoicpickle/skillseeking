from __future__ import annotations

import json

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
