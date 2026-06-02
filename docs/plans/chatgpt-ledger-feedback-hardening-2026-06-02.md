# ChatGPT Ledger Feedback Hardening Plan

## Source

Feedback source: `/Users/russ/.codex/attachments/329340cd-a3cd-4344-8f40-77bba702b9c8/pasted-text.txt`.

## Critical Feedback Extracted

The Skill Candidate Ledger is landed enough to keep, but it should be hardened before any active governor behavior. The important critiques are:

1. **Runtime ledger failure policy is implicit.** If the summary ledger is corrupt or locked, `run_task()` can fail after the immutable run log has already been written. The feedback recommends preserving the task result and treating ledger update failure as degraded evidence synthesis, not a failed task.
2. **Human-facing approval wording is ambiguous.** `Human approval required` can be misread as current-run approval instead of durable promotion approval. Human CLI/explain output should say `Promotion approval required` while preserving the internal field name.
3. **Docs are stale now that the ledger exists.** `docs/operating-roadmap.md` still frames Skill Candidate Ledger as next, `docs/build-map.md` lacks the completed milestone, `README.md` omits candidate/explain lifecycle commands, `docs/evaluation-plan.md` should mention lifecycle expectations, and `docs/architecture.md` should remove the obsolete `CREATE_TEMP_SKILL` checker-decision wording.
4. **P0 tests should cover degraded ledger runtime behavior and wording.** Add focused tests for corrupt ledger behavior through `agent_loop` and promotion-approval wording in candidate/explain surfaces.

## Implementation Plan

- [x] Use Context7 for current Typer CLI testing and Pydantic JSON/contract guidance.
- [x] Add degraded ledger update handling in `app/agent_loop.py` after `write_run_log()`.
  - Preserve the run result if `record_run_in_candidate_ledger()` raises.
  - Add trace evidence that ledger recording failed.
  - Do not auto-promote or change routing/governor behavior.
- [x] Update human-facing candidate wording in `app/cli_output.py` and `app/explain.py` to `Promotion approval required`.
- [x] Add focused tests in `tests/test_skill_candidate_ledger.py` and `tests/test_cli_explain.py`.
- [x] Update docs: `docs/operating-roadmap.md`, `docs/build-map.md`, `README.md`, `docs/evaluation-plan.md`, and `docs/architecture.md`.
- [x] Run validation bundle.
- [x] Run CodeRabbit, fix valid findings, revalidate, commit, and push.

## Non-Goals

- No active governor steering.
- No durable auto-promotion.
- No human promotion workflow yet.
- No broad router/planner rewrite.
