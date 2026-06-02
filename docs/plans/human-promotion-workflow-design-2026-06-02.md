# Human Promotion Workflow Design: Implementation Plan

## Goal

Add the first explicit, human-governed promotion workflow for Skill Candidate Ledger entries. This workflow records a human approval decision and moves an eligible ledger entry to `candidate` status, while preserving the core safety boundary: no skill files are copied into durable `skills/`, no permissions are widened, and the governor does not steer execution.

## Plan

- [x] Planning pass with current Typer/Pydantic guidance via Context7.
- [x] Add promotion approval contract fields to candidate ledger entries.
- [x] Add ledger helper for human promotion approval with eligibility gates.
- [x] Add CLI command for human promotion approval and JSON/human output.
- [x] Update candidate output, explain output, docs, and tests.
- [x] Validate, run CodeRabbit, fix medium/high findings, note small findings for automation.
- [x] Schedule 2am small-finding automation with the local scheduling app if available.
- [ ] Commit and push.

## Workflow Contract

Command shape:

```bash
skill-agent promote-candidate <candidate-id> --reviewer <name> --notes <text> --runs-dir runs
skill-agent promote-candidate <candidate-id> --reviewer <name> --notes <text> --json
```

Rules:

- Only `temporary` entries can be promoted to ledger `candidate` in this first slice.
- Blocked/quarantined/duplicate entries cannot be promoted.
- Entries with validation failures cannot be promoted.
- At least one validation pass and one successful temporary use are required.
- Human reviewer and notes are required.
- Promotion records are ledger evidence only; no durable skill file is created or loaded.

## Non-goals

- No candidate-to-stable workflow.
- No durable copy into `skills/`.
- No registry admission changes.
- No active governor behavior.
