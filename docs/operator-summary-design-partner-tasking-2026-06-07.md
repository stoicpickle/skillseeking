# Operator-Summary Design Partner Tasking

Status: complete

Source review: pasted external review dated 2026-06-07

This tasking list converts the latest review into repo-grounded next work. It
does not replace [Post-v1 Public Dev-Preview Tasking](post-v1-public-dev-preview-tasking-2026-06-07.md), which is complete through public-preview hardening. This list starts the next product question: can a cold technical reviewer understand the governed capability-gap loop through `operator-summary` without reading every evidence surface first?

## Current Read

The review's core judgment matches the current repo:

```text
Do not add more autonomy yet.
Make the governed capability-gap loop easier to review.
Use operator-summary as the front door.
```

The strongest product wedge is still:

```text
Evidence-first governed capability acquisition for local agents.
```

Put more plainly, Skill-Seeking Agent is a local CLI workbench for making agent capability gaps reviewable before they become agent authority.

## Source Material Checked

- Pasted external review dated 2026-06-07
- `docs/post-v1-public-dev-preview-tasking-2026-06-07.md`
- `docs/design-partner-feedback.md`
- `docs/demo-suite.md`
- `docs/product-manager.md`
- `README.md`
- Current branch state at `f151370`

## Already Satisfied Or Mostly Satisfied

These should not become duplicate work unless future edits regress them.

- Public-preview hardening is complete through CI gates, launch proof, launch demo, public-claims tests, operator summary, adversarial eval expansion, no-mutation smoke coverage, and strategy docs.
- `docs/design-partner-feedback.md` already defines the 3 to 5 partner feedback loop and friction template.
- `docs/demo-suite.md` already names `operator-summary` as the follow-up operator index after the launch demo.
- `operator-summary` is read-only and reports active input requests, candidate queues, promotion-ready candidates, missing evidence, unsafe/negative evidence, unsafe run-log items, checkpoint deltas, and next steps.
- Durable admission remains dry-run/preview only; positive stable routing and active governor steering remain deferred.

## P0 Next Product Slice

### 1. Build A Design-Partner Review Pack Around `operator-summary`

Goal:
Make the current proof surfaces legible to a cold technical reviewer in one short path.

Tasks:

- Add a review-pack document, for example `docs/operator-summary-review-pack.md`.
- Show one command path:
  - install or use existing editable install;
  - run `bash scripts/run_launch_demo.sh`;
  - run or inspect `skill-agent operator-summary --runs-dir <runs-dir>`;
  - inspect one run log or `skill-agent explain`;
  - inspect the candidate decision only as supporting evidence.
- Include one sample transcript or expected output excerpt for `operator-summary`.
- Add a "what decision should the operator make?" section.
- Add a "what does not happen" section:
  - no durable generated-skill admission;
  - no stable routing;
  - no hosted service;
  - no marketplace;
  - no true sandbox claim;
  - no autonomous promotion;
  - no active governor steering.
- Add a small evidence map:
  - run log;
  - candidate ledger;
  - input request / resolution ledger;
  - candidate-decision;
  - operator-summary;
  - v1 smoke no-mutation proof.
- Update README and `docs/design-partner-feedback.md` so design partners start with the review pack before deeper report docs.

Checks:

- A fresh reviewer can explain the product loop in under 10 minutes.
- `operator-summary` is presented as the first inspection command after the demo/run.
- The transcript says `candidate` means review evidence, not admission.
- The pack reduces operator confusion without adding a new authority surface.
- Existing docs avoid production, hosted, marketplace, true sandbox, autonomous promotion, durable admission, positive stable-routing, and active-governor claims.

Recommended validation:

```bash
.venv/bin/python -m pytest -q tests/test_launch_demo.py tests/test_operator_summary.py tests/test_v1_release_docs.py
bash scripts/v1_smoke.sh
git diff --check
```

Questions before implementation:

- What is the single operator decision the review pack should end on?
- Does the path use `operator-summary` as the front door, or does it still force users into raw ledgers?
- Which misconception should the transcript prevent first: candidate equals admission, temporary skill equals durable skill, or stable-readiness equals stable routing?

## P1 Architecture And Evidence Slices

### 2. Refresh Durable Admission / Candidate-To-Stable Design Before Implementation

Goal:
Define what proof must exist before a candidate can move from review evidence toward any durable or stable local-use state.

Tasks:

- Review existing durable-admission and managed-prefix docs before writing anything new.
- Add a short RFC or update the existing design docs with the current post-v1 state.
- Keep this design-only: do not add durable `skills/` admission, stable routing, dependency installation, or new write authority.
- Separate these concepts clearly:
  - candidate evidence;
  - promotion approval;
  - durable admission review;
  - managed-prefix local use;
  - stable routing.
- Name required proof:
  - source hash;
  - plan digest;
  - checkpoint hash;
  - approval ID;
  - approval expiry;
  - collision policy;
  - permission/dependency diff;
  - rollback/deactivation evidence.
- Include failure cases:
  - stale source;
  - expired approval;
  - digest mismatch;
  - permission widening;
  - duplicate candidate;
  - negative evidence present;
  - missing checkpoint;
  - symlink or path escape.

Checks:

- The RFC adds no mutation path and no `--no-dry-run` durable admission implementation.
- The doc says candidate evidence is not durable admission and not stable routing.
- The doc includes a future test/eval plan before any behavior change.

Recommended validation:

```bash
.venv/bin/python -m pytest -q tests/test_durable_admission_workflow_docs.py tests/test_v1_release_docs.py
git diff --check
```

### 3. Expand Adversarial Lifecycle And Admission Evals

Goal:
Prove the system fails closed when evidence looks tempting but is still insufficient.

Tasks:

- Add focused tests or eval rows for:
  - successful temporary use plus negative evidence;
  - promotion approval plus stale source hash;
  - matching capability plus permission widening;
  - duplicate candidate contract;
  - missing checkpoint;
  - expired plan approval;
  - digest mismatch;
  - repaired history with unresolved blockers.
- Prefer existing eval expectation hooks for candidate ledger fields, input request status/counts/resolution decisions, and stable-readiness authorization/routing fields.
- Keep failure categories and suggested next actions clear.

Checks:

- No adversarial lifecycle case mutates durable skills.
- No stable routing or active governor steering appears.
- `operator-summary` surfaces the blocker clearly enough for a reviewer.

Recommended validation:

```bash
.venv/bin/python -m pytest -q tests/test_durable_admission_preview.py tests/test_durable_admission_acceptance.py tests/test_stable_readiness.py tests/test_operator_summary.py
.venv/bin/skill-agent eval --suite evals/agent_diagnostic_v0.jsonl --skills-dir skills --runs-dir /tmp/skill-agent-diagnostic-lifecycle-check
bash scripts/v1_smoke.sh
git diff --check
```

## P2 Decision Compression

### 4. Improve Decision Compression Inside `operator-summary`

Goal:
Reduce operator decision load without adding another report.

Tasks:

- Add prioritization inside the existing `operator-summary` output rather than creating a new command.
- Group next steps by operator decision instead of only by subsystem.
- Keep raw evidence references in JSON.
- Add tests for priority ordering:
  - unsafe/blocker before missing evidence;
  - missing evidence before promotion-ready;
  - checkpoint unavailable as blocker;
  - clean state reports no active action.

Checks:

- Every recommendation points to an existing command.
- The report remains advisory and read-only.
- No ledgers, run logs, durable skills, registries, routing, permissions, or governor behavior mutate.

Recommended validation:

```bash
.venv/bin/python -m pytest -q tests/test_operator_summary.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
```

## P3 Design Only

### 5. Active Governor Preflight Design

Goal:
Define what evidence would be required before the governor moves from advisory reporting toward any active behavior.

Tasks:

- Write design only; do not implement active steering.
- Define "advisory", "blocking", and "authorizing" separately.
- List the exact actions the governor would be allowed to influence in a future release.
- Define eval gates that must pass before any advisory-to-active transition.
- Define human override and revoke paths.
- Require route decisions to remain visible in run logs and explain output.

Checks:

- No code path starts consulting the governor for new authority.
- No routing, promotion, durable admission, permission, dependency, or marketplace behavior changes.
- The design names the smallest reversible future behavior and the eval failure categories that block rollout.

## Explicitly Not Next

Do not build these from this review:

- positive stable routing;
- durable generated-skill admission into `skills/`;
- active governor steering;
- marketplace or signature infrastructure;
- hosted service behavior;
- UI/API surface;
- dependency installation;
- broad LLM or embedding router replacement;
- automatic repair-and-promote workflows;
- any workflow that treats generated skill self-tests as sufficient evidence.

## Recommended Next Slice

Start with:

```text
Design-partner review pack centered on operator-summary
```

Why:

- It directly addresses the review's highest-confidence recommendation.
- It reduces operator confusion without adding authority.
- It reuses the launch demo, operator summary, run logs, candidate evidence, and no-mutation proof already in the repo.
- It should be small enough to plan, implement, validate, review, and push in one slice.

After that, choose between:

```text
Durable admission / candidate-to-stable RFC refresh
```

or:

```text
Adversarial lifecycle/admission eval expansion
```

The decision should depend on whether the next goal is clearer architecture or stronger failure-proof evidence.

## Implementation Progress

- [x] P2 decision compression inside `operator-summary`: added prioritized `OPERATOR_DECISIONS` while preserving advisory, read-only output.
- [x] P0 design-partner review pack: added `docs/operator-summary-review-pack.md` and README/design-partner/demo/product-manager pointers.
- [x] P1 candidate-to-stable/durable admission RFC refresh: added a design-only proof contract and roadmap/lifecycle/stable-routing references.
- [x] P3 active-governor preflight design: added a design-only boundary document and roadmap/governor references.
- [x] P1 adversarial lifecycle/admission proof expansion: locked the failure-case matrix in the RFC/docs tests and preserved executable coverage for stale source hash, digest mismatch, expired approval, permission widening, duplicate/negative evidence, missing checkpoint, and unresolved repair blockers.
