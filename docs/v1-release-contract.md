# V1.0 Release Contract

Status: draft for local v1 readiness

This contract defines what Skill-Seeking Agent must promise before the project can be stamped as `1.0.0`. It is not itself a version bump, tag, release note, hosted deployment, marketplace launch, or production-safety claim.

## Product Boundary

V1.0 is a local CLI product for governed skill acquisition.

The v1 product promise is:

```text
A local operator can rely on the CLI to identify capability gaps, validate temporary skills, preserve evidence, ask for human decisions, and admit or route skills only through explicit reviewed paths.
```

V1.0 is still local-first and operator-governed. The agent may draft, validate, load, inspect, and report evidence, but it must not silently promote generated skills, widen permissions, copy generated skills into durable `skills/`, or enable stable routing without explicit human-reviewed evidence.

## Explicit Non-Goals

V1.0 does not promise:

- hosted service behavior;
- production-safe operation;
- external skill marketplace support;
- true sandboxing for untrusted code;
- automatic promotion from temporary or candidate evidence to stable skills;
- automatic stable routing without approval evidence;
- permission widening without explicit human review;
- active governor steering over routing or promotion;
- package dependency installation for candidate skills.

Scripted skills remain trusted-local opt-in subprocesses with guardrails. They are not a true sandbox.

## Stable Local CLI Surfaces

The v1 compatibility surface should include these local CLI categories:

- Task execution and trace: `skill-agent run`, `skill-agent run --json`, `skill-agent explain`.
- Local registry and health inspection: `skill-agent registry`, `skill-agent health`.
- Human input focus: `skill-agent input-requests`, `skill-agent resolve-input-request`.
- Candidate review: `skill-agent candidates`, `skill-agent candidate-usefulness`, `skill-agent skill-receipt`, `skill-agent stable-readiness`, `skill-agent candidate-decision`.
- Negative and checkpoint evidence: `skill-agent negative-evidence`, `skill-agent evidence-checkpoint`, `skill-agent evidence-governor`.
- Managed-prefix proof path: `skill-agent shadow-activation-plan`, `skill-agent shadow-rollback-plan`, `skill-agent shadow-activation-acceptance`, `skill-agent shadow-write-gate`, `skill-agent shadow-managed-write`.
- V1 operator checklist: `skill-agent v1-local-use`, pointing to the managed-prefix-first local-use path without adding a second mutation surface.
- Promotion and admission review: `skill-agent promote-candidate`, `skill-agent admission-plan`, `skill-agent admit-candidate --dry-run`.
- Evaluation: `skill-agent eval`.

The stable routing policy is deferred for v1 and documented in [Stable Routing Policy](stable-routing-policy.md). The detailed JSON surfaces live in [Data Contracts](contracts/data-contracts.md), including the representative v1 fixture freeze for run logs, candidate ledgers, input resolutions, checkpoints, decision reports, and eval reports. Breaking frozen v1 JSON fields should be treated as a deliberate versioned change after v1 is stamped.

## Lifecycle Boundary

The lifecycle vocabulary remains:

```text
requested -> draft -> temporary -> candidate -> stable -> deprecated -> blocked
```

For v1 readiness:

- `requested`, `draft`, and `temporary` are runtime evidence states.
- `candidate` is human-review evidence, not stable admission.
- `stable` must require explicit reviewed evidence and a separate post-v1 stable routing path.
- `blocked` and negative evidence remain visible and must not be erased by later summaries.

Candidate evidence may support a decision. It must not become durable admission or stable routing by itself.

## Safety And Mutation Boundary

V1 commands must make mutation boundaries visible.

Allowed local writes are limited to explicitly documented evidence surfaces, such as:

- run logs and run-scoped artifacts under `runs/` or a caller-supplied run directory;
- append-only input request resolutions;
- local evidence checkpoints;
- run-scoped admission snapshot/staging evidence when explicitly requested;
- run-scoped shadow activation acceptance evidence;
- human-approved managed-prefix writes when every digest/hash/checkpoint gate matches.

V1 commands must not silently mutate:

- durable `skills/`;
- registries;
- candidate ledgers outside the command's documented write surface;
- historical run logs;
- permissions;
- stable routing policy;
- governor behavior.

## Fresh-Checkout Operator Path

A local operator should be able to prove the first-run path from a fresh checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
bash scripts/v1_smoke.sh
```

The smoke helper is a local readiness check. It does not install dependencies, call hosted services, publish artifacts, tag releases, bump versions, admit durable skills, or enable stable routing.

The smoke helper should prove:

- CLI/package availability;
- the v1 local-use checklist;
- the Skill Gauntlet demo path;
- capability-gap smoke eval;
- lifecycle eval;
- agent diagnostic eval;
- v1 release eval;
- one isolated candidate-decision JSON inspection path;
- compileability of `app/`.

## Release Gates

Before stamping `1.0.0`, the release gate should include:

```bash
bash scripts/v1_smoke.sh
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
.venv/bin/skill-agent eval --suite evals/capgap_smoke.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/capgap_v0.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/skill_lifecycle_v0.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/agent_diagnostic_v0.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/v1_release.jsonl --skills-dir skills --runs-dir runs/evals
```

CodeRabbit or an equivalent external review pass should run once for release-relevant changes. Valid correctness, safety, data-loss, contract, and test-confidence findings should be fixed. Preference-only findings should not block a locally green v1 slice unless they reveal real operator confusion.

## Version And Release Artifacts

Context7 guidance for Python Semantic Release identifies `pyproject.toml:project.version` as the project version stamp and supports changelog/release-note generation from release history.

For this repo:

- `pyproject.toml` remains the authoritative package version stamp.
- `CHANGELOG.md` should exist before `1.0.0`.
- `docs/v1-release-notes.md` should summarize abilities, boundaries, proof, and known limitations.
- A `1.0.0` tag should be created only after all release gates pass.
- This contract does not itself authorize a `1.0.0` bump.

## Current Status

The repo is moving toward v1.0. It is not yet v1.0.

Current v1 blockers remain:

- final v1 release eval suite expansion, if later stable routing is included;
- release notes and changelog;
- final `1.0.0` gate.
