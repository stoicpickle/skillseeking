# Skill-Seeking Agent External Review Export

Generated: 2026-06-03

Repo-local framing source: `docs/product-manager.md`

## Purpose

This export summarizes the current state of Skill-Seeking Agent for external product and architecture review. It is meant to be pasted into ChatGPT Pro or another reviewer so the reviewer can reason from the actual repo state instead of giving generic agent advice.

## Product Promise

Skill-Seeking Agent should make capability gaps inspectable. When the agent cannot safely or confidently complete a task with the current local skill library, it should explain the missing capability, produce a structured skill request or input request, preserve evidence, and give the operator a clear next decision.

The strongest product shape is evidence-first:

- show what capability was needed,
- show which skill evidence was considered,
- show what was missing or unsafe,
- show what human decision is needed,
- point to the run log, ledger, or eval that proves the claim,
- and make the next slice small enough to validate and review.

## Current State

Skill-Seeking Agent is a CLI-first prototype, not a production agent framework. The public roadmap frames it as:

1. Static Skill Loader
2. Skill Request Mode
3. Markdown-Only Skillsmith
4. Scripted Skills with explicit trusted-local opt-in guardrails
5. SkillOps

The current product proof includes:

- static skill loading and routing from local `skills/` metadata,
- structured missing-skill requests when a capability is absent,
- Markdown-only temporary skill drafting, validation, and one-run loading,
- explicitly enabled trusted-local scripted skills with JSON I/O validation and execution logs,
- malicious or suspicious skill rejection before routing or loading,
- run logs and explain output for traceability,
- capability-gap eval suites and diagnostic dimensions,
- Skill Candidate Ledger evidence for repeated gaps and candidate lifecycle signals,
- candidate review queues and candidate surfaces,
- durable admission dry-run reports,
- remote progress/input-focus queues,
- dry-run input request decision classification,
- append-only input request resolution evidence.

## Current Capabilities And Commands

Core operator surfaces:

```bash
.venv/bin/skill-agent run "<task>" --skills-dir skills --runs-dir runs
.venv/bin/skill-agent registry --skills-dir skills --json
.venv/bin/skill-agent health --skills-dir skills --runs-dir runs
.venv/bin/skill-agent health --skills-dir skills --runs-dir runs --json
.venv/bin/skill-agent candidates --runs-dir runs
.venv/bin/skill-agent candidates --runs-dir runs --json
.venv/bin/skill-agent explain runs/run_<timestamp>_<run_id>.json
.venv/bin/skill-agent explain runs/run_<timestamp>_<run_id>.json --include-candidates
```

Input focus and resolution surfaces:

```bash
.venv/bin/skill-agent input-requests --runs-dir runs
.venv/bin/skill-agent input-requests --runs-dir runs --json
.venv/bin/skill-agent resolve-input-request <input-request-id> --runs-dir runs --decision defer --reviewer "Ada" --notes "Reviewed evidence." --dry-run
.venv/bin/skill-agent resolve-input-request <input-request-id> --runs-dir runs --decision approve_workflow --reviewer "Ada" --notes "Reviewed evidence." --no-dry-run
```

Admission and eval surfaces:

```bash
.venv/bin/skill-agent admission-plan <candidate-id> --runs-dir runs --skills-dir skills
.venv/bin/skill-agent eval --suite evals/capgap_smoke.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/capgap_v0.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/skill_lifecycle_v0.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/agent_diagnostic_v0.jsonl --skills-dir skills --runs-dir runs/evals
```

## Recently Shipped Slices

Recent commits:

- `0e77ea0 docs: add product manager profile`
- `e455831 feat: add input request resolution ledger`
- `b942003 feat: add dry-run input request resolution`
- `82c1b16 feat: add input queue source diagnostics`
- `bd0ef18 feat: add remote progress input focus`

Recent product slices:

- Remote Progress and Input Focus: `InputRequest`, `skill-agent input-requests`, `INPUT_NEEDED`, health `INPUT_FOCUS`, admission-plan summaries, and eval expectations expose human decision boundaries.
- Input Queue Source Diagnostics: input request JSON includes `input_request_items` with `run_log`, `candidate_ledger`, and now resolution-ledger provenance.
- Dry-Run Input Resolution: `resolve-input-request` classifies every declared human decision option while proving run logs and candidate ledgers remain unchanged.
- Append-Only Input Resolution Ledger: `resolve-input-request --no-dry-run` appends `runs/input_request_resolutions.json` records and `input-requests` applies the latest status without mutating source evidence.
- Product Manager Profile: `docs/product-manager.md` frames product/eval direction and routes implementation into focused work threads.

## Proof And Eval Status

Latest readiness proof recorded in `docs/operating-roadmap.md`:

- Full tests: `.venv/bin/python -m pytest -q` -> `157 passed in 14.51s`.
- Compile: `.venv/bin/python -m compileall -q app` -> passed.
- Diff check: `git diff --check` -> passed.
- Smoke eval: `evals/capgap_smoke.jsonl` -> `4/4`, report `runs/evals/eval_report_20260603_040824_455105.json`.
- Capability-gap v0 eval: `evals/capgap_v0.jsonl` -> `20/20`, report `runs/evals/eval_report_20260603_040824_968794.json`.
- Lifecycle eval: `evals/skill_lifecycle_v0.jsonl` -> `4/4`, report `runs/evals/eval_report_20260603_040824_542795.json`.
- Agent diagnostic eval: `evals/agent_diagnostic_v0.jsonl` -> `13/13`, report `runs/evals/eval_report_20260603_040824_802697.json`.
- CodeRabbit review for the append-only resolution-ledger diff: `0 findings`.

## Evidence Surfaces

Current evidence surfaces include:

- run logs under `runs/`,
- `runs/skill_candidate_ledger.json` for rebuildable candidate lifecycle summary evidence,
- `runs/input_request_resolutions.json` for append-only human input resolution evidence,
- `skill-agent candidates` and `skill-agent candidates --json`,
- `skill-agent input-requests` and `skill-agent input-requests --json`,
- `skill-agent explain` and `skill-agent explain --include-candidates`,
- eval reports under `runs/evals/`,
- docs contracts in `docs/contracts/data-contracts.md`,
- roadmap and build-map proof in `docs/operating-roadmap.md` and `docs/build-map.md`.

## Known Boundaries And Non-Goals

These are intentional boundaries, not accidental missing features:

- no active governor steering,
- no auto-promotion from generated or temporary skills to durable `skills/`,
- no durable skill install/copy workflow yet,
- no treating `candidate` status as stable admission,
- no permission widening without human review,
- no treating generated skill self-tests as sufficient promotion evidence,
- no broad planner/router rewrite,
- no marketplace/signatures/external distribution work yet,
- no UI/API surface yet,
- no true sandboxing beyond current trusted-local scripted-skill guardrails.

The product bias is lifecycle evidence, candidate/input-request ledgers, capability-gap evals, and checkpointed progress before adding more autonomy.

## Open Risks And Gaps

- The governor is still trace-only; this is safer now, but future active controls need stronger eval gates.
- Durable skill install/copy and candidate-to-stable workflow remain unimplemented and need careful permission/admission design.
- Resolution-ledger behavior has focused tests but could use explicit eval expectation rows in the diagnostic/lifecycle suites.
- Scripted skills are trusted-local opt-in, not true sandboxing.
- The CLI is proven locally, but the project is not production-ready.
- External review may find that the product surface needs a sharper demo path, especially for non-repo users.
- Product sequencing still needs discipline: the temptation is to add autonomy before proving enough evidence surfaces.

## Suggested Next-Slice Candidates

Possible next slices for review:

1. Add resolution-ledger eval expectation rows so the eval harness proves resolved vs deferred input requests.
2. Design durable copy/install workflow without implementing mutation yet.
3. Expand duplicate and blocked/quarantined candidate eval fixture coverage.
4. Create a canonical demo script that walks through missing capability -> skill request -> candidate evidence -> input request -> resolution ledger.
5. Add a lightweight product demo README section showing what an operator sees at each evidence surface.

## Ready-To-Paste ChatGPT Pro Prompt

```text
You are reviewing a local research/prototype repo called Skill-Seeking Agent. Please reason from the exported state below, not from generic agent-building advice.

I want a product and architecture review. Focus on recommendations and next-slice prioritization, not code implementation. Treat the current product bet as evidence-first: lifecycle evidence, candidate ledgers, input-request ledgers, capability-gap evals, and checkpointed progress should come before adding more autonomy.

Current product promise:
Skill-Seeking Agent should make capability gaps inspectable. When the agent cannot safely or confidently complete a task with the current local skill library, it should explain the missing capability, produce a structured skill request or input request, preserve evidence, and give the operator a clear next decision.

Current state:
- CLI-first prototype, not a production agent framework.
- Static skill loading and routing from local skills metadata.
- Structured missing-skill requests.
- Markdown-only temporary skill drafting, validation, and one-run loading.
- Explicitly enabled trusted-local scripted skills with validation and execution logs.
- Malicious/suspicious skill rejection.
- Run logs, explain output, candidate ledger, input request queue, and append-only input request resolution ledger.
- Candidate review surfaces and durable admission dry-run reports.
- Capability-gap eval suites and diagnostic dimensions.

Recent shipped slices:
- Remote Progress and Input Focus: exposes human decision boundaries through InputRequest, input-requests CLI, health counts, explain/admission summaries, and eval assertions.
- Input Queue Source Diagnostics: input request JSON includes run-log/candidate-ledger/resolution-ledger provenance.
- Dry-Run Input Resolution: classifies every declared human decision option without mutating evidence.
- Append-Only Input Resolution Ledger: resolve-input-request --no-dry-run appends runs/input_request_resolutions.json and input-requests applies latest status.
- Product Manager Profile: frames product/eval direction and keeps implementation in focused work threads.

Latest proof:
- Full tests: 157 passed.
- Compile app: passed.
- git diff --check: passed.
- capgap smoke eval: 4/4.
- capgap v0 eval: 20/20.
- lifecycle eval: 4/4.
- agent diagnostic eval: 13/13.
- CodeRabbit review for the append-only resolution-ledger diff: 0 findings.

Known boundaries:
- No active governor steering.
- No auto-promotion from generated or temporary skills to durable skills.
- No durable skill install/copy workflow yet.
- Candidate status is evidence only, not stable admission.
- No permission widening without human review.
- Generated skill self-tests are not sufficient promotion evidence.
- No broad planner/router rewrite.
- No marketplace/signatures/external distribution work yet.
- No UI/API surface yet.
- Scripted skills are trusted-local opt-in, not true sandboxing.

Open risks/gaps:
- Governor remains trace-only; future active controls need stronger eval gates.
- Durable skill install/copy and candidate-to-stable workflow remain unimplemented.
- Resolution-ledger behavior has focused tests but needs explicit eval expectation rows.
- Product demo path may still be too repo-internal for external users.
- There is a temptation to add autonomy before enough evidence surfaces are proven.

Candidate next slices:
1. Add resolution-ledger eval expectation rows so evals prove resolved vs deferred input requests.
2. Design durable copy/install workflow without implementing mutation yet.
3. Expand duplicate and blocked/quarantined candidate eval fixture coverage.
4. Create a canonical demo script for missing capability -> skill request -> candidate evidence -> input request -> resolution ledger.
5. Add a product demo README section showing what an operator sees at each evidence surface.

Please review:
1. What is the strongest product wedge here?
2. What are the highest-risk architecture or product assumptions?
3. Which next slice should be prioritized, and why?
4. What should explicitly not be built next?
5. What proof/eval should gate the next behavior change?
6. What would make this compelling to an external technical reviewer without overclaiming production readiness?
7. Are the current ledgers and evals enough to justify more autonomy, or should the project deepen evidence surfaces first?

Return a ranked recommendation list with rationale, suggested acceptance criteria, and any questions you would ask before approving the next slice.
```
