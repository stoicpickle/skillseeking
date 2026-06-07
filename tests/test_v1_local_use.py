from __future__ import annotations

import json

from typer.testing import CliRunner

from app.cli import app


def test_v1_local_use_outputs_managed_prefix_operator_checklist():
    runner = CliRunner()

    result = runner.invoke(app, ["v1-local-use"])

    assert result.exit_code == 0
    assert "V1_LOCAL_USE" in result.stdout
    assert "skill-agent shadow-managed-write" in result.stdout
    assert "Stable routing policy: deferred_for_v1" in result.stdout
    assert "dry-run mode" in result.stdout
    assert "shadow-managed-write --no-dry-run" in result.stdout
    assert "managed_write_plan_digest=<digest>" in result.stdout
    assert "--write-approval-id" in result.stdout
    assert "--expected-checkpoint-hash" in result.stdout
    assert "--expected-source-sha256" in result.stdout
    assert "--expected-durable-plan-digest" in result.stdout
    assert "--expected-shadow-plan-digest" in result.stdout
    assert "--expected-rollback-plan-digest" in result.stdout
    assert "--expected-acceptance-plan-digest" in result.stdout
    assert "--expected-managed-write-plan-digest" in result.stdout
    assert "managed-prefix path escapes" in result.stdout
    assert "stable routing" in result.stdout
    assert "governor steering" in result.stdout
    assert "durable skills admission" in result.stdout
    assert "automatic candidate-to-stable promotion" in result.stdout


def test_v1_local_use_json_names_read_only_boundaries():
    runner = CliRunner()

    result = runner.invoke(app, ["v1-local-use", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["scope"] == "managed-prefix-first local use"
    assert data["primary_command"] == "shadow-managed-write"
    assert data["mutation_surface"] == "managed prefix only"
    assert data["stable_routing_policy"] == "deferred_for_v1"
    assert "--write-approval-id" in data["required_inputs"]
    assert "--expected-managed-write-plan-digest" in data["required_inputs"]
    assert "stable routing" in data["unchanged_authority"]
    assert "durable skills" in data["unchanged_authority"]
    assert "registry" in data["unchanged_authority"]
    assert "candidate ledger" in data["unchanged_authority"]
    assert "resolution ledger" in data["unchanged_authority"]
    assert "run logs" in data["unchanged_authority"]
    assert "governor steering" in data["unchanged_authority"]
    assert "durable skills admission" in data["excluded_authority"]
    assert "positive stable routing" in data["excluded_authority"]
    assert "true sandboxing claims" in data["excluded_authority"]


def test_new_authority_readiness_states_planning_ready_but_enablement_blocked():
    runner = CliRunner()

    result = runner.invoke(app, ["new-authority-readiness"])

    assert result.exit_code == 0
    assert "NEW_AUTHORITY_READINESS" in result.stdout
    assert "Phase: v1.0 local CLI / design-partner validation" in result.stdout
    assert "Ready for authority planning: true" in result.stdout
    assert "Ready to enable new authority: false" in result.stdout
    assert "checkpoint-gated active blocker" in result.stdout
    assert "Design-partner feedback has not been collected" in result.stdout
    assert "positive stable routing" in result.stdout
    assert "active governor steering" in result.stdout
    assert "durable generated-skill admission" in result.stdout
    assert "bash scripts/v1_smoke.sh" in result.stdout


def test_new_authority_readiness_json_preserves_no_authority_boundary():
    runner = CliRunner()

    result = runner.invoke(app, ["new-authority-readiness", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["status"] == "ready_for_new_authority_design_review"
    assert data["ready_for_authority_planning"] is True
    assert data["ready_to_enable_new_authority"] is False
    assert "checkpoint-gated active blocker" in data["next_authority_candidate"]
    assert any("Design-partner feedback" in item for item in data["why_not_enable_yet"])
    assert any("eval rows" in item for item in data["required_before_enablement"])
    assert any("approval expiry" in item for item in data["required_before_enablement"])
    assert "positive stable routing" in data["must_remain_disabled_until_separate_slice"]
    assert "active governor steering" in data["must_remain_disabled_until_separate_slice"]
    assert "docs/plans/active-governor-preflight-design-2026-06-07.md" in data[
        "reference_docs"
    ]
