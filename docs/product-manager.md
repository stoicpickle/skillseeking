# Skill-Seeking Agent Product Manager Profile

This profile is a repo-local product and evaluation PM brief. It frames and routes work for Skill-Seeking Agent; it does not implement features. Implementation belongs in focused Skill-Seeking Agent work threads that can plan, patch, validate, review, commit, and push.

## Product Promise

Skill-Seeking Agent should make capability gaps inspectable. When the agent cannot safely or confidently complete a task with the current local skill library, it should explain the missing capability, produce a structured skill request or input request, preserve evidence, and give the operator a clear next decision.

The product is strongest when it can show:

- what capability was needed,
- which skill evidence was considered,
- what was missing or unsafe,
- what human decision is needed,
- which ledger or eval proves the claim,
- and what changed after review.

## Current Bet

Prefer lifecycle evidence, candidate ledgers, input-request ledgers, capability-gap evals, and checkpointed progress before adding more autonomy.

The current bet is not "make the agent more autonomous." The current bet is "make the agent's lack of capability, repair needs, admission readiness, and human decision points durable enough that autonomy can be earned later."

The current product risk is **operator decision overload**, not missing proof infrastructure. The next slices should compress existing proof surfaces into clearer operator decisions before adding authority, durable admission, stable routing, UI, marketplace, dependency installation, or active governor steering.

The agent can now state the next boundary with `skill-agent new-authority-readiness`: it is ready for new-authority design review and planning, but `ready_to_enable_new_authority=false` remains the product truth until a separate reviewed slice proves a narrow authority candidate.

## Target User And Use Case

Target user:

- A local operator building and curating agent skills.
- Someone who wants to know why an agent stopped, asked for a skill, requested approval, or refused a risky path.
- Someone willing to review evidence before durable skill admission, permission widening, or stable promotion.

Primary use case:

- Run a task through `skill-agent`.
- Inspect run logs, candidate evidence, input requests, and eval results.
- Decide whether to repair, reject, defer, approve promotion evidence, or request more evidence.
- Ship the smallest validated slice that improves evidence quality or decision clarity.

## Non-Goals

- Do not frame this repo as a production agent framework.
- Do not add active governor steering before lifecycle and input evidence are proven.
- Do not add auto-promotion from temporary skill output to durable `skills/`.
- Do not treat candidate status as stable admission.
- Do not widen permissions without explicit human review.
- Do not treat generated skill self-tests as sufficient promotion evidence.
- Do not route work into broad planner, router, marketplace, UI, or sandbox rewrites unless the current roadmap and eval evidence justify that slice.

## Public Preview Strategy Boundary

The repo's current source boundary is MIT-licensed open source for the local CLI dev-preview. That does not grant product scope for hosted service behavior, production safety, true sandboxing, marketplace support, autonomous promotion, durable generated-skill admission, or positive stable routing.

Public-preview learning should come from 3 to 5 contained reviewer sessions that report setup, demo, `operator-summary` decision clarity, evidence, candidate-decision, safety-boundary, new-authority readiness, and stable-routing deferral friction. The recommended front door is the [Operator Summary Review Pack](operator-summary-review-pack.md): run the launch demo, inspect `operator-summary`, then drill into run logs or candidate-specific proof only when needed. Capture each session in [Reviewer Feedback Log](reviewer-feedback-log.md). Use the design-only [Candidate-To-Stable And Durable Admission RFC](internal/plans/candidate-to-stable-and-durable-admission-rfc-2026-06-07.md) and [Active Governor Preflight Design](internal/plans/active-governor-preflight-design-2026-06-07.md) to explain future gates without promising new authority. Future commercial exploration should stay secondary to evidence, approval, audit, policy control, and private-registry proof surfaces. These strategy notes are not implementation approval for those future surfaces.

## Next-Slice Rules

For behavior changes, require:

```text
plan -> implement -> eval -> review -> push
```

A valid next slice should:

- Start from `AGENTS.md`, `docs/operating-roadmap.md`, `docs/build-map.md`, relevant plan docs, and current git status.
- Name the product question it answers.
- State the boundary it preserves.
- Reuse existing CLI, model, ledger, eval, and docs surfaces where possible.
- Prefer evidence compression over adding another isolated report when the operator decision can be clarified through an existing surface.
- Prefer tests and eval rows that prove behavior over prose-only claims.
- Keep changes narrow enough to review in one pass.
- Update contracts or dev logs when the user-facing behavior changes.

## Proof Required

Docs-only slices:

- `git diff --check`
- staged diff review before commit

Behavior slices:

- targeted tests for the changed path
- `.venv/bin/python -m pytest -q`
- `.venv/bin/python -m compileall -q app`
- `git diff --check`
- capability-gap smoke eval
- capability-gap v0 eval
- lifecycle eval when lifecycle evidence changes
- agent diagnostic eval when routing, safety, lifecycle, repair, or input-focus behavior changes
- CodeRabbit review before push when the change is nontrivial or the user asks for review

## Review Questions

Before approving a proposed slice, ask:

- What evidence surface improves?
- Does this preserve run logs as immutable evidence?
- Does this mutate only the intended ledger or artifact?
- Does this keep candidate promotion and durable admission human-governed?
- Does this make a future eval clearer?
- Does this reduce operator decision load instead of adding another proof surface to inspect?
- Does it avoid adding active governor steering?
- Does it avoid permission widening?
- Is there a smaller slice that proves the same product bet?
- Are docs and contracts updated only where the behavior changed?

## Handoff Prompt Template

```text
Start a Skill-Seeking Agent work thread for this slice:

Goal:
<one sentence product/eval outcome>

Repo:
<repo-root>

Grounding:
- Inspect git status and branch.
- Read AGENTS.md.
- Read docs/product-manager.md.
- Read docs/operating-roadmap.md and docs/build-map.md.
- Read any relevant plan or contract docs.

Scope:
<files or behavior to change>

Boundaries:
- Preserve unrelated user changes.
- Do not rewrite historical run logs.
- Do not auto-promote generated or temporary skills.
- Do not install/copy durable skills unless the slice explicitly designs that workflow.
- Do not widen permissions.
- Do not add active governor steering.
- Do not introduce broad planner/router rewrites.

Proof:
- Plan -> implement -> eval -> review -> push for behavior changes.
- Run the validation bundle appropriate to the slice.
- Report files changed, validation results, commit/push status, and residual risk.
```
