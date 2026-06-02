# Operating Roadmap and Skill Candidate Ledger: Implementation Plan

## Goal

Consolidate the project roadmap into one operating source of truth, then implement the next controlled product capability: a **Skill Candidate Ledger** that records repeated capability gaps, candidate evidence, blocked/quarantine reasons, and human promotion requirements without enabling auto-promotion.

This plan follows the recommended tempo:

```text
stabilize current proof
-> consolidate roadmap
-> validate what exists
-> add one lifecycle ledger
-> expand evals around lifecycle control
-> defer active governor behavior
```

## Implementation Progress

- [x] Chunk 1 — Operating roadmap consolidation.
- [x] Chunk 2 — Evidence checkpoint and validation baseline.
- [x] Chunk 3 — Skill Candidate Ledger data contract and persistence.
- [x] Chunk 4 — Ledger integration with missing-skill requests, temporary skills, validation failures, and rejected skills.
- [x] Chunk 5 — CLI/explain/health surfaces for lifecycle state.
- [x] Chunk 6 — Lifecycle eval expansion and final validation.

## Background

The roadmap now lives across several documents:

- `docs/roadmap.md` describes the phase roadmap from static skills through SkillOps.
- `docs/build-map.md` records completed v0 milestones and proof points.
- `docs/homeostatic-governor.md` documents the trace-only governor layer and future active-control boundary.
- `docs/skill-lifecycle.md` sketches requested/draft/temporary/candidate/stable/deprecated/blocked lifecycle states.

The core agent loop is substantially built: static skills, missing-skill requests, temporary Markdown skills, scripted opt-in skills, repair requests, health reports, malicious skill rejection, demos, evals, calibration, and trace-only governor decisions.

The next gap is not another governor feature. The next gap is an operating lifecycle layer that can remember repeated skill needs and describe what evidence would justify human-governed promotion.

## Locked Decisions

- Do **not** silently promote generated or temporary skills into durable `skills/`.
- Do **not** let generated skills widen permissions without approval.
- Do **not** treat a generated skill's own tests as sufficient promotion evidence.
- Do **not** let active governor controls steer execution yet.
- Keep the first pass docs-only: create `docs/operating-roadmap.md` before changing runtime behavior.
- Treat the Skill Candidate Ledger as a record/evidence layer first, not an autonomous promotion system.

## Non-Goals

This plan does not include:

- Auto-promotion from temporary to candidate or stable.
- Marketplace, signatures, external skill distribution, or UI work.
- True sandboxing beyond the current trusted-local scripted-skill guardrails.
- Active freshness checks, cost/latency routing, or tool-failure steering.
- Broad planner/router rewrites.

## Chunk 1 — Operating Roadmap Consolidation

Create `docs/operating-roadmap.md` as the single near-term operating roadmap.

It should merge:

- completed v0 proof from `docs/build-map.md`,
- phase framing from `docs/roadmap.md`,
- control-layer boundaries from `docs/homeostatic-governor.md`,
- lifecycle states from `docs/skill-lifecycle.md`,
- eval gates from `docs/evaluation-plan.md`,
- explicit "not yet" boundaries.

Recommended shape:

```markdown
# Operating Roadmap

## Current Proven Surface
## Current Control Layer
## Current Lifecycle Boundary
## Next Three Milestones
## Eval and Validation Gates
## Not Yet
## Decision Log
```

Acceptance checks:

- The doc names the next runtime milestone as **Skill Candidate Ledger**.
- It makes auto-promotion explicitly out of scope.
- It lists the required validation checkpoint before runtime changes.
- It links back to the source docs rather than duplicating every detail.

## Chunk 2 — Evidence Checkpoint and Validation Baseline

Before runtime changes, run the existing validation/eval bundle and record the current proof state.

Suggested commands:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m skill_agent eval --suite evals/capgap_smoke.jsonl
.venv/bin/python -m skill_agent eval --suite evals/capgap_v0.jsonl
```

If command names differ, use the current CLI help and update this plan or `docs/operating-roadmap.md` with the verified commands.

Acceptance checks:

- Full test suite result is known.
- Smoke eval result is known.
- v0 eval result is known, or blockers are captured.
- No runtime implementation starts until failures are categorized as unrelated, expected, or blocking.

## Chunk 1–2 Proof State

Completed on 2026-06-01:

- Created `docs/operating-roadmap.md` as the consolidated near-term operating roadmap.
- Recorded **Skill Candidate Ledger** as the next runtime milestone and kept auto-promotion explicitly out of scope.
- Ran the validation/eval baseline before runtime ledger work:
  - `.venv/bin/python -m pytest -q` -> `107 passed in 8.41s`.
  - `.venv/bin/skill-agent eval --suite evals/capgap_smoke.jsonl --skills-dir skills --runs-dir runs/evals` -> `4/4` passed; reports under `runs/evals/eval_report_20260601_154837.*`.
  - `.venv/bin/skill-agent eval --suite evals/capgap_v0.jsonl --skills-dir skills --runs-dir runs/evals` -> `20/20` passed; reports under `runs/evals/eval_report_20260601_154841.*`.
- Local note: `python -m pytest -q` failed in this shell because `python` was not on `PATH`; `.venv/bin/python` was available and used.
- No runtime ledger code was implemented in Chunks 1–2.

## Chunk 3 — Skill Candidate Ledger Contract and Persistence

Add a ledger that records lifecycle evidence for skill requests and candidates.

Likely code touchpoints:

- `app/models.py`
- `app/librarian.py`
- `app/run_log.py`
- `app/skill_requester.py`
- `app/agent_loop.py`
- `tests/test_librarian.py`
- new `tests/test_skill_candidate_ledger.py`

Proposed model concepts:

```text
SkillCandidateStatus:
  requested | draft | temporary | candidate | stable | deprecated | blocked

SkillCandidateLedgerEntry:
  candidate_id
  skill_name
  capability
  status
  first_seen_run_id
  last_seen_run_id
  request_count
  successful_temporary_uses
  validation_pass_count
  validation_failure_count
  safety_flags
  duplicate_of
  quarantine_reason
  block_reason
  promotion_requirements
  human_approval_required
  governor_summary
  evidence_run_ids
  created_at
  updated_at
```

Persistence options:

1. Prefer a simple JSON ledger under `runs/skill_candidate_ledger.json` for the first slice.
2. Keep run logs as the immutable per-run evidence source.
3. Let the ledger be rebuildable or repairable from run logs later.

Acceptance checks:

- Repeated missing-skill requests increment a deterministic ledger entry.
- Ledger entries preserve evidence run IDs.
- Ledger writes are deterministic enough for tests.
- Legacy run logs and health reporting remain tolerant of missing ledger fields.

## Chunk 4 — Integrate Ledger with Lifecycle Events

Wire the ledger to existing lifecycle seams without changing task execution semantics.

Events to record:

- Missing skill request created.
- Temporary skill drafted.
- Temporary skill validation passed.
- Temporary skill validation failed and repair requested.
- Malicious or invalid skill rejected/quarantined.
- Duplicate candidate suspected.
- Human approval required before promotion.

Behavior boundaries:

- A `temporary` skill may still be loaded only through the existing temporary-skill path.
- A `candidate` ledger state does not automatically create or admit a durable skill.
- `blocked` and quarantine reasons should be visible and durable.
- Ledger updates should not change router scoring yet.

Acceptance checks:

- A repeated gap creates one ledger entry with `request_count > 1`, not duplicates.
- Unsafe candidates can be marked `blocked` with a reason.
- Validation failures record repair requirements.
- Duplicate candidates are visible without deleting either source artifact.

## Chunk 5 — CLI, Explain, and Health Surfaces

Expose the ledger in inspectable surfaces.

Likely code touchpoints:

- `app/cli.py`
- `app/cli_output.py`
- `app/explain.py`
- `app/librarian.py`
- tests for CLI/explain/health output

Possible CLI surface:

```bash
skill-agent candidates
skill-agent candidates --json
skill-agent explain <run-log> --include-candidates
```

Minimum output should show:

- skill/capability name,
- lifecycle status,
- request count,
- validation evidence,
- safety/quarantine/block reason,
- promotion requirements,
- whether human approval is required.

Acceptance checks:

- Human-readable output has stable landmarks.
- JSON output has stable fields for evals and future UI/API surfaces.
- `skill-agent explain` can connect a missing-skill request to its ledger entry.
- Existing registry and health commands still work.

## Chunk 6 — Lifecycle Eval Expansion

Add eval cases around lifecycle behavior.

Recommended cases:

- repeated gap increments the same candidate ledger entry,
- unsafe candidate is blocked/quarantined,
- duplicate candidate is flagged,
- temporary validation failure records repair requirements,
- candidate promotion remains human-gated,
- candidate evidence is visible in explain/JSON output.

Likely files:

- `evals/capgap_v0.jsonl`
- optional new `evals/skill_lifecycle_v0.jsonl`
- `app/eval_runner.py`
- `tests/test_eval_runner.py`
- new eval end-to-end tests as needed

Acceptance checks:

- Eval runner can assert lifecycle status and ledger evidence.
- Eval reports distinguish capability decision accuracy from lifecycle evidence accuracy.
- No eval expects auto-promotion.

## Final Validation Bundle

Run after implementation:

```bash
.venv/bin/python -m pytest
.venv/bin/python -m skill_agent eval --suite evals/capgap_smoke.jsonl
.venv/bin/python -m skill_agent eval --suite evals/capgap_v0.jsonl
.venv/bin/python -m skill_agent candidates --json
```

If `skill_lifecycle_v0.jsonl` is added:

```bash
.venv/bin/python -m skill_agent eval --suite evals/skill_lifecycle_v0.jsonl
```

## Success Criteria

This plan is complete when:

- `docs/operating-roadmap.md` exists and becomes the single near-term source of truth.
- The current validation/eval baseline is recorded before runtime changes.
- The Skill Candidate Ledger records repeated requests, evidence, validation outcomes, duplicate/quarantine/block reasons, and promotion requirements.
- Candidate/stable promotion remains human-governed and non-automatic.
- CLI/explain/health surfaces make lifecycle state inspectable.
- Evals assert lifecycle behavior without adding active governor steering.

## Next Deferred Milestones

After this plan lands and evals are stable, consider in order:

```text
quarantine / blocked candidate workflow
-> human promotion workflow
-> lifecycle health report expansion
-> active governor controls
```

Active governor controls should wait until the ledger can tell the system what has happened before the governor starts changing what the system does.
