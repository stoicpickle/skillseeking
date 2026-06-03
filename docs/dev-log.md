# Dev Log

## 2026-05-29

Created the initial documentation scaffold for the Skill-Seeking Agent idea.

Files added:

- `README.md`
- `docs/product-brief.md`
- `docs/architecture.md`
- `docs/skill-lifecycle.md`
- `docs/mvp-plan.md`
- `docs/contracts/data-contracts.md`
- `docs/evaluation-plan.md`
- `docs/safety-model.md`
- `docs/roadmap.md`
- `docs/clarifying-questions.md`
- `docs/reference/references.md`
- `docs/adr/0001-markdown-only-mvp.md`

Core direction captured:

- The product is an agent that can identify missing capabilities as first-class structured skill requests.
- The central demo trace is `BLOCKED -> REQUESTED SKILL -> VALIDATED -> LOADED -> CONTINUED`.
- The MVP should start with research workflows and Markdown-only skills before introducing executable generated skills.
- Safety, validation, and library maintenance are part of the core product, not later polish.

Current external repository note:

- GitHub repo: https://github.com/stoicpickle/skillseeking.git

Potential next steps:

- Initialize or connect this local folder to the GitHub repository.
- Choose the public product name.
- Convert the MVP plan into issues or a project board.
- Scaffold the first static skill registry and sample research skills.

## 2026-05-29 v0 Build Guardrails

Captured the working answers for v0:

- Do not run Deep Research before building v0.
- Build the trace first with CLI/API only.
- Keep v0 Markdown-only and local-only.
- Seed a small skill library and intentionally omit `detect-contradictions`.
- Prove three cases: existing skill, missing skill, and malicious skill rejected.
- Treat skill metadata as untrusted data, not instruction.
- Deeper research should happen before executable, external, or shared skills.

Added:

- `docs/v0-build-guardrails.md`

## 2026-05-29 Build Map Language

Added a shared planning vocabulary:

- `Milestone` for product capability.
- `Slice` for a small demoable build unit.
- `Task` for implementation work.
- `Check` for verification.

Status values:

- `not_started`
- `working`
- `blocked`
- `complete`
- `deferred`
- `cut`

Added:

- `docs/build-map.md`

## 2026-05-29 M1 Static Skill Loader

Implemented M1 as a CLI-first static skill loader.

Added:

- Python package scaffold and `skill-agent` CLI.
- Local `skills/<name>/SKILL.md` convention.
- Five seed skills: `extract-claims`, `compare-claims`, `source-quality-check`, `write-structured-answer`, and `validate-skill-md`.
- Strict frontmatter parser using safe YAML loading.
- Pydantic models for compact skill records, route decisions, loaded skills, and run logs.
- M1 validator for low-risk Markdown-only skills.
- Suspicious text scanner for routing manipulation and prompt-injection style phrases.
- Deterministic registry, planner, router, loader, and run logger.
- JSON run logs under `runs/`.
- Pytest coverage for parser, validator, registry, router, loader, run logs, and CLI demo.

Verified:

```bash
.venv/bin/python -m pytest -q
.venv/bin/skill-agent run "Extract claims from this article and write a structured summary with source-quality notes."
```

Result:

- 22 tests passed.
- Demo selected `extract-claims`, `source-quality-check`, and `write-structured-answer`.
- M1 does not generate skills, execute scripts, install skill dependencies, import external skills, or promote skills.

## 2026-05-29 M2 Skill Request Mode

Implemented M2 as a blocked-state and structured request layer on top of M1.

Added:

- `SkillRequest` Pydantic contract.
- `skill_requester` module for deterministic request creation.
- Missing-skill CLI trace stages: `BLOCKED_MISSING_SKILL` and `REQUESTING_SKILL`.
- CLI blocked card showing missing capability, requested skill, risk, status, and request ID.
- Run-log persistence for `skill_requests`.
- Missing-skill eval fixture.
- Tests proving `detect contradictions` creates a `detect-contradictions` request without generating a skill folder.

Verified:

```bash
.venv/bin/python -m pytest -q
.venv/bin/skill-agent run "Extract claims from these two sources and identify contradictions." --no-temporary-skills
```

Result:

- 25 tests passed.
- Missing-skill demo emits a structured request and exits blocked.
- M2 does not draft, validate, create, or load temporary skills.

## 2026-05-29 M3 Markdown Skillsmith

Implemented M3 as a deterministic Markdown-only Skillsmith.

Added:

- `TemporarySkillResult` contract.
- `skillsmith` module for drafting temporary `SKILL.md` files under the local skills directory.
- Safe YAML frontmatter emission with no scripts, tools, network, secrets, dependencies, or code execution.
- Agent-loop integration that drafts, validates, reloads the registry, and loads the temporary skill for the current run.
- `--no-temporary-skills` CLI flag to preserve M2 blocked-only behavior.
- Tests for temporary skill generation, validation, loading, run logging, and M2 compatibility mode.

Verified:

```bash
.venv/bin/python -m pytest -q
.venv/bin/skill-agent run "Cluster arguments from these sources."
```

Result:

- 31 tests passed.
- Low-risk missing-skill tasks now draft, validate, and load a temporary Markdown skill by default.
- Medium-risk missing-skill tasks preserve their risk level and fail M1/M3 validation until an approval path exists.
- M3 does not generate scripts, install dependencies, use network access, access secrets, or promote skills.

## 2026-05-29 M4 Scripted Skills

Implemented M4 as an explicitly enabled local scripted-skill path.

Added:

- `ScriptSpec` and script execution log contracts.
- Script validation via local pytest tests before registry admission.
- `--scripted-skills` CLI flag.
- Restricted subprocess runner with JSON stdin/stdout, timeout, captured stdout/stderr, and reduced environment.
- Scripted `count-words` fixture skill for validation and CLI demo.
- Tests proving scripted skills are rejected by default, admitted only when enabled, and executed with logs.

Verified:

```bash
.venv/bin/python -m pytest -q
.venv/bin/skill-agent run "Count words in one two three." --scripted-skills --no-temporary-skills --skills-dir tests/fixtures/scripted-skills
```

Result:

- 40 tests passed.
- Scripted skills remain opt-in.
- M4 does not allow network, secrets, file writes, external dependencies, or untested script execution.

## 2026-05-29 M5 Skill Maintenance

Implemented M5 as a local library-health reporting pass.

Added:

- `LibraryHealthReport`, `SkillUsageMetrics`, and `SkillHealthIssue` contracts.
- `librarian` module that reads the local registry and JSON run logs.
- Usage counts for loaded skills, temporary uses, skill requests, and script failures.
- Issue detection for rejected skills, duplicate input/output contracts, failed temporary validation, failed script execution, failed-run usage, and unused skills.
- `skill-agent health` text report.
- `skill-agent health --json` structured report.
- Tests using temporary skills and run logs.

Verified:

```bash
.venv/bin/python -m pytest -q
.venv/bin/skill-agent health
.venv/bin/skill-agent health --json
```

Result:

- 45 tests passed.
- M5 is read-only: it does not repair, retire, mutate, or promote skills.

## 2026-05-29 M6 Malicious Skill Rejection

Implemented M6 as a quarantine-proof milestone using the existing registry and health surfaces.

Added:

- Dedicated malicious skill fixtures with one safe control skill.
- Metadata routing attack fixture.
- Body prompt-injection fixture.
- Obfuscated base64-like instruction fixture.
- Unsafe secrets-permission fixture.
- Tests proving unsafe skills are rejected before routing or loading.
- CLI tests proving rejection is visible through `skill-agent registry`, `skill-agent health`, and `skill-agent health --json`.

Verified:

```bash
.venv/bin/python -m pytest -q
.venv/bin/skill-agent registry --skills-dir tests/fixtures/malicious-skills
.venv/bin/skill-agent health --skills-dir tests/fixtures/malicious-skills --runs-dir /tmp/skillseeking-empty-runs
.venv/bin/skill-agent health --skills-dir tests/fixtures/malicious-skills --runs-dir /tmp/skillseeking-empty-runs --json
coderabbit review --agent -t uncommitted
```

Result:

- 48 tests passed.
- CodeRabbit review found 0 issues.
- M6 adds no new CLI command, execution path, network access, or generated code.

## 2026-05-29 M7 v0 Trace Demo

Implemented M7 as CLI polish for the canonical successful temporary-skill trace.

Canonical command:

```bash
.venv/bin/skill-agent run "Cluster arguments from these sources."
```

Added:

- `TRACE`, `DECISIONS`, and `RESULT` sections for `skill-agent run`.
- A final result summary with exit code, loaded skills, temporary skills, and run-log path.
- Tests proving the canonical demo emits the required v0 landmarks and loads `argument-clustering`.
- Regression coverage that the contradiction path still exits blocked when temporary skill validation fails.

Verified:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
.venv/bin/skill-agent run "Cluster arguments from these sources."
```

Result:

- The canonical demo shows `PLANNING -> CHECKING_SKILLS -> BLOCKED_MISSING_SKILL -> REQUESTING_SKILL -> VALIDATION_PASSED -> LOADING_TEMP_SKILL -> ROUTE_COMPLETE -> RESULT`.
- M7 adds no new CLI command, dependency, routing behavior, or generated executable skill path.

## 2026-05-29 M8 Core Demo Suite

Implemented M8 as the public-facing v0 demo baseline.

Added:

- `docs/demo-suite.md` with four canonical demos:
  - existing skill
  - temporary skill success
  - blocked/no-temporary-skill
  - malicious skill rejected
- README entrypoint for running the four demos with an isolated skills copy.
- Lightweight demo-suite tests that assert exit status and durable output landmarks without full-output snapshots.

Verified:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
```

Result:

- The repo now has a stable, documented demo spine before adding the future repair flow.
- M8 adds no new CLI command, dependency, routing behavior, or agent capability.

## 2026-05-29 M9 Skill Repair Request

Implemented M9 as a structured repair-request layer for failed temporary validation.

Added:

- `SkillRepairRequest` contract.
- `skill_repairer` module for deterministic repair request creation.
- Agent-loop integration for temporary skill validation failures.
- `REQUESTING_REPAIR` trace stage.
- `REPAIR_REQUESTED` CLI card with failed skill, failed capability, status, objective, and validation reasons.
- Run-log persistence under `skill_repair_requests`.
- Tests proving failed `detect-contradictions` validation stays blocked and now emits a repair request.

Verified:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
```

Result:

- Failed temporary validation now produces a useful next-step artifact instead of only a failed route.
- M9 does not auto-repair, rewrite, validate, load, execute, or promote any repaired skill.

## 2026-05-29 M10 v0 Acceptance Harness

Implemented M10 as the comprehensive v0 confidence gate.

Added:

- `tests/test_v0_acceptance.py` with shared helpers for ordered CLI landmarks, run-log loading, and no-Markdown-body checks.
- Acceptance coverage for existing-skill, temporary-skill, blocked, repair-request, malicious-rejection, and scripted opt-in paths.
- Run-log assertions for loaded skills, skill requests, repair requests, and script executions.
- Filesystem assertions for temporary skill creation and validation-failure cleanup.
- Optional subprocess smoke for `.venv/bin/skill-agent` when the local entrypoint is available.

Verified:

```bash
.venv/bin/python -m pytest -q tests/test_v0_acceptance.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
coderabbit review --agent -t uncommitted
```

Result:

- The v0 demo, safety, repair, run-log, and entrypoint paths now have one acceptance-level regression harness.
- M10 adds no new CLI command, dependency, schema, or runtime behavior.

## 2026-05-29 Chunk 4 Hardening

Implemented final agent-improvement hardening:

- Router decisions now include ranked candidates with scoring reasons.
- `run --json` and `registry --json` emit machine-readable contracts.
- Scripted skills cap stdout/stderr, parse JSON stdout, validate output schema, and categorize failures.
- Library health reports v2 result categories, temporary outcomes, repair counts, safety stops, approval waits, route/load failures, and script failure categories while tolerating legacy logs.
- Documentation now separates safety risk from task complexity: contradiction detection is low safety risk; the repair demo uses an explicitly medium-risk local-code request.

Verified:

```bash
.venv/bin/python -m pytest -q
```

## 2026-05-29 M11 Skill Gauntlet Demo

Implemented M11 as a single mixed-pressure showcase.

Added:

- `tests/fixtures/gauntlet-skills/` with safe `extract-claims`, `source-quality-check`, and `write-structured-answer` fixtures plus malicious `malicious-router` and `secrets-stealer` fixtures.
- `scripts/run_gauntlet_demo.py` to print `SKILL GAUNTLET`, task, registry status, trace, and result summary.
- `tests/test_gauntlet_demo.py` to prove the demo output and run log.
- Demo-suite and README entries for running the gauntlet.

Verified:

```bash
.venv/bin/python scripts/run_gauntlet_demo.py
.venv/bin/python -m pytest -q tests/test_gauntlet_demo.py
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
```

Result:

- One command now demonstrates safe skill loading, malicious skill rejection, temporary skill creation/loading, repair-request generation, and traceable run-log output.
- M11 adds no new `skill-agent` command, external dependency, or runtime capability.

## 2026-05-30 M11 Eval Runner and Trace Explain

Implemented the capability-gap eval harness from the improvement prompt set.

Added:

- `skill-agent eval` for JSONL suites, per-task run logs, JSON reports, and Markdown summaries.
- `evals/capgap_smoke.jsonl` and `evals/capgap_v0.jsonl` as small deterministic suites.
- Deterministic request-quality scoring across specificity, contracts, success criteria, failure modes, risk correctness, and reuse potential.
- `skill-agent explain` for human-readable summaries of run logs.
- Tests for eval loading/reporting/CLI behavior, request-quality scoring, and explain output.

Verified:

```bash
.venv/bin/python -m pytest -q tests/test_request_quality.py tests/test_eval_runner.py tests/test_cli_explain.py
.venv/bin/skill-agent eval --suite evals/capgap_smoke.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent explain "$(ls -t runs/evals/202*/run_*.json | head -1)"
```

Result:

- The repo can now prove that the agent knows when to use a skill, request a missing skill, reject unsafe tasks, wait for approval-sensitive tasks, and expose the route through an auditable trace.

## 2026-05-31 M13 Capability-Gap Calibration

Implemented the calibration loop on top of the eval harness.

Added:

- Renamed the end-to-end eval test to `tests/test_capgap_eval_end_to_end.py`.
- Expanded `evals/capgap_v0.jsonl` from 5 tasks to 20 tasks:
  - 5 existing-skill tasks
  - 5 missing-skill tasks
  - 3 workflow-guidance tasks
  - 3 adversarial-routing tasks
  - 2 unsafe-stop tasks
  - 2 approval-required tasks
- Machine-readable eval failure categories.
- Per-failure Markdown diagnostics with expected outcome, actual result, loaded skills, requested skills, failure categories, suggested next action, and `skill-agent explain` command.
- Aggregate metrics for task pass rate, approval-required detection, trace completeness, and failure-category counts.
- A narrow safety classifier calibration for the natural phrase "read local files".

Verified:

```bash
.venv/bin/python -m pytest -q tests/test_eval_runner.py tests/test_cli_explain.py tests/test_capgap_eval_end_to_end.py tests/test_safety_decisions.py
.venv/bin/skill-agent eval --suite evals/capgap_v0.jsonl --skills-dir skills --runs-dir runs/evals
```

Result:

- The 20-task calibration suite passes 20/20.
- The first calibration run exposed `approval_not_requested` for "read local files"; the classifier now treats that phrase as human-approval-required file access.
- M13 adds no new agent feature surface, CLI command, dependency, or execution capability.

## 2026-06-01 Homeostatic Governor Planning

Documented the next planned product addition as a control layer, not a new autonomous agent framework.

Added:

- `docs/homeostatic-governor.md`

Updated:

- `docs/product-brief.md`
- `docs/architecture.md`
- `docs/evaluation-plan.md`
- `docs/safety-model.md`
- `docs/mvp-plan.md`

Direction captured:

- The product wedge is: turn recurring operational friction into validated, human-governed agent skills.
- The next slice should add a homeostatic governor around capability decisions.
- The governor records control signals such as confidence, risk, reversibility, approval requirement, freshness concern, tool failure history, and cost or latency concern.
- Governor output should attach to every capability decision, including `USE_SKILL`, `REQUEST_SKILL`, `ASK_HUMAN`, and `ABORT_UNSAFE`.
- Eval tasks should be able to assert governor decision accuracy, approval-gate accuracy, risk level, and dominant control signal.
- Durable promotion remains human-governed; generated or temporary skills should not promote themselves into the durable library.

Implementation touchpoints identified:

- `app/models.py`
- `app/capability_checker.py`
- `app/skill_router.py`
- `app/agent_loop.py`
- `app/eval_runner.py`
- `app/explain.py`

Status:

- Documentation-only planning update.
- No runtime behavior, schema, CLI command, dependency, or eval expectation has changed yet.

## 2026-06-01 Homeostatic Governor Trace + Eval Slice

Implemented the first Homeostatic Governor slice as an observer layer over existing capability decisions.

Added:

- `app/governor.py`
- `tests/test_governor.py`

Updated:

- `app/models.py`
- `app/agent_loop.py`
- `app/cli_output.py`
- `app/explain.py`
- `app/eval_runner.py`
- `evals/capgap_smoke.jsonl`
- `evals/capgap_v0.jsonl`
- governor, eval, explain, safety, CLI JSON, and run-log tests

Behavior captured:

- New run logs use schema version 3.
- Each capability decision gets a deterministic `GovernorDecision`.
- Each governor record produces a `GOVERNOR_DECIDED` trace event.
- `run --json` includes `governor_decisions`.
- `skill-agent explain` includes a `GOVERNOR` section.
- Eval suites can assert governor decision, risk level, approval requirement, and dominant signal.
- Eval reports include governor decision accuracy and governor-specific mismatch categories.

Boundaries:

- The governor does not change routing, safety classification, skill loading, temporary skill behavior, result-category precedence, or promotion rules.
- Freshness, tool failure history, and cost/latency fields are placeholder signals in this slice, not active scoring inputs.
- High-risk `ABORT_UNSAFE` records `approval_required=false` because the path is blocked, not reviewable.

## 2026-06-01 Skill Request Control Summary

Extended missing-skill request artifacts with a copied governor-control snapshot.

Updated:

- `app/models.py`
- `app/skill_requester.py`
- `app/agent_loop.py`
- `app/eval_runner.py`
- `evals/capgap_smoke.jsonl`
- `evals/capgap_v0.jsonl`
- `docs/contracts/data-contracts.md`
- request, eval, CLI, and acceptance tests

Behavior captured:

- New `REQUEST_SKILL`-generated `SkillRequest` artifacts include `control_summary`.
- `control_summary` mirrors the matching governor decision, dominant signal, confidence, risk, reversibility, and approval state.
- Low-risk missing-skill requests use `approval_gate="none"`.
- Elevated-risk missing-skill requests use `approval_gate="sandbox"` while preserving existing behavior.
- `ASK_HUMAN`, `ABORT_UNSAFE`, and existing-skill paths still do not create skill requests.
- Temporary-skill and repair-request flows preserve the original request control summary.
- Eval suites can require `must_have_request_control_summary` and report `request_control_summary_missing`.

Boundaries:

- The summary is a copied snapshot, not a live reference to governor records.
- This slice does not add governor-influenced routing, promotion, quarantine, approval handling, or new CLI commands.

## 2026-06-02 Lifecycle Review Queues and Health Expansion

Implemented advisory review queues on top of the Skill Candidate Ledger.

Added:

- Derived candidate review queues: `promotion_ready`, `repair_needed`, `blocked_or_quarantined`, `duplicate_merge_needed`, and `repeated_requested_gap`.
- Queue counts and per-entry queue names in `skill-agent candidates` and `skill-agent candidates --json`.
- Queue counts in `skill-agent health` and health JSON.
- Eval support for `candidate_review_queue` expectations.
- Expanded lifecycle eval rows for repeated-gap, promotion-ready, and repair-needed queue proof.
- Focused tests for blocked/quarantined and duplicate queue classification with fixture-backed ledger evidence.

Boundaries:

- Queues are advisory read-time summaries.
- Queues do not mutate the ledger schema, route skills, promote candidates, install durable skills, widen permissions, or change governor decisions.

## 2026-06-02 Durable Candidate Admission Planning

Implemented the first durable admission workflow surface as a dry-run report.

Added:

- `skill-agent admission-plan <candidate-id>` with human and `--json` output.
- Output-only admission report models covering candidate evidence, source artifacts, durable registry checks, blockers, warnings, and next steps.
- Read-only evidence discovery from the Skill Candidate Ledger, immutable run logs, and explicit temporary `SKILL.md` paths.
- Source parsing/validation checks and durable registry collision/contract-overlap checks.
- Tests covering ready candidates, unpromoted previews, missing evidence, missing source files, validation failures, durable collisions, contract-overlap warnings, permission blockers, CLI output, and no-mutation invariants.

Boundaries:

- `admission-plan` is dry-run only.
- It does not copy files, install durable skills, mutate the ledger, mutate the registry, steer the governor, widen permissions, or promote candidates to stable.

## 2026-06-02 Testing/Iteration Readiness Checkpoint

Added a bounded readiness checkpoint for local testing and iteration of the current CLI prototype.

Added:

- Source-path hardening for admission plans when run logs store temporary `SKILL.md` paths relative to `runs_dir`.
- End-to-end CLI acceptance proof for temporary skill creation, candidate approval, and `admission-plan --json`.
- Durable `skills/` snapshot assertions proving the readiness path does not copy or install candidate artifacts.
- Lifecycle eval in the GitHub Actions validation bundle.
- README, operating roadmap, and build-map wording that separates local testing readiness from production readiness.

Boundaries:

- No durable copy/install workflow was added.
- `ready_for_durable_review` remains human review evidence only.
- Governor steering, stable promotion, permission widening, and true sandboxing remain out of scope.

## 2026-06-02 Agent Diagnostic Eval

Added the local iteration eval for deciding what to improve next.

Added:

- `evals/agent_diagnostic_v0.jsonl` covering existing-skill routing, missing-skill detection, request quality, safety aborts, approval waits, adversarial routing, lifecycle evidence, temporary success, and repair-required validation failure.
- Eval aggregate diagnostic dimensions grouped by non-generic task tags.
- Markdown and CLI output that surface weakest failing diagnostic dimensions.
- Pytest coverage that runs the diagnostic suite, verifies report contract fields, and proves a human-approved diagnostic candidate can produce a read-only `admission-plan` report.

Boundaries:

- This is an insight eval, not a new autonomous behavior.
- It does not copy/install durable skills, promote stable skills, or steer the governor.

## 2026-06-03 Remote Progress And Input Focus

Added the read-only input-needed layer for remote progress.

Added:

- `InputRequest` contracts on run logs and admission-plan reports.
- Runtime input requests for `ASK_HUMAN` safety waits and repair-required temporary skill paths.
- Candidate-derived input requests for promotion-ready, repair-needed, and duplicate-merge queues.
- `skill-agent input-requests` and `skill-agent input-requests --json` for a consolidated queue.
- `INPUT_NEEDED` output in run, explain, and admission-plan surfaces.
- `INPUT_FOCUS` health counts and JSON fields for open input requests by kind.
- Eval expectations for `must_have_input_request`, `input_request_kind`, and `input_request_status`.
- Diagnostic and lifecycle eval rows that assert safety approval, promotion approval, and repair-review requests.
- Remote progress docs and data-contract updates.

Boundaries:

- The queue is advisory and read-only.
- No durable skill install/copy workflow was added.
- No auto-promotion, stable promotion, permission widening, unsafe execution, or active governor steering was added.

## 2026-06-03 Input Queue Source Diagnostics

Added the next Remote Progress coverage slice.

Added:

- Source-aware input queue items with `run_log` and `candidate_ledger` provenance.
- `skill-agent input-requests --json` `input_request_items` output while preserving the flat `input_requests` list.
- Human queue output that prints source paths and source details for each open or blocked request.
- Queue warnings for unreadable candidate ledger evidence.
- Missing-evidence admission-plan assertions for blocked `missing_evidence` input requests.
- Design-only input request resolution workflow at `docs/plans/input-request-resolution-workflow-2026-06-03.md`.

Boundaries:

- Resolution remains design-only.
- No resolution ledger, durable copy/install, stable promotion, permission widening, unsafe execution, or governor steering was added.

## 2026-06-03 Dry-Run Input Resolution

Added dry-run resolution classification for input requests.

Added:

- `skill-agent resolve-input-request <input-request-id>` with required `--decision`, `--reviewer`, `--notes`, and dry-run-only execution.
- Decision classification into `approve`, `revise`, `repair`, `reject`, `defer`, `block`, `recover`, `merge`, and `keep_separate`.
- Dry-run report fields for proposed status, remaining blocked scope, evidence sources, next steps, and mutation flags.
- Tests covering all six input request kinds, every declared decision option, and candidate-ledger requests while proving evidence files are unchanged.
- Rejection tests for invalid decisions and `--no-dry-run`.
- Contract and workflow docs updated from design-only to dry-run implemented.
- `AGENTS.md` added as tracked repo guidance for future Codex work.

Boundaries:

- The resolver does not write run logs, candidate ledgers, resolution ledgers, durable skills, or governor state.
- The append-only resolution ledger remains future work.

## 2026-06-03 Append-Only Input Resolution Ledger

Added durable resolution evidence for input requests.

Added:

- `runs/input_request_resolutions.json` with append-only resolution records.
- `skill-agent resolve-input-request --no-dry-run` appends one resolution record while dry-run remains non-mutating.
- Resolution records snapshot the source request, evidence sources, decision, resulting status, reviewer, notes, blocked scope, next steps, and timestamp.
- `skill-agent input-requests` applies the latest resolution status so resolved requests leave the active queue and deferred requests remain open.
- Tests proving dry-run writes nothing, non-dry-run appends, repeated resolutions preserve history, and source run logs/candidate ledgers remain unchanged.

Boundaries:

- No historical run logs are rewritten.
- Candidate ledgers are not mutated by resolution.
- No durable skill install/copy, permission widening, stable promotion, unsafe execution, or governor steering was added.

## 2026-06-03 Durable Admission Write-Plan Contract

Extended the dry-run durable admission preview into a concrete future write-mode contract.

Added:

- Nested `write_plan` output on `skill-agent admit-candidate --dry-run`.
- Collision policy preview with `block_existing` by default and `allow_replace_with_approval` for explicitly reviewed replacement plans.
- Destination write plan fields for source path/hash, target durable path, and future source snapshot retention path.
- Permission approval evidence hook through `--permission-approval-id`.
- Tests proving dry runs do not rewrite run logs, candidate ledgers, input request resolution ledgers, durable skill files, or snapshot directories.

Boundaries:

- `--no-dry-run` is still rejected.
- No durable skill copy/install, source snapshot creation, stable promotion, permission widening, unsafe execution, or governor steering was added.

## 2026-06-03 No-Write Durable Admission Acceptance Harness

Added acceptance-level proof for the future durable copy/install write mode while keeping the workflow dry-run only.

Added:

- CLI-driven acceptance tests for candidate creation, promotion approval, admission review resolution, and `admit-candidate --dry-run --json`.
- Source hash and source-drift assertions proving future write mode can detect stale plans.
- Destination and future snapshot path assertions under `runs/admission_snapshots/<candidate_id>/<source_sha>/`.
- Collision approval and permission approval scenarios using append-only resolution evidence.
- No-write assertions for durable skills, run logs, candidate ledgers, resolution ledgers, and snapshot directories.

Boundaries:

- `--no-dry-run` remains rejected.
- No durable skill copy/install, source snapshot creation, stable promotion, permission widening, unsafe execution, or governor steering was added.

## 2026-06-03 Dry-Run Snapshot Retention And Destination Staging

Added the next dry-run evidence layer for future durable admission writes.

Added:

- `admit-candidate --dry-run --prepare-write-evidence` to retain a source snapshot and stage the destination copy under `runs/` only.
- `--expected-source-sha256` stale-plan protection before run-scoped evidence is created.
- Write-plan fields for source-hash verification, retained snapshot state, destination staging paths, and staging hash.
- Acceptance tests proving matching evidence is reusable, mismatched historical evidence is not overwritten, source-hash mismatches block preparation, and durable `skills/` remains untouched.

Boundaries:

- `--no-dry-run` remains rejected.
- No durable skill copy/install, stable promotion, permission widening, unsafe execution, ledger rewrite, registry mutation, or governor steering was added.

## 2026-06-03 Candidate Usefulness Packet

Added a read-only usefulness evidence packet for candidate skills.

Added:

- `skill-agent candidate-usefulness <candidate-id>` with human and `--json` output.
- Report fields for matching run-log evidence, temporary validation/load state, successful temporary run IDs, admission-plan readiness, and no-mutation flags.
- Deterministic outcomes: `usefulness_supported`, `needs_successful_temporary_use`, `repair_required`, `blocked`, and `evidence_missing`.
- Tests proving successful temporary skills, repair-required candidates, requested-only candidates, missing evidence, and unknown candidates are surfaced without mutating run logs, candidate ledgers, durable skills, snapshots, staging folders, registry state, or governor behavior.

Boundaries:

- The packet does not compute statistical lift or claim paired baseline comparison yet.
- No durable skill copy/install, stable promotion, permission widening, unsafe execution, ledger rewrite, registry mutation, or governor steering was added.

## 2026-06-03 Proof-Carrying Capability Roadmap And Paired Usefulness

Translated the external deep-research recommendations into a repo-local proof-carrying capability roadmap and shipped the first utility-proof slice.

Added:

- `docs/plans/proof-carrying-capability-roadmap-2026-06-03.md` with goals for paired utility proof, plan-digest approval, permission/dependency diffs, managed shadow activation, rollback, negative evidence, tamper-evident checkpoints, and a future non-steering evidence governor.
- Optional `--baseline-run-id` and `--treatment-run-id` flags on `skill-agent candidate-usefulness`.
- A read-only `comparison` object that records baseline/treatment result categories, exit codes, candidate-request matching, temporary-skill loading, comparison outcome, blockers, warnings, and summary.
- Tests proving a blocked no-temporary-skill baseline plus successful temporary-skill treatment reports `improved`, while a contaminated baseline is rejected.

Boundaries:

- A single paired comparison is evidence for that pinned pair, not statistical lift.
- The command remains read-only: no run logs, candidate ledgers, input request resolution ledgers, durable skills, snapshots, staging files, registry state, or governor behavior are mutated.
- No durable skill copy/install, stable promotion, permission widening, unsafe execution, or active governor steering was added.

## 2026-06-03 Exact Admission Plan Digest Approval

Added the next proof layer for future durable admission write mode.

Added:

- Stable `sha256` plan digest output on `admit-candidate --dry-run`.
- `--plan-approval-id` to pin a resolved `approve_review` record when needed.
- Approval-note verification for `plan_digest=<digest>` and non-expired `expires_at=<timestamp>`.
- Plan digest coverage over candidate ID, planned operation, source path/hash, target path, snapshot path, destination staging path, collision policy, permission policy, permission approval ID, permission widening, and write-evidence preparation options.
- Tests proving matching approval enables readiness, mismatched approval is rejected, expired approval is rejected, source drift invalidates the old digest, and `--prepare-write-evidence` does not create run-scoped snapshot/staging evidence until the exact plan digest is approved.

Boundaries:

- `--no-dry-run` remains rejected.
- Plan-digest approval is preview evidence only; it is not durable copy/install, stable promotion, permission widening, registry mutation, or governor steering.
- Durable `skills/` remains untouched.

## 2026-06-03 Permission And Dependency Diff Packet

Added a semantic permission/dependency evidence packet to durable admission preview.

Added:

- `permission_dependency_diff` in `admit-candidate --dry-run` write plans.
- Permission class diffs for `read_files`, `write_files`, `network`, `secrets`, and `execute_code`.
- Tool diffs for declared `allowed_tools`.
- Dependency declaration evidence for unsupported `dependencies`, `dependency_lock`, `dependency_realization`, `requirements`, and `packages` frontmatter keys.
- Blocking behavior for dependency declarations without an exact realization/lock contract.
- Tests proving normal Markdown candidates have no dependency declarations, permission widening is visible as an added class, and dependency declarations are blocked without mutating durable skills or evidence history.

Boundaries:

- No dependency resolver, package install, lockfile generation, durable skill copy/install, stable promotion, permission widening, registry mutation, or governor steering was added.
- The packet is dry-run evidence only.

## 2026-06-03 Exact Dependency Realization Evidence

Extended the dependency diff packet with an exact realization contract.

Added:

- Optional `dependency_realization` manifest entries with `name`, `version`, `sha256`, and `source`.
- Dependency diff fields for realized and unresolved dependency names.
- Distinct blockers for missing realization (`dependency_realization_missing`) versus exact realization with unsupported install semantics (`dependency_install_unsupported`).
- Tests proving exact realization clears the missing-realization blocker while still blocking any future install/copy readiness.

Boundaries:

- No dependency resolution, dependency installation, package download, durable skill copy/install, permission widening, registry mutation, stable promotion, or governor steering was added.

## 2026-06-03 Counterfactual Skill Receipt

Added a read-only proof bundle surface for one candidate.

Added:

- `skill-agent skill-receipt <candidate-id>` with human and `--json` output.
- `SkillReceiptReport` and `SkillReceiptProof` contracts.
- Proof categories for origin, utility, containment, compatibility, approval, and reversibility.
- Nested candidate usefulness and durable admission preview evidence so a reviewer can inspect the current proof bundle from one command.
- Tests proving a receipt can use paired baseline/treatment utility evidence while keeping missing promotion approval, plan approval, and rollback support visible as blocked, missing, or partial proof.

Boundaries:

- The receipt is read-only and does not rewrite run logs, mutate candidate ledgers, append resolution records, create snapshots, stage destination files, copy/install durable skills, mutate the registry, widen permissions, or steer the governor.
- Receipt `ready`, `incomplete`, or `blocked` is audit evidence only; it is not durable admission approval and does not enable write mode.

## 2026-06-03 Negative Evidence Report

Added a read-only report for unfavorable or limiting evidence that already exists in the repo ledgers.

Added:

- `skill-agent negative-evidence` with human and `--json` output.
- `NegativeEvidenceReport` and `NegativeEvidenceItem` contracts.
- Reporting for reject, defer, block, and repair input request resolution history from `runs/input_request_resolutions.json`.
- Reporting for blocked/quarantined, repair-required, and duplicate candidate evidence from `runs/skill_candidate_ledger.json`.
- Optional `--candidate-id` filtering.
- Tests proving deferred and rejected resolution history plus blocked candidate evidence remain queryable without rewriting either ledger.

Boundaries:

- No new negative-evidence ledger was introduced; the command reads existing append-only or summary evidence.
- The report does not append resolutions, rewrite run logs, mutate candidate ledgers, create snapshots, stage destination files, copy/install durable skills, mutate the registry, widen permissions, or steer the governor.

## 2026-06-03 Managed Shadow Activation Plan

Added a dry-run plan for the future managed-prefix activation path.

Added:

- `skill-agent shadow-activation-plan <candidate-id>` with human and `--json` output.
- `ShadowActivationPlanReport` contract.
- Content-addressed managed store path planning under a managed prefix.
- Profile generation planning with activation pointer, previous generation, planned generation, and rollback target.
- A stable shadow plan digest that binds candidate ID, source hash, durable plan digest, managed prefix, store path, generation path, previous generation, rollback target, activation policy, and canary scope.
- Tests proving the command can read an existing generation directory to compute the next generation and rollback target without creating store files, generation files, profile pointers, or durable skills.

Boundaries:

- The command is read-only: it does not create the managed prefix, write store objects, switch activation pointers, rewrite run logs, mutate candidate or resolution ledgers, copy/install durable skills, mutate the registry, widen permissions, or steer the governor.
- Shadow activation remains a future write-mode design; this slice only makes the exact plan inspectable.

## 2026-06-03 Shadow Rollback Plan

Added a read-only verifier for future managed-prefix rollback.

Added:

- `skill-agent shadow-rollback-plan <candidate-id>` with human and `--json` output.
- `ShadowRollbackPlanReport` contract.
- Activation pointer inspection for symlink or text-file pointer evidence.
- Current/planned/rollback generation reporting.
- Rollback target existence checks and a stable rollback plan digest.
- Blockers for missing rollback generation, missing rollback target, missing activation pointer, or activation pointer target mismatch.
- Tests proving verifiable and blocked rollback plans do not create managed-prefix store files, generation directories, durable skills, run logs, candidate ledger entries, resolution ledger entries, registry mutations, or governor steering.

Boundaries:

- The command is read-only: it does not create the managed prefix, write store objects, switch activation pointers, rewrite run logs, mutate candidate or resolution ledgers, copy/install durable skills, mutate the registry, widen permissions, or steer the governor.
- Real profile switching, interruption handling, and rollback execution remain future write-mode work.

## 2026-06-03 Managed-Prefix Activation Acceptance Harness

Added a controlled acceptance harness for future managed-prefix write mode.

Added:

- `skill-agent shadow-activation-acceptance <candidate-id>` with human and `--json` output.
- `ShadowActivationAcceptanceReport` contract.
- Default planned mode that reports run-scoped acceptance paths without writing evidence.
- `--prepare-acceptance-evidence`, which may create or reuse matching acceptance evidence under `runs/` only.
- Acceptance store and generation `SKILL.md` copies from the approved source artifact.
- Simulated activation pointer switching to the planned generation followed by rollback to the previous generation.
- Pointer-before reporting, interrupted activation recovery when the acceptance pointer already targets the planned generation, and conflict detection for unexpected pointer targets.
- Stable acceptance plan digest binding candidate, planned managed prefix, acceptance prefix, source hash, store path, generation path, pointer path, rollback target, and shadow plan digest.
- Blockers for acceptance prefixes outside `--runs-dir`, source hash drift, missing rollback generation, missing acceptance paths, conflicting existing acceptance files, and unexpected pointer preconditions.
- Tests proving activation and rollback are verified inside the acceptance prefix, interrupted pointer states recover to rollback, conflicts block without partial rewrites, and durable `skills/`, the real managed prefix, run logs, candidate ledgers, resolution ledgers, registry, permissions, and governor behavior stay untouched.

Boundaries:

- This is not real durable activation. It writes only controlled acceptance evidence under `runs/`.
- No arbitrary destination writes, durable skill copy/install, stable promotion, real profile switching, permission widening, registry mutation, ledger mutation, or governor steering was added.

## 2026-06-03 Shadow Write Gate Verifier

Added a read-only human gate verifier for future managed-prefix write mode.

Added:

- `skill-agent shadow-write-gate <candidate-id>` with human and `--json` output.
- `ShadowWriteGateReport` contract.
- Composition of durable admission, shadow activation, shadow rollback, and prepared acceptance evidence.
- Verification for unchanged source hash, acceptance store copy, acceptance generation copy, restored acceptance pointer, rollback marker, rollback evidence, and supplied exact `--acceptance-plan-digest`.
- Tests proving the gate becomes ready only after prepared acceptance evidence exists, blocks missing evidence, blocks digest mismatch, and does not mutate durable `skills/`, run logs, candidate ledgers, resolution ledgers, the real managed prefix, registry, permissions, or governor behavior.

Boundaries:

- The command does not prepare acceptance evidence and does not enable real durable activation.
- No arbitrary destination writes, durable skill copy/install, stable promotion, real profile switching, permission widening, registry mutation, ledger mutation, or governor steering was added.

## 2026-06-03 Evidence Checkpoint Hash Chain

Added local tamper-evident checkpoints over core run evidence.

Added:

- `skill-agent evidence-checkpoint` with human and `--json` output.
- `EvidenceCheckpointReport`, `EvidenceCheckpointRecord`, `EvidenceCheckpointFile`, and `EvidenceCheckpointLedger` contracts.
- Dry-run checkpoint creation that computes the next checkpoint hash without writing.
- `--no-dry-run` append support for `runs/evidence_checkpoints.json` only.
- `--verify` support for checkpoint-chain validation and current-evidence comparison against the latest checkpoint.
- Scope filtering that includes core `runs/` evidence while excluding eval reports, locks, temporary checkpoint writes, and the checkpoint ledger itself.
- Tests proving dry-run writes nothing, append writes only the checkpoint ledger, repeated checkpoints preserve the previous hash, current evidence tampering is detected, and checkpoint-ledger tampering is detected.

Boundaries:

- This is local tamper-evidence only; it does not sign evidence, prove trust, approve durable admission, or enable real durable activation.
- No run logs, candidate ledgers, resolution ledgers, durable skills, registry records, permissions, managed prefixes, or governor behavior were mutated by checkpoint verification.

## 2026-06-03 Non-Steering Evidence Governor

Added a read-only evidence governor report for candidate review.

Added:

- `skill-agent evidence-governor <candidate-id>` with human and `--json` output.
- `EvidenceGovernorReport` and `EvidenceGovernorSignal` contracts.
- Composition of `skill-receipt`, `negative-evidence`, and `evidence-checkpoint --verify` surfaces.
- Deterministic advisory recommendations limited to `ask`, `test_more`, `deny`, and `defer`.
- Explicit no-authority fields for approval, install, promotion, permission widening, route steering, and governor steering.
- Tests proving the recommendation ladder for missing proof, missing approval, negative reject evidence, and strongest-current-proof deferral while preserving no-mutation flags.

Boundaries:

- The command is advisory only. It does not grant approval, authorize install/copy, promote candidates, widen permissions, route work, or steer execution.
- No run logs, candidate ledgers, resolution ledgers, checkpoint ledgers, durable skills, registry records, permissions, managed prefixes, or active governor behavior were mutated.
