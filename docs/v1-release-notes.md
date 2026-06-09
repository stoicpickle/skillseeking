# V1.0 Release Notes

Status: v1.0 local CLI release

Package version: `1.0.0`

Git release tag: `v1.0.0`

Release date: 2026-06-06

These notes describe the v1.0 local CLI release state: the code is version-stamped, tagged, and considered released for local CLI use. This is not a hosted service, marketplace launch, package publish, production-safety claim, or true-sandbox claim.

## Positioning

Skill-Seeking Agent is a local CLI for governed capability acquisition. The product is not a generic agent framework or skill marketplace; the product is the inspectable loop where the agent notices a missing capability, records the needed input/output contract, validates temporary skill evidence, and keeps human review in the path before any stable local use.

## Current Abilities

- Runs local CLI tasks through `skill-agent run` and writes schema-versioned JSON run logs.
- Explains existing run logs with `skill-agent explain`.
- Loads durable Markdown skills from the local registry and rejects malformed or unsafe skill fixtures.
- Emits structured skill requests when a capability is missing.
- Validates temporary Markdown skills and can load them for a single run.
- Preserves candidate evidence in a skill candidate ledger for human review.
- Exposes input requests and append-only input request resolutions for human decisions.
- Summarizes candidate review state with `skill-agent candidate-decision`.
- Provides deeper advisory proof surfaces including `candidate-usefulness`, `skill-receipt`, `stable-readiness`, `negative-evidence`, `evidence-checkpoint`, and `evidence-governor`.
- Supports a managed-prefix-first local-use lane through `shadow-activation-plan`, `shadow-rollback-plan`, `shadow-activation-acceptance`, `shadow-write-gate`, `shadow-managed-write`, and the read-only `v1-local-use` checklist.
- Runs release and regression evals through `skill-agent eval`, including `evals/v1_release.jsonl`.

## Explicit Boundaries

- No hosted service, package publish, or marketplace release is included in v1.0.
- The CLI is local-only and operator-governed; it is not a hosted service.
- Scripted skills are trusted-local opt-in subprocesses with guardrails, not a true sandbox.
- V1 does not provide an external skill marketplace.
- V1 does not install package dependencies for candidate skills.
- V1 does not silently copy generated skills into durable `skills/`.
- V1 stable local use is managed-prefix-first; durable `skills/` admission is not the v1 lane.
- Stable routing is deferred for v1. Candidate readiness, stable-readiness reports, and managed-prefix writes do not enable normal stable routing.
- Permission widening, durable admission, stable review, stable promotion, and stable routing require explicit reviewed paths; they are not granted by candidate evidence alone.
- Evidence governor and decision reports are advisory. They do not steer routing or grant approval.

## Verification

The canonical local readiness smoke path is:

```bash
bash scripts/v1_smoke.sh
```

The v1.0 release gate is:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
.venv/bin/skill-agent eval --suite evals/capgap_smoke.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/capgap_v0.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/skill_lifecycle_v0.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/agent_diagnostic_v0.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/v1_release.jsonl --skills-dir skills --runs-dir runs/evals
```

Release-relevant changes should also receive one scoped external/manual review or a clearly recorded bounded-stall fallback with local proof.

## Release Gate Result

The release gate passed on the commit tagged `v1.0.0`. Stable routing remains deferred for v1, so the conditional positive stable-routing eval expansion remains out of scope. The named v1 release eval row `v1_release_stable_routing_policy_deferred_even_when_ready` is the intended release proof for that boundary.
