from __future__ import annotations

import json
import re

from typer.testing import CliRunner

from app.cli import app


ANSI_PATTERN = re.compile(r"\x1b\[[0-9;]*m")


def test_banner_no_color_outputs_compact_identity_banner():
    runner = CliRunner()

    result = runner.invoke(app, ["banner", "--no-color"])

    assert result.exit_code == 0
    assert "\x1b[" not in result.stdout
    assert "Skill-Seeking Agent" in result.stdout
    assert "####" in result.stdout
    assert "mode: governed capability acquisition" in result.stdout
    assert "scope: local CLI | evidence first | no hidden authority" in result.stdout
    assert 'start: skill-agent run "Cluster arguments from these sources."' in result.stdout
    assert len(result.stdout.strip().splitlines()) == 13


def test_banner_color_outputs_ansi_gradient():
    runner = CliRunner()

    result = runner.invoke(app, ["banner", "--force-color"])

    assert result.exit_code == 0
    assert "\x1b[" in result.stdout
    stripped = ANSI_PATTERN.sub("", result.stdout)
    assert "Skill-Seeking Agent" in stripped
    assert "####" in stripped


def test_banner_does_not_pollute_existing_json_output():
    runner = CliRunner()

    result = runner.invoke(app, ["v1-local-use", "--json"])

    assert result.exit_code == 0
    assert result.stdout.lstrip().startswith("{")
    data = json.loads(result.stdout)
    assert data["scope"] == "managed-prefix-first local use"
    assert "Skill-Seeking Agent" not in result.stdout
