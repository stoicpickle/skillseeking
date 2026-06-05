# Operator Decision Load and Stable Review Rehearsal

## Source

This note distills the external review in `/Users/russ/Downloads/review 06032026.md` into repo-local tasking. The review assessment was docs-and-selected-evidence based, not a fresh line-by-line code audit, so implementation threads should still inspect current code, tests, ledgers, and CLI behavior before changing anything.

Context7 check: current Typer documentation still recommends typed command functions with `Annotated`, `typer.Argument`, and `typer.Option` help text for clear CLI surfaces. Any Slice 1 CLI additions should follow the existing repo pattern: typed arguments/options, explicit `--json` output, and help text that names the no-authority boundary.

## Review Thesis

The product risk has shifted.

The repo no longer mainly needs proof that the agent can notice missing capabilities. The current surface already includes capability-gap detection, temporary Markdown skill creation, candidate ledgers, usefulness packets, admission previews, input-resolution evidence, negative evidence, tamper-evident checkpoints, non-steering governance, shadow activation, human-approved managed-prefix writes, no-write dependency evidence, and advisory stable-readiness.

The next risk is **operator decision overload**: too many individually useful proof reports can make the operator ask which report actually says what to do. The next work should collapse existing evidence into clearer decisions without granting new authority.

## Operating Mindset

- Prefer evidence compression over new authority.
- Make the next human decision obvious before adding new proof surfaces.
- Treat `stable-readiness` as the candidate-to-stable aggregation hub.
- Keep all candidate-to-stable work advisory until a separate human-approved stable workflow exists.
- Keep dependency evidence distinct from dependency installation.
- Keep local checkpointing described as local tamper-evidence, not external provenance or trust.
- Avoid UI, marketplace, sandboxing, active governor steering, durable `skills/` admission, and stable routing until the evidence-to-decision path is clearer.

## Tasking List

### 1. Candidate-to-stable review rehearsal, no mutation

Use `skill-agent stable-readiness` as the core aggregation surface. Extend it only as needed to answer:

```text
What exact evidence is still missing before a human could approve stable review?
```

Required proof cases:

- candidate has the stable-use threshold but negative evidence blocks review;
- candidate has the stable-use threshold but receipt approval/proof is missing or incomplete;
- same-name durable registry conflict blocks review;
- stable-review-ready still reports stable promotion unauthorized;
- stable-review-ready still reports stable routing disabled;
- one lifecycle/eval row proves “ready for stable review” is still not stable-routed.

Boundary:

- no stable promotion;
- no stable routing;
- no durable copy/install into `skills/`;
- no ledger, registry, permission, or governor mutation.

### 2. Stable-readiness eval dimension

Teach the eval layer to assert stable-review states the same way it already asserts lifecycle and input-focus behavior.

Expected additions:

- `stable_readiness_outcome` expectation;
- `stable_review_authorized=false` expectation;
- `stable_routing_enabled=false` expectation;
- one ready-for-review row;
- duplicate-blocked and negative-evidence-blocked rows;
- diagnostic dimension output for stable-readiness failures.

### 3. Dependency-evidence acceptance matrix

Promote the no-write dependency contract into a named black-box acceptance matrix so digest-bound behavior does not regress.

Expected cases:

- unresolved dependency keeps `dependency_realization_missing`;
- exact realization keeps `dependency_install_unsupported`;
- dependency digest changes when declaration changes;
- dependency digest changes when realization changes;
- prepared manifest is reused when bytes match;
- conflicting manifest blocks without overwrite;
- dependency approval verifies;
- dependency approval does not remove install blockers.

Boundary: still no resolver, package download, dependency installation, permission widening, or durable admission authority.

### 4. Candidate decision summary report

After Slice 1 and the eval dimension are stable, consider a compact CLI index over existing reports, for example:

```bash
skill-agent candidate-decision <candidate-id>
```

The report should summarize existing evidence into one advisory answer:

```text
decision: test_more | ask_human | deny | defer
why:
  - utility: present
  - approval: missing
  - dependency install: unsupported
  - stable readiness: needs_more_evidence
next command:
  skill-agent stable-readiness <candidate-id>
```

Rules:

- no new persistence;
- cite the source report for every claim;
- preserve advisory-only semantics;
- cover ready-ish, blocked, dependency-blocked, and negative-evidence candidates.

### 5. Proof-surface drift guardrails

Create shared tests or helpers that make advisory-report no-authority contracts hard to erode.

Candidate surfaces:

- `candidate-usefulness`;
- `skill-receipt`;
- `stable-readiness`;
- `negative-evidence`;
- `evidence-governor`;
- no-write dependency evidence.

Common invariants:

- durable skills are not mutated;
- registry is not mutated;
- candidate ledger is not mutated;
- resolution ledger is not mutated;
- stable promotion remains unauthorized;
- stable routing remains disabled;
- governor steering remains disabled.

Avoid brittle phrase tests except where wording protects user-facing boundaries.

## Slice 1 Goal

```text
Goal:
Make `skill-agent stable-readiness <candidate-id>` a candidate-to-stable review rehearsal that clearly states whether existing evidence is ready, missing, or blocked for human stable review, while still refusing to promote, route, copy, install, mutate ledgers, widen permissions, or steer the governor.
```

### Product Question

```text
Can the CLI prove, from existing evidence, that a candidate is ready for human stable review while still refusing to promote or route it?
```

### Scope

- Inspect `app/stable_readiness.py`, `app/models.py`, `app/cli.py`, `app/cli_output.py`, `app/eval_runner.py`, and existing lifecycle/stable-readiness tests.
- Reuse `StableReadinessReport`, `SkillReceiptReport`, `NegativeEvidenceReport`, durable registry evidence, and existing eval surfaces where possible.
- Improve `stable-readiness` output only where it reduces operator decision load.
- Add stable-readiness eval assertions and one lifecycle/eval row if the current eval runner lacks them.

### Boundaries

- Preserve unrelated user changes.
- Do not rewrite historical run logs.
- Do not auto-promote generated, temporary, or candidate skills.
- Do not copy/install durable skills into `skills/`.
- Do not mutate candidate ledgers, resolution ledgers, registries, or durable skills.
- Do not widen permissions.
- Do not enable stable routing.
- Do not add active governor steering.
- Do not introduce broad planner/router rewrites.

### Proof

Targeted tests should cover at least:

- stable-use threshold plus negative evidence blocks review;
- stable-use threshold plus missing/incomplete receipt proof remains not-authorized;
- durable same-name registry conflict blocks review;
- ready-for-review preserves `stable_promotion_authorized=false`;
- ready-for-review preserves `stable_routing_enabled=false`;
- eval row for ready-for-stable-review but not stable-routed.

Validation bundle:

```bash
.venv/bin/python -m pytest -q tests/test_stable_readiness.py
.venv/bin/python -m pytest -q tests/test_eval_runner.py tests/test_capgap_eval_end_to_end.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
.venv/bin/skill-agent eval --suite evals/skill_lifecycle_v0.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/agent_diagnostic_v0.jsonl --skills-dir skills --runs-dir runs/evals
```

Run the smoke/v0 evals too if the implementation touches shared eval reporting or run-loop behavior.

## Explicitly Not Yet

- Real durable copy/install into `skills/`.
- Stable routing.
- Active governor steering.
- General dependency resolution or package installation.
- Marketplace/imported skills.
- Web UI.
- True sandboxing claims without actual isolation.
- Auto-promotion from temporary to candidate or candidate to stable.
- Broad planner/router rewrites.
- More report commands that do not reduce operator decision load.
