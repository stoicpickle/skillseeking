# Durable Candidate Admission Plan: Implementation Plan

## Goal

Add the first durable admission workflow surface as a read-only dry run. The command inspects whether a Skill Candidate Ledger entry is ready for human durable-skill admission review, but it does not copy files, install skills, mutate the ledger, mutate the registry, steer the governor, or promote anything to stable.

## Milestone

Milestone: Durable candidate admission planning

Status: complete

Goal:
Join candidate ledger evidence, immutable run logs, run-scoped temporary skill artifacts, source validation, and durable registry checks into one inspectable admission report.

## Slices

| Slice | Status | Checks |
| --- | --- | --- |
| Admission report contract | complete | Output-only Pydantic models expose dry-run and no-mutation invariants |
| Evidence discovery | complete | Report reads ledger evidence run IDs, matching run logs, and explicit temporary `SKILL.md` paths only |
| Source and registry checks | complete | Report blocks missing/invalid source skills, permission widening, scripted candidates, and same-name durable collisions |
| CLI surface | complete | `skill-agent admission-plan <candidate-id>` supports human and `--json` output |
| Tests and docs | complete | Unit/CLI tests cover readiness, blockers, collisions, warnings, and read-only invariants |

## Contract

Command shape:

```bash
skill-agent admission-plan <candidate-id> --runs-dir runs --skills-dir skills
skill-agent admission-plan <candidate-id> --runs-dir runs --skills-dir skills --json
```

Outcome values:

- `ready_for_durable_review`
- `needs_promotion_approval`
- `evidence_incomplete`
- `blocked`

Invariant fields:

- `dry_run=true`
- `auto_promotion_enabled=false`
- `durable_skill_installed=false`
- `ledger_mutated=false`
- `registry_mutated=false`
- `governor_steering_enabled=false`

## Non-Goals

- No durable copy into `skills/`.
- No durable install workflow.
- No stable promotion.
- No permission widening.
- No active governor behavior.
- No registry admission mutation.
