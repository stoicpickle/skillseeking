# Operating Roadmap

This document is the near-term operating source of truth for Skill-Seeking Agent. It consolidates the project phase roadmap, completed v0 proof, current control-layer boundary, skill lifecycle boundary, and validation gates. Source documents remain authoritative for deeper detail:

- [Build Map](build-map.md)
- [Roadmap](roadmap.md)
- [Homeostatic Governor](homeostatic-governor.md)
- [Skill Lifecycle](skill-lifecycle.md)
- [Evaluation Plan](evaluation-plan.md)
- [V1.0 Release Tasking](v1-release-tasking.md)
- [V1.0 Release Contract](v1-release-contract.md)

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
- Candidate usefulness packets through `skill-agent candidate-usefulness`, deriving temporary-skill usefulness support from preserved run-log evidence and optional pinned baseline/treatment comparisons without claiming statistical lift.
- Counterfactual skill receipts through `skill-agent skill-receipt`, aggregating origin, utility, containment, compatibility, approval, and reversibility proof without enabling durable writes.
- Negative evidence reports through `skill-agent negative-evidence`, keeping rejected, deferred, blocked, repair, duplicate, and quarantined evidence visible from existing ledgers.
- Evidence checkpoints through `skill-agent evidence-checkpoint`, appending or verifying a local hash-chain over core `runs/` evidence without rewriting historical evidence.
- Non-steering evidence governor reports through `skill-agent evidence-governor`, recommending only ask, test_more, deny, or defer from existing proof surfaces without granting approval or steering execution.
- Managed shadow activation plans through `skill-agent shadow-activation-plan`, naming content-addressed store paths, profile generations, activation pointers, and rollback targets without writing the managed prefix.
- Shadow rollback plans through `skill-agent shadow-rollback-plan`, verifying existing profile pointer and generation rollback evidence without creating generations, switching profiles, or mutating ledgers.
- Managed-prefix activation acceptance reports through `skill-agent shadow-activation-acceptance`, proving store/generation copy, pointer switch, interrupted-pointer recovery, conflict blocking, and rollback mechanics only inside a run-scoped acceptance prefix.
- Human write-gate verification through `skill-agent shadow-write-gate`, proving prepared acceptance evidence, restored rollback pointer, supplied exact acceptance digest, and unchanged source hash before the managed-prefix write command runs.
- Human-approved managed-prefix write mode through `skill-agent shadow-managed-write`, writing only the shadow managed store, profile generation, profile pointer, and managed-prefix-local receipt after exact digest/hash/checkpoint matches plus a separate non-expired `managed_write_plan_digest` approval; durable `skills/`, stable routing, registries, ledgers, permission widening, and governor steering remain unchanged.
- Stable readiness reports through `skill-agent stable-readiness`, composing candidate ledger, skill receipt, negative evidence, and durable registry evidence to advise candidate-to-stable review without authorizing stable promotion or routing.
- Candidate decision summaries through `skill-agent candidate-decision`, compressing stable-readiness, receipt, usefulness, admission, and negative evidence into one advisory next decision without granting approval, install, promotion, routing, permission, or governor authority.
- Advisory lifecycle review queues for promotion-ready, repair-needed, blocked/quarantined, duplicate-merge-needed, and repeated-requested-gap candidate records.
- Durable admission dry-run reports through `skill-agent admission-plan`, without copying, installing, or promoting skills.
- Remote progress input focus through `InputRequest`, `skill-agent input-requests`, `INPUT_NEEDED`, `INPUT_FOCUS`, append-only input request resolutions, and resolution-ledger eval assertions.

The current product proof is a CLI-first prototype, not a production agent framework. The public phase framing remains in [Roadmap](roadmap.md): static skill loader -> skill request mode -> Markdown-only Skillsmith -> scripted skills -> SkillOps.

The next product risk is proof-surface sprawl: many reports now expose useful evidence, but the operator still needs a smaller answer about what decision to make next. Near-term work should compress existing evidence into clearer advisory decisions before adding durable admission, stable routing, dependency installation, UI, marketplace, or active governor authority.

The current v1 planning source is [V1.0 Release Tasking](v1-release-tasking.md), and the local v1 promise is drafted in [V1.0 Release Contract](v1-release-contract.md). The active slice is [V1 Contract And Fresh-Checkout Operator Path](plans/v1-contract-and-fresh-checkout-operator-path-2026-06-06.md).

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
- `shadow-managed-write` is managed-prefix activation only; it is not candidate-to-stable promotion, durable `skills/` admission, stable routing, registry mutation, or ledger mutation.
- No generated skill may widen permissions without approval.
- A generated skill's own tests are not sufficient promotion evidence.
- A `candidate` record is evidence only; it is not automatic admission to the durable registry.

## Next Three Milestones

1. **Remote progress and input focus**
   - Current progress: input-needed evidence is normalized across safety approvals, repair review, candidate promotion approval, and durable admission review. Queue output now includes run-log, candidate-ledger, and resolution-ledger source diagnostics, missing-evidence fixture coverage, dry-run decision resolution, append-only resolution evidence, eval rows for deferred/resolved/repeated resolution states, negative-evidence reporting over unfavorable resolution history, local evidence checkpointing over core run evidence, and non-steering evidence-governor recommendations.
   - Next coverage: keep resolution, checkpoint, and admission evidence in sync as future durable-admission proof gates are added.
   - Keep queues advisory; do not let them steer routing, promotion, registry admission, or governor behavior.

2. **Human promotion workflow design**
   - Current progress: `promote-candidate` records reviewer/notes approval and can move eligible temporary ledger entries to `candidate` evidence status; `candidate-usefulness` summarizes whether preserved temporary-skill evidence actually supports review and can compare a pinned no-temporary-skill baseline against a pinned temporary-skill treatment; `skill-receipt` aggregates origin, utility, containment, compatibility, approval, and reversibility categories for one candidate; `admission-plan` can inspect durable review readiness without mutating durable skills; durable admission workflow design defines the required proof gates; `admit-candidate --dry-run` previews source fingerprint, target path, source snapshot retention path, collision policy, permission approval evidence, permission/dependency diffs, exact plan digest approval, no-write dependency evidence (`dependency_install_contract`, `dependency_plan_digest`, and optional run-scoped manifest), write blockers, and required approval records while rejecting write mode; `shadow-activation-plan` previews a managed-prefix store/generation/pointer/rollback plan without writing it; `shadow-rollback-plan` verifies existing pointer/generation rollback evidence without writing it; `shadow-activation-acceptance` exercises store/generation copy, pointer switch, interrupted-pointer recovery, conflict blocking, and rollback only inside a run-scoped acceptance prefix; `shadow-write-gate` verifies the already prepared acceptance evidence, supplied exact acceptance digest, source hash, and restored rollback pointer without writing; `shadow-managed-write` is the first real write surface and is confined to the shadow managed prefix.
   - Operator sequence for `shadow-managed-write`: prepare durable admission proof, prepare acceptance evidence, verify `shadow-write-gate`, dry-run `shadow-managed-write` to capture `managed_write_plan_digest`, record a separate non-expired write approval with that digest, checkpoint and verify evidence, then execute `shadow-managed-write --no-dry-run` with every expected digest/hash plus the latest checkpoint hash and `--write-approval-id`.
   - Next coverage: candidate-to-stable review rehearsal through `stable-readiness`, stable-readiness eval assertions, promotion review queues, durable `skills/` admission, and stable routing only after stable-readiness evidence, the managed-prefix boundary, and no-write dependency evidence boundary remain proven. `stable-readiness` is advisory only: it is not stable promotion, durable `skills/` admission, stable routing, registry mutation, ledger mutation, permission widening, or governor steering. Dependency evidence is not dependency installation, candidate-to-stable promotion, durable `skills/` admission, registry mutation, ledger mutation, stable routing, or governor steering.
   - Current decision compression: `candidate-decision` uses existing proof reports to return `ask_human`, `test_more`, `deny`, or `defer` plus source-backed reasons and the next `stable-readiness` command, without creating new persistence or authority.
   - Keep permission widening human-gated and evidence-backed.

3. **Lifecycle review queues and health expansion**
   - Current progress: `skill-agent candidates`, `skill-agent candidates --json`, `skill-agent health`, health JSON, `skill-agent negative-evidence`, `skill-agent evidence-checkpoint`, and `skill-agent evidence-governor` now surface derived advisory review, negative-evidence, local checkpoint, and non-steering recommendation records.
   - Next coverage: more blocked/quarantined and duplicate eval rows using explicit fixture setup, plus durable candidate-to-stable workflow design.
   - Keep all queues advisory; do not let them steer routing, promotion, registry admission, or governor behavior.

## Eval and Validation Gates

Before Skill Candidate Ledger runtime changes, record a clean baseline or categorize any failures as unrelated, expected, or blocking.

Validated command set for this repository:

```bash
.venv/bin/python -m pytest -q
.venv/bin/skill-agent eval --suite evals/capgap_smoke.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/capgap_v0.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/skill_lifecycle_v0.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/agent_diagnostic_v0.jsonl --skills-dir skills --runs-dir runs/evals
```

CI currently runs the full test suite with `python -m pytest -q`, smoke, lifecycle, and agent diagnostic evals through the installed `skill-agent` script, and `python -m compileall -q app`; see [.github/workflows/tests.yml](../.github/workflows/tests.yml). In this shell, `python` was not on `PATH`, so the local baseline used `.venv/bin/python` and `.venv/bin/skill-agent`.

## Testing/Iteration Readiness Checkpoint

Status: ready after the validation bundle passes.

The repo is ready for local testing and iteration of the current CLI prototype when:

- the full pytest suite passes,
- `python -m compileall -q app` passes,
- capability-gap smoke and v0 evals pass,
- lifecycle eval passes,
- agent diagnostic eval passes and exposes diagnostic dimensions plus input-focus assertions,
- lifecycle/admission acceptance coverage proves temporary skill creation, human candidate approval, and `admission-plan` without durable skill mutation,
- no durable copy/install workflow has been introduced,
- governor behavior remains trace-only,
- scripted skills remain trusted-local opt-in and are not described as sandboxed.

### Readiness proof state — 2026-06-03

Status: passed for local validation; the current CLI prototype is ready for local testing and iteration inside the documented boundaries. CodeRabbit review has repeatedly stalled after `tools_completed` on recent slices, so local validation and manual review are the current reliable proof path.

| Check | Command | Result | Notes |
| --- | --- | --- | --- |
| Full test suite | `.venv/bin/python -m pytest -q` | passed | `214 passed in 27.33s`. |
| Compile app | `.venv/bin/python -m compileall -q app` | passed | No compile errors. |
| Diff check | `git diff --check` | passed | No whitespace errors. |
| Smoke eval | `.venv/bin/skill-agent eval --suite evals/capgap_smoke.jsonl --skills-dir skills --runs-dir runs/evals` | passed | `4/4` passed, task pass rate `1.0`, trace completeness `4 / 4`; report: `runs/evals/eval_report_20260603_154806_598278.json`. |
| v0 eval | `.venv/bin/skill-agent eval --suite evals/capgap_v0.jsonl --skills-dir skills --runs-dir runs/evals` | passed | `20/20` passed, task pass rate `1.0`, trace completeness `20 / 20`; report: `runs/evals/eval_report_20260603_154814_748619.json`. |
| Lifecycle eval | `.venv/bin/skill-agent eval --suite evals/skill_lifecycle_v0.jsonl --skills-dir skills --runs-dir runs/evals` | passed | `4/4` passed, task pass rate `1.0`, trace completeness `4 / 4`; report: `runs/evals/eval_report_20260603_154806_645953.json`. |
| Agent diagnostic eval | `.venv/bin/skill-agent eval --suite evals/agent_diagnostic_v0.jsonl --skills-dir skills --runs-dir runs/evals` | passed | `16/16` passed, task pass rate `1.0`, trace completeness `16 / 16`; report: `runs/evals/eval_report_20260603_154814_636176.json`. |
| CodeRabbit review | `coderabbit review --agent -t uncommitted --dir /Users/russ/Documents/Russ/skillseekingagent` | stalled | Bounded review reached `tools_completed`, entered `reviewing`, then remained heartbeat-only; the process was terminated. No findings were returned. |

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
- Treating `shadow-managed-write` as durable `skills/` admission or stable routing.
- Automatic candidate-to-stable promotion.
- Permission widening without approval.
- Treating a generated skill's own tests as sufficient promotion evidence.
- Marketplace, signatures, external distribution, or UI work.
- True sandboxing beyond current trusted-local scripted-skill guardrails.
- Active freshness checks, active cost/latency routing, active tool-failure steering, or other governor-controlled execution changes.
- Broad planner or router rewrites.

## Decision Log

- 2026-06-04: Stable-readiness eval coverage now includes ready-for-review, duplicate-blocked, and negative-evidence-blocked candidate-to-stable rehearsal rows while stable review, stable promotion, and stable routing remain unauthorized.
- 2026-06-04: Captured external review tasking in `docs/plans/operator-decision-load-and-stable-review-rehearsal-2026-06-04.md`; next work should reduce operator decision overload by strengthening stable-readiness review rehearsal and eval coverage before adding stable routing or durable admission authority.
- 2026-06-06: Added `skill-agent candidate-decision` as the first compact operator-decision summary over existing candidate proof reports. It returns only advisory decisions and leaves approval, install, stable promotion, stable routing, permission widening, evidence mutation, registry mutation, and governor steering disabled.
- 2026-06-06: Started the v1 contract and fresh-checkout operator path slice. `scripts/v1_smoke.sh` is the local readiness smoke helper; it does not stamp `1.0.0`, publish releases, admit durable skills, enable stable routing, claim true sandboxing, or add hosted/marketplace scope.

- 2026-06-01: Consolidated near-term roadmap into this document before runtime Skill Candidate Ledger work.
- 2026-06-01: Named **Skill Candidate Ledger** as the next runtime milestone.
- 2026-06-02: Skill Candidate Ledger is landed; next work is lifecycle eval expansion, human promotion workflow design, and lifecycle review queues.
- 2026-06-02: Added first human promotion workflow: reviewer/notes approval can mark eligible temporary ledger entries as `candidate` evidence without durable install or auto-promotion.
- 2026-06-02: Added advisory lifecycle review queues and health expansion for promotion-ready, repair-needed, blocked/quarantined, duplicate, and repeated-requested candidate evidence.
- 2026-06-02: Added durable candidate admission dry-run reports; durable copy/install and stable promotion remain out of scope.
- 2026-06-03: Added Remote Progress and Input Focus as the next slice: input-needed evidence is explicit and read-only across run logs, queue output, health, explain, admission plans, and eval assertions.
- 2026-06-03: Added append-only input request resolution evidence through `runs/input_request_resolutions.json`; source run logs, candidate ledgers, durable skills, and governor behavior remain untouched.
- 2026-06-03: Added resolution-ledger eval expectations proving deferred requests stay active, resolved requests leave the active queue, and repeated resolution history appends new evidence.
- 2026-06-03: Added durable admission workflow design; `ready_for_durable_review` and `approve_review` remain review checkpoints, not install/copy approval.
- 2026-06-03: Added `admit-candidate --dry-run` durable admission mutation preview; target path/source hash are inspectable, but `--no-dry-run` is rejected and no durable files or ledgers are mutated.
- 2026-06-03: Extended `admit-candidate --dry-run` with a durable write-plan contract for collision policy, destination paths, source snapshot retention, permission approval evidence, and historical-evidence immutability before any real copy/install mode exists.
- 2026-06-03: Added a no-write durable admission acceptance harness proving source hash drift, snapshot path planning, collision approval, permission approval, destination planning, and no mutation before enabling real copy/install behavior.
- 2026-06-03: Added opt-in dry-run write evidence preparation; `--prepare-write-evidence` verifies the source hash, retains a run-scoped snapshot, stages the exact destination copy under `runs/admission_staging/`, and still does not copy/install into durable `skills/`.
- 2026-06-03: Added `candidate-usefulness` read-only packets, proving preserved temporary-skill validation/load/result evidence before admission review without mutating ledgers or durable skills.
- 2026-06-03: Added proof-carrying capability roadmap and paired baseline/treatment `candidate-usefulness` comparison; valid pairs remain read-only evidence and contaminated baselines are rejected.
- 2026-06-03: Added exact dry-run admission plan digests; `admit-candidate` now requires matching non-expired `approve_review` notes before a preview can become ready or prepare run-scoped write evidence.
- 2026-06-03: Added permission/dependency diff packets to durable admission preview, including added permission classes, added tools, dependency declaration keys, and blockers for dependency declarations without exact realization.
- 2026-06-03: Added exact dependency realization evidence: dependency declarations can carry `dependency_realization` entries with name/version/sha256, clearing missing-realization evidence while still blocking install because dependency install support is intentionally absent.
- 2026-06-03: Added counterfactual skill receipts through `skill-agent skill-receipt`; receipts aggregate existing read-only proof surfaces and keep missing promotion approval, plan approval, and rollback support visible as blockers or partial proof.
- 2026-06-03: Added negative evidence reports through `skill-agent negative-evidence`; reports read existing candidate and resolution ledgers to keep reject/defer/block/repair decisions and blocked/repair/duplicate candidate evidence visible without mutating history.
- 2026-06-03: Added local evidence checkpoints through `skill-agent evidence-checkpoint`; dry-run computes the next checkpoint, `--no-dry-run` appends only `runs/evidence_checkpoints.json`, and `--verify` checks the hash-chain plus current evidence without rewriting historical evidence.
- 2026-06-03: Added non-steering evidence governor reports through `skill-agent evidence-governor`; reports recommend ask/test_more/deny/defer from skill receipt, negative evidence, and checkpoint proof without granting approval, installing, promoting, widening permissions, routing, or steering execution.
- 2026-06-03: Added managed shadow activation plans through `skill-agent shadow-activation-plan`; plans read existing generation directories when present and compute the next profile generation, activation pointer, rollback target, and shadow digest without creating files or switching profiles.
- 2026-06-03: Added shadow rollback plans through `skill-agent shadow-rollback-plan`; plans read existing profile pointers and generation directories to verify rollback readiness or report rollback blockers without mutating managed prefixes, ledgers, durable skills, registry, or governor behavior.
- 2026-06-03: Added managed-prefix activation acceptance reports through `skill-agent shadow-activation-acceptance`; with `--prepare-acceptance-evidence`, the command creates or reuses matching acceptance files under `runs/` only and verifies pointer switch plus rollback without touching durable skills or the real managed prefix.
- 2026-06-03: Hardened the managed-prefix activation acceptance harness with pointer-before reporting, interrupted activation recovery, and conflict blocking for mismatched acceptance files or unexpected pointer targets.
- 2026-06-03: Added `skill-agent shadow-write-gate`; it verifies prepared acceptance evidence, supplied exact acceptance digest, unchanged source hash, and restored rollback pointer without preparing evidence or enabling real managed-prefix writes.
- 2026-06-04: Added `skill-agent shadow-managed-write` as the first human-approved real write surface; it is confined to the shadow managed prefix and does not admit durable `skills/`, enable stable routing, mutate registries or ledgers, widen permissions, or steer the governor.
- 2026-06-04: Added `skill-agent stable-readiness` as an advisory candidate-to-stable evidence report; it does not mark candidates stable, authorize stable promotion, enable stable routing, mutate ledgers or registries, widen permissions, or steer the governor.
- 2026-06-01: Reaffirmed that auto-promotion and permission widening remain out of scope without human approval.
- 2026-06-01: Required full test, smoke eval, and v0 eval baseline before runtime ledger changes.
- 2026-06-01: Recorded passing baseline: full tests `107 passed`, smoke eval `4/4`, and v0 eval `20/20`.
