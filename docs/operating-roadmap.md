# Operating Roadmap

This document is the near-term operating source of truth for Skill-Seeking Agent. It consolidates the project phase roadmap, completed v0 proof, current control-layer boundary, skill lifecycle boundary, and validation gates. Source documents remain authoritative for deeper detail:

- [Build Map](build-map.md)
- [Roadmap](roadmap.md)
- [Homeostatic Governor](homeostatic-governor.md)
- [Skill Lifecycle](skill-lifecycle.md)
- [Evaluation Plan](evaluation-plan.md)

## Current Proven Surface

The v0 surface is implemented and proven through the completed milestones in the [Build Map](build-map.md):

- Static skill loading and routing from local `skills/` metadata.
- Structured missing-skill requests when a needed capability is absent.
- Markdown-only temporary skill drafting, validation, and one-run loading.
- Explicitly enabled trusted-local scripted skills with validation and execution logs.
- Skill-library health reporting from local metadata and run logs.
- Malicious or suspicious skill rejection before routing or loading.
- Canonical demos, acceptance harnesses, gauntlet demo, eval harness, and 20-task capability-gap calibration.
- Skill Candidate Ledger evidence tracking for repeated gaps, temporary outcomes, repair requirements, blocked/quarantined skills, duplicate contracts, and promotion requirements.
- Candidate review surfaces through `skill-agent candidates`, `skill-agent candidates --json`, `skill-agent health`, and `skill-agent explain --include-candidates`.

The current product proof is a CLI-first prototype, not a production agent framework. The public phase framing remains in [Roadmap](roadmap.md): static skill loader -> skill request mode -> Markdown-only Skillsmith -> scripted skills -> SkillOps.

## Current Control Layer

The current control layer is trace-only. Per [Homeostatic Governor](homeostatic-governor.md), the governor records deterministic decision evidence for capability decisions but does not steer execution.

Current control decisions include:

- `USE_SKILL`
- `REQUEST_SKILL`
- `ASK_HUMAN`
- `ABORT_UNSAFE`

Current boundaries:

- The governor may record confidence, risk, reversibility, approval need, freshness need, failure history, cost/latency concern, decision, and reason.
- The governor may appear in trace events, run logs, explain output, eval assertions, and missing-skill request control summaries.
- The governor must not change routing thresholds, skill loading, temporary skill drafting/loading, safety classification, or result-category precedence yet.
- Active governor controls remain deferred until lifecycle evidence is durable and inspectable.

## Current Lifecycle Boundary

The lifecycle vocabulary is defined in [Skill Lifecycle](skill-lifecycle.md):

```text
requested -> draft -> temporary -> candidate -> stable -> deprecated -> blocked
```

Current runtime behavior covers `requested`, `draft`, `temporary`, and `blocked`-style rejection/quarantine evidence through the landed **Skill Candidate Ledger**: a durable summary record for repeated gaps, candidate evidence, validation outcomes, duplicate/quarantine/block reasons, and promotion requirements. Run logs remain the immutable evidence source; the ledger is rebuildable summary evidence and should not control execution.

Promotion remains human-governed:

- No generated or temporary skill may silently become a durable skill in `skills/`.
- No generated skill may widen permissions without approval.
- A generated skill's own tests are not sufficient promotion evidence.
- A `candidate` record is evidence only; it is not automatic admission to the durable registry.

## Next Three Milestones

1. **Lifecycle eval expansion**
   - Current progress: the lifecycle smoke suite now covers repeated requested gaps, temporary-skill success, and repair-required validation failure.
   - Next coverage: blocked/quarantined candidates, duplicate candidates, promotion gates, and explain/JSON visibility.
   - Distinguish capability decision accuracy from lifecycle evidence accuracy.

2. **Human promotion workflow design**
   - Define the explicit review command/process for moving a ledger entry toward durable `candidate` status.
   - Keep promotion and permission widening human-gated and evidence-backed.

3. **Lifecycle review queues and health expansion**
   - Surface repeated-demand, repair-needed, blocked, duplicate, and promotion-ready review queues.
   - Keep all queues advisory; do not let them steer routing or governor behavior yet.

## Eval and Validation Gates

Before Skill Candidate Ledger runtime changes, record a clean baseline or categorize any failures as unrelated, expected, or blocking.

Validated command set for this repository:

```bash
.venv/bin/python -m pytest -q
.venv/bin/skill-agent eval --suite evals/capgap_smoke.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/capgap_v0.jsonl --skills-dir skills --runs-dir runs/evals
```

CI currently runs the full test suite with `python -m pytest -q`, the smoke eval through the installed `skill-agent` script, and `python -m compileall -q app`; see [.github/workflows/tests.yml](../.github/workflows/tests.yml). In this shell, `python` was not on `PATH`, so the local baseline used `.venv/bin/python` and `.venv/bin/skill-agent`.

### Baseline proof state — 2026-06-01

Status: passed; runtime Skill Candidate Ledger work is unblocked by the current validation baseline.

| Check | Command | Result | Notes |
| --- | --- | --- | --- |
| Full test suite | `.venv/bin/python -m pytest -q` | passed | `107 passed in 8.41s`. Initial `python -m pytest -q` attempt failed because `python` was not on `PATH`. |
| Smoke eval | `.venv/bin/skill-agent eval --suite evals/capgap_smoke.jsonl --skills-dir skills --runs-dir runs/evals` | passed | `4/4` passed, task pass rate `1.0`, average request quality `4.6`, trace completeness `4 / 4`; reports: `runs/evals/eval_report_20260601_154837.json` and `.md`. |
| v0 eval | `.venv/bin/skill-agent eval --suite evals/capgap_v0.jsonl --skills-dir skills --runs-dir runs/evals` | passed | `20/20` passed, task pass rate `1.0`, average request quality `4.6`, trace completeness `20 / 20`; reports: `runs/evals/eval_report_20260601_154841.json` and `.md`. |

Runtime ledger implementation may start after this docs-only checkpoint; this update did not implement runtime ledger code.

## Not Yet

The following are explicitly out of scope for the next runtime milestone:

- Auto-promotion from temporary artifacts to durable `skills/`.
- Automatic candidate-to-stable promotion.
- Permission widening without approval.
- Treating a generated skill's own tests as sufficient promotion evidence.
- Marketplace, signatures, external distribution, or UI work.
- True sandboxing beyond current trusted-local scripted-skill guardrails.
- Active freshness checks, active cost/latency routing, active tool-failure steering, or other governor-controlled execution changes.
- Broad planner or router rewrites.

## Decision Log

- 2026-06-01: Consolidated near-term roadmap into this document before runtime Skill Candidate Ledger work.
- 2026-06-01: Named **Skill Candidate Ledger** as the next runtime milestone.
- 2026-06-02: Skill Candidate Ledger is landed; next work is lifecycle eval expansion, human promotion workflow design, and lifecycle review queues.
- 2026-06-01: Reaffirmed that auto-promotion and permission widening remain out of scope without human approval.
- 2026-06-01: Required full test, smoke eval, and v0 eval baseline before runtime ledger changes.
- 2026-06-01: Recorded passing baseline: full tests `107 passed`, smoke eval `4/4`, and v0 eval `20/20`.
