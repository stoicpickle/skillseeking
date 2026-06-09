# Skill-Seeking Agent

[![Tests](https://github.com/stoicpickle/skillseeking/actions/workflows/tests.yml/badge.svg)](https://github.com/stoicpickle/skillseeking/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![Version](https://img.shields.io/badge/local_CLI-v1.0.0-orange)
![License](https://img.shields.io/badge/license-MIT-green)

![Skill-Seeking Agent governed capability acquisition hero](docs/assets/skillseeking-hero.png)

Skill-Seeking Agent is a v1.0 local CLI release for governed capability acquisition. It makes an agent stop when it lacks a capability, emit a structured skill request, validate a temporary Markdown skill, preserve evidence, and ask for the next human decision before any durable authority is granted.

It is intentionally **local-only**, **operator-governed**, and **Markdown-first**. Version `1.0.0` is the local CLI compatibility stamp; the matching Git release tag is `v1.0.0`. It is not a production agent framework, not a hosted platform, not a marketplace, and not production-safe.

## What To Inspect First

| Reviewer question | Start here | Proof |
| --- | --- | --- |
| Does the CLI run from a fresh checkout? | `python3 -m venv .venv && .venv/bin/python -m pip install -e '.[dev]'` | [Start Here](docs/start-here.md) |
| Can it show the capability-gap loop quickly? | `.venv/bin/python scripts/run_gauntlet_demo.py` | [Demo suite](docs/demo-suite.md) |
| Does it compress the next human decision? | `bash scripts/run_launch_demo.sh --keep-workspace`, then run the printed `operator-summary` command | [Operator Summary Review Pack](docs/operator-summary-review-pack.md) |
| Are the safety boundaries tested? | `bash scripts/v1_smoke.sh` | [V1.0 Release Contract](docs/v1-release-contract.md) |

## The Hook

The product is the agent's ability to say:

```text
I am blocked because I lack capability X.
I need a skill with input Y, output Z, and success test W.
```

The core trace is:

```text
BLOCKED -> REQUESTED_SKILL -> VALIDATED -> LOADED -> CONTINUED
```

That trace is more important than the final answer. The demo is visible capability self-awareness with evidence, not a large tool catalog.

![Governed capability-gap evidence loop](docs/assets/skillseeking-evidence-loop.png)

## 30-Second Quickstart

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python scripts/run_gauntlet_demo.py
```

The gauntlet runs one mixed-pressure task where the agent:

- loads existing safe skills;
- rejects malicious skill fixtures;
- requests and validates a missing Markdown skill;
- loads that temporary skill only for the run;
- rejects a higher-risk local-code skill and emits a repair request;
- writes a JSON run log with the complete trace.

![Skill Gauntlet terminal demo](docs/assets/skill-gauntlet-terminal.svg)

To verify the same path as a test:

```bash
.venv/bin/python -m pytest -q tests/test_gauntlet_demo.py
```

## What It Proves

V1.0 can:

- run local CLI tasks and write schema-versioned JSON run logs;
- explain run logs with `skill-agent explain`;
- load trusted local Markdown skills from the durable registry;
- reject malformed, unsafe, or malicious skill fixtures;
- emit structured skill requests when a capability is missing;
- validate temporary Markdown skills and load them for one run;
- preserve candidate evidence in local ledgers;
- surface human decision requests and append-only resolutions;
- summarize candidate review state with `skill-agent candidate-decision`;
- run release, lifecycle, diagnostic, and capability-gap eval suites.

V1.0 still does **not** provide hosted operation, a public skill marketplace, true sandboxing, dependency installation, durable `skills/` admission for generated candidates, positive stable routing, autonomous promotion, permission widening without review, or active governor steering. Scripted skills are trusted-local only; `--scripted-skills` does not provide a sandbox.

## Launch Demo

For the shortest public-preview path through the product wedge:

```bash
bash scripts/run_launch_demo.sh --keep-workspace
```

This uses an isolated temporary copy of `skills/` to show the agent detecting a missing capability, requesting and validating a temporary Markdown skill, loading it for one run, then surfacing `candidate-decision` while durable skill admission and stable routing remain disabled. `--keep-workspace` preserves the demo evidence and prints the exact `operator-summary` command to inspect next.

## Validation

Run the local smoke gate:

```bash
bash scripts/v1_smoke.sh
```

For a faster CLI surface check:

```bash
.venv/bin/python scripts/cli_doctor.py
.venv/bin/python scripts/cli_doctor.py --json
```

Run the local security gate before public-facing changes:

```bash
.venv/bin/python scripts/security_check.py
```

## Documentation

Public tour:

- [Start Here](docs/start-here.md)
- [CLI Reference](docs/cli-reference.md)
- [System Architecture](docs/architecture.md)
- [Skill Lifecycle](docs/skill-lifecycle.md)
- [Safety Model](docs/safety-model.md)
- [Evaluation Plan](docs/evaluation-plan.md)
- [Demo Suite](docs/demo-suite.md)
- [Data Contracts](docs/contracts/data-contracts.md)
- [Operator Summary Review Pack](docs/operator-summary-review-pack.md)
- [V1.0 Release Contract](docs/v1-release-contract.md)
- [V1.0 Release Notes](docs/v1-release-notes.md)
- [Changelog](CHANGELOG.md)
- [ADR 0001: Markdown-Only MVP](docs/adr/0001-markdown-only-mvp.md)

Supporting design notes and dated tasking live under [docs/internal](docs/internal/README.md).

## Source And Contributions

This repo is open source under the [MIT License](LICENSE). Contributions are welcome inside the local CLI/dev-preview boundary described in [Contributing](CONTRIBUTING.md).

The public proof is the CLI demo suite, evals, v1 smoke gate, and boundary docs. The repo does not claim a hosted service, production safety, autonomous skill promotion, or marketplace behavior.
