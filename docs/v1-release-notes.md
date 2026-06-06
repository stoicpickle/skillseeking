# V1.0 Release Notes

Status: local v1 release candidate

Skill-Seeking Agent is not stamped or tagged as `1.0.0` yet. These notes describe the current local CLI release-candidate state and the remaining final gate before a version bump or tag.

## Positioning

Skill-Seeking Agent is a local CLI for governed capability acquisition. The product is not a generic agent framework or skill marketplace; the product is the inspectable loop where the agent notices a missing capability, records the needed input/output contract, validates temporary skill evidence, and keeps human review in the path before any stable local use.

## Current Abilities

- Runs local tasks through `skill-agent run` and writes schema-versioned JSON run logs.
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

- No `1.0.0` version stamp, tag, or published release has been created yet.
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

Before a final `1.0.0` stamp, run:

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

Release-relevant changes should also receive one scoped CodeRabbit review or a clearly recorded bounded-stall fallback with local proof.

## Remaining Final Gate

- Keep the v1 release eval at 100 percent pass rate.
- Expand the v1 release eval only if a later decision brings positive stable routing back into v1 scope.
- Run the final validation bundle from the release contract.
- Update `pyproject.toml` to `1.0.0` only after the final gate is clean.
- Create the `1.0.0` tag only after version, changelog, release notes, and proof agree.
