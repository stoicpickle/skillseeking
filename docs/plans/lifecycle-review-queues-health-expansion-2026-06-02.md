# Lifecycle Review Queues and Health Expansion: Implementation Plan

## Goal

Add advisory review queues over the Skill Candidate Ledger so humans can see which lifecycle records need attention without changing routing, governor behavior, or durable skill admission.

## Milestone

Milestone: Lifecycle review queues and health expansion

Status: working

Goal:
Surface repeated demand, repair-needed, blocked/quarantined, duplicate, and promotion-ready candidate records through existing CLI, JSON, health, and eval proof surfaces.

## Slices

| Slice | Status | Checks |
| --- | --- | --- |
| Derive advisory review queues from ledger evidence | complete | Unit tests classify promotion-ready, repair-needed, blocked/quarantined, duplicate, and repeated-requested candidates |
| Surface queue counts and entries in candidate output | complete | `skill-agent candidates` and `skill-agent candidates --json` show advisory queues without mutating the ledger |
| Expand health summary | complete | `skill-agent health` and JSON include review queue counts |
| Expand lifecycle eval proof | complete | `evals/skill_lifecycle_v0.jsonl` covers repeated-gap, repair-needed, and promotion-ready queue expectations; fixture tests cover blocked/quarantined and duplicate classification |
| Update docs and validation | complete | Docs describe advisory-only queues; validation bundle and CodeRabbit pass before push |

## Queue Contract

Queue names:

- `promotion_ready`: temporary candidate has at least one validation pass and one successful temporary use, has no repair, block, quarantine, or duplicate evidence, and still requires promotion approval.
- `repair_needed`: candidate has validation failures or repair requirements.
- `blocked_or_quarantined`: candidate is blocked or carries block/quarantine evidence.
- `duplicate_merge_needed`: candidate duplicates another candidate contract.
- `repeated_requested_gap`: requested candidate has repeated demand but no draft/temporary evidence yet.

Queues are advisory and may overlap. They must not:

- promote a skill,
- copy any skill into durable `skills/`,
- widen permissions,
- steer routing,
- change governor decisions,
- treat a generated skill's own tests as sufficient promotion evidence.

## Implementation Tasks

- Add a `CandidateReviewQueueItem` contract and derived queue helper.
- Include queue counts/items in candidate JSON output and queue names beside each human candidate card.
- Include queue counts in `LibraryHealthReport` and human health output.
- Add eval expectations for candidate review queues.
- Expand unit tests and lifecycle JSONL cases.
- Update operating roadmap, evaluation plan, data contracts, README, and dev log.

## Validation

Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
.venv/bin/skill-agent eval --suite evals/capgap_smoke.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/capgap_v0.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/skill_lifecycle_v0.jsonl --skills-dir skills --runs-dir runs/evals
coderabbit review --agent -t uncommitted --dir .
```

## Non-Goals

- No candidate-to-stable workflow.
- No durable install/copy workflow.
- No auto-promotion.
- No active governor steering.
- No planner or router rewrite.
