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
