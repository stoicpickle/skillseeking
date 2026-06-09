from __future__ import annotations

import json

from typer.testing import CliRunner

from app.cli import app


def test_v1_local_use_keeps_public_authority_locked():
    runner = CliRunner()

    result = runner.invoke(app, ["v1-local-use", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["stable_routing_policy"] == "deferred_for_v1"
    assert data["mutation_surface"] == "managed prefix only"
    assert "durable skills" in data["unchanged_authority"]
    assert "stable routing" in data["unchanged_authority"]
    assert "governor steering" in data["unchanged_authority"]
    assert "durable skills admission" in data["excluded_authority"]
    assert "automatic candidate-to-stable promotion" in data["excluded_authority"]
    assert "positive stable routing" in data["excluded_authority"]
    assert "dependency installation" in data["excluded_authority"]
    assert "provider API" not in data["excluded_authority"]
    assert "hosted service behavior" in data["excluded_authority"]
    assert "marketplace publication" in data["excluded_authority"]
    assert "true sandboxing claims" in data["excluded_authority"]


def test_new_authority_readiness_is_planning_only_for_public_use():
    runner = CliRunner()

    result = runner.invoke(app, ["new-authority-readiness", "--json"])

    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["ready_for_authority_planning"] is True
    assert data["ready_to_enable_new_authority"] is False
    disabled = data["must_remain_disabled_until_separate_slice"]
    assert "durable generated-skill admission into skills/" in disabled
    assert "positive stable routing" in disabled
    assert "active governor steering" in disabled
    assert "dependency installation" in disabled
    assert "marketplace publication" in disabled
    assert "hosted service behavior" in disabled
    assert "true sandboxing claims" in disabled


def test_dependency_install_and_api_authority_remain_absent_from_public_claims(repo_root):
    docs = "\n".join(
        [
            (repo_root / "README.md").read_text(encoding="utf-8"),
            (repo_root / "docs" / "v1-release-contract.md").read_text(encoding="utf-8"),
            (repo_root / "docs" / "safety-model.md").read_text(encoding="utf-8"),
            (repo_root / "docs" / "contracts" / "data-contracts.md").read_text(
                encoding="utf-8"
            ),
        ]
    ).lower()

    forbidden = [
        "dependency installation is enabled",
        "automatically installs dependencies",
        "installs candidate dependencies",
        "provider api is enabled",
        "hosted api is enabled",
        "true sandboxing is provided",
    ]
    for phrase in forbidden:
        assert phrase not in docs
    assert "dependency installation" in docs
    assert "not a true sandbox" in docs


def test_feedback_and_summary_surfaces_do_not_grant_authority(tmp_path):
    feedback_log = tmp_path / "feedback.md"
    feedback_log.write_text(
        "\n".join(
            [
                "# Feedback",
                "",
                "## Summary Rollups",
                "",
                "| Metric | Count |",
                "| --- | ---: |",
                "| Completed partner sessions | 0 |",
                "| Partners who identified the next `operator-summary` decision unaided | 0 |",
                "| Partners who confused candidate evidence with durable admission | 0 |",
                "| Partners who confused stable-readiness with stable routing | 0 |",
                "| Partners who understood `ready_to_enable_new_authority=false` | 0 |",
                "| Repeated setup friction items | 0 |",
                "| Repeated evidence-surface confusion items | 0 |",
                "",
                "## Current Sessions",
                "",
                "No reviewer sessions have been recorded yet.",
                "",
                "## Synthesis Checklist",
                "",
            ]
        ),
        encoding="utf-8",
    )
    runner = CliRunner()

    template = runner.invoke(app, ["feedback-session-template", "--json"])
    append = runner.invoke(
        app,
        [
            "feedback-session-append",
            "--feedback-log",
            str(feedback_log),
            "--partner-alias",
            "public-lock",
            "--date",
            "2026-06-07",
            "--dry-run",
            "--json",
        ],
    )
    summary = runner.invoke(
        app,
        [
            "feedback-log-summary",
            "--feedback-log",
            str(feedback_log),
            "--json",
        ],
    )

    assert template.exit_code == 0
    assert append.exit_code == 0
    assert summary.exit_code == 0
    for result in [template, append, summary]:
        data = json.loads(result.stdout)
        boundary = data.get("mutation_boundary", data)
        assert boundary.get("stable_routing_enabled") is False
        assert boundary.get("governor_steering_enabled") is False
        assert boundary.get("durable_skills_mutated") is False
        assert boundary.get("registry_mutated") is False
        assert data.get("ready_to_enable_new_authority", False) is False
