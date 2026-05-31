# Agent Improvement Implementation: Plan

## Goal
Turn the ChatGPT Pro architecture/code-evaluation recommendations into an executable implementation plan for the Skill-Seeking Agent v0. This is a hardening plan, not a rewrite: make the current agent loop more honest, temporary, inspectable, and policy-driven before adding broader capability.

## Implementation Progress
- [x] Chunk 1 — Schema/run identity/structured trace foundation: implemented Work Items 1–3; full `.venv/bin/python -m pytest` reported passing in the sub-agent. Result-category precedence exists but will be finalized with safety/result work.
- [x] Chunk 2 — Run-scoped temporary skill storage: implemented per-run temp artifacts, explicit registry overlay, `source_root` containment, and updated tests; full suite reported passing.
- [x] Chunk 3 — Safety decisions, capability catalog, and result-category normalization: implemented catalog, preflight safety decisions, safety CLI cards, and result-category precedence; full suite reported passing. Final chunk should re-check the risk-vs-complexity semantics called out in P0.
- [x] Chunk 4 — Router explanations, JSON CLI, scripted-skill hardening, health/docs/final validation: implemented Work Items 8–13, aligned risk-vs-complexity semantics, and validated with full pytest plus compileall.

## Background

### Locked decisions
- Temporary skill state should use a **separate lifecycle/provenance field**, rather than overloading `metadata.status` or `validation.status`.
- Add a unique per-execution `run_id` while keeping deterministic `task_id` as repeatable task grouping.
- Add explicit safety states (`ASK_HUMAN`, `ABORT_UNSAFE`) and clearer CLI/result categories.

### Source evaluation priorities
- P0: make temporary skills actually temporary; separate safety risk from task complexity; add explicit safety decisions; make route/load vs actual task execution honest; harden or clearly label scripted skills.
- P1: structured trace events; shared capability catalog; stronger router scoring/explanations; categorized validation policy; more inspectable Skillsmith outputs; run-log schema versioning and stable run IDs; richer library health; JSON CLI surfaces.
- P2: later skill-guided execution, real sandboxing, and web UI only after structured trace/JSON output exist.

### Current control flow
The current CLI run path is deterministic:

```text
app.cli.run()
-> app.agent_loop.run_task()
-> app.planner.plan_task()
-> SkillRegistry.load()
-> check_capabilities()
-> route_capability()
-> existing skill load OR missing skill request/temp generation
-> optional script execution
-> RunLog
-> write_run_log()
-> emit_run_output()
```

Key ownership today:
- `app/models.py` owns the Pydantic contracts.
- `app/planner.py` hard-codes task-term-to-capability rules.
- `app/skill_requester.py` hard-codes missing-skill request templates, duplicating capability knowledge.
- `app/skill_router.py` scores accepted skills and currently returns only `USE_SKILL` or `REQUEST_SKILL`.
- `app/agent_loop.py` owns orchestration, trace strings, exit-code decisions, temporary skill generation, and run-log creation.
- `app/skillsmith.py` writes generated Markdown skills directly into durable `skills_dir`.
- `app/run_log.py` creates unique filenames, but `RunLog` itself has no unique `run_id`.
- `app/librarian.py` reads raw JSON logs tolerantly and is the best migration seam for schema evolution.

### Temporary skill and lifecycle seams
- `app/agent_loop.py:18-23` owns run inputs (`skills_dir`, `runs_dir`, temporary-skill toggles) and is the seam for creating run-scoped storage.
- `app/skillsmith.py:16-39` writes generated skills directly under durable `skills_dir`; `_safe_skill_dir()` at `app/skillsmith.py:42-49` enforces containment under that root.
- `app/registry.py:16-35` loads one registry root with `skills_dir.glob("*/SKILL.md")`.
- `app/skill_validator.py:53-56` validates skill-file containment against the passed root; `app/skill_validator.py:85-86` admits only candidate/stable manifest statuses even though `SkillStatus` includes `temporary` at `app/models.py:9`.
- `app/loader.py:13-39` assumes a single containing `skills_dir` for loading.
- `app/models.py:195-203` (`TemporarySkillResult`) and `app/models.py:178-185` (`LoadedSkillLog`) capture temporary usage, but no explicit lifecycle/provenance model exists yet.
- Current tests encode durable-temp behavior: `tests/test_v0_acceptance.py:105-114`, `tests/test_skillsmith.py:24-33`, plus cleanup assertions around validation failure.

### Run log, trace, and health seams
- `app/models.py:206-224` defines `RunLog` with `task_id`, `created_at`, `exit_code`, plan/decision/log collections, `trace: list[str]`, and `result_quality`; it lacks `schema_version`, `run_id`, `execution_summary`, and structured trace events.
- `app/agent_loop.py:25-147` builds trace strings imperatively and constructs `RunLog` at `app/agent_loop.py:133-146`.
- `app/run_log.py:11-23` persists JSON using `run_log.model_dump(mode="json")`; unique timestamp/UUID identity currently exists only in the filename at `app/run_log.py:13-15`.
- `app/librarian.py:122-133` reads raw `run_*.json` dicts tolerantly, so schema evolution should preserve legacy-log support with defaults/normalization.
- Existing tests hand-write minimal legacy-ish logs in `tests/test_librarian.py:18-39`, `tests/test_librarian.py:82-101`, and `tests/test_librarian.py:115-124`.

### Safety decision and CLI/result seams
- `app/models.py:12` restricts `CapabilityDecisionType` to `USE_SKILL` and `REQUEST_SKILL`, while `docs/contracts/data-contracts.md:53-59` and `docs/architecture.md:68-80` already describe `CREATE_TEMP_SKILL`, `ASK_HUMAN`, and `ABORT_UNSAFE`.
- `app/capability_checker.py:8-11` is a thin seam between planning and routing; it currently maps every capability to `route_capability()`.
- `app/skill_router.py:11-47` emits only `USE_SKILL`/`REQUEST_SKILL`; unsafe permissions are scoring metadata around `app/skill_router.py:61-69`, not hard safety decisions.
- `app/agent_loop.py:39-129` collapses blocked missing skills, validation/repair needed, selected-record misses, and script failures into `exit_code = 1`.
- `app/cli_output.py:10-82` prints trace, decisions, blocked/repair/script cards, and final exit code, but no named result category.
- `RouteDecision.requires_human_approval` (`app/models.py:127`) and `SkillRequest.approval_required` (`app/models.py:143`) exist but are not yet active control-flow states.

### Scripts, capability catalog, and router seams
- Script manifest/runtime models live in `app/models.py` (`ScriptSpec`, `SkillManifest.script`, `SkillRecord.script`, `ScriptExecutionLog`).
- `app/script_validator.py:10-33` runs pytest with `safe_env(include_home=True)` and returns only `(bool, str)`; test execution is trusted-local code execution.
- `app/script_executor.py:11-49` runs scripts with JSON stdin, timeout, raw stdout/stderr capture, and return-code logging; stdout is not capped or validated against `output_schema`.
- `app/planner.py:8-37` hard-codes capability trigger rules and fallback `write structured answer`.
- `app/skill_requester.py:11-63` duplicates capability knowledge, including a contradiction-specific request template and generic fallback.
- `app/skill_router.py:51-76` computes weighted lexical/schema/status/risk/compatibility scores; `RouteDecision` does not preserve ranked candidates.

### Prior art and constraints
- No existing `docs/plans/` or `docs/completed/` prior plans were found before this plan was created.
- `docs/mvp-plan.md:87-104`, `docs/adr/0001-markdown-only-mvp.md:21-35`, and `docs/safety-model.md:3-54` establish the Markdown-only generated-skill safety boundary: no generated scripts/deps/network/secrets/promotion and no filesystem writes outside sanctioned artifacts.
- `docs/skill-lifecycle.md:3-13` distinguishes requested, draft, temporary, candidate, stable, deprecated, and blocked; temporary means one-task use after minimal validation.
- `docs/evaluation-plan.md:129-137` names success criteria: structured requests, no silent unsafe execution, visible trace, no unevaluated temporary promotion, and malicious-skill rejection.
- Recent relevant commits: `2a60b47` (static loader/run logs), `02e5ae1` (Skillsmith/scripted skills), `dcc9582` (library health), `0dd7156` (malicious rejection), `e7ce253` (demo/repair/acceptance).

### External research note
Context7 resolved official Pydantic docs as `/pydantic/pydantic`. Relevant guidance: additive optional fields with defaults are straightforward on `BaseModel`; JSON-safe serialization should use `model_dump(mode="json")`; `model_json_schema()` can document evolved schemas. This supports additive `RunLog` fields (`schema_version`, `run_id`, `execution_summary`, `trace_events`) with defaults and tolerant legacy reading.

## Approach

Implement this as a staged hardening sequence. First establish data contracts and runtime identity, then move temporary skills out of the durable registry, then wire explicit safety/result states, then improve observability, routing, scripts, health, and CLI surfaces. Keep existing human-readable CLI landmarks stable unless a work item explicitly updates them.

Treat Items 1–7 as the P0 invariant pass. Items 8–13 are follow-up hardening milestones; they are ordered, but they should not block shipping the core corrections unless the implementation discovers a direct dependency.

### 1. Establish schema-v2 contracts additively
Add the contract surface in `app/models.py` before changing behavior. The implementation should prefer additive fields with defaults where compatibility matters, then update tests around the new schema.

Planned contract concepts:
- `schema_version` on `RunLog`, with legacy logs treated as version 1.
- Unique `run_id` on every new run log, while preserving deterministic `task_id`.
- `SkillLifecycle` / provenance object separate from manifest status and validation status.
- Expanded `CapabilityDecisionType`: `USE_SKILL`, `REQUEST_SKILL`, `ASK_HUMAN`, `ABORT_UNSAFE`.
- `RunResultCategory`, including success, blocked missing skill, repair requested, awaiting human approval, unsafe aborted, script failed, and route/load failed.
- `TraceEvent` plus `RunLog.trace_events`, while preserving `RunLog.trace`.
- `ExecutionSummary` for stable CLI/JSON consumption.
- `RouteCandidate` for ranked router explanations.
- Richer `ScriptExecutionLog` fields for parsed/categorized script results.

### 2. Create stable run identity and schema-aware logging
Generate `run_id` at the start of `agent_loop.run_task()`, ideally through a helper in `app/run_log.py`. `write_run_log()` should use `run_log.run_id` for the filename while continuing to support `run_*.json` discovery patterns in `librarian.py`.

Recommended naming shape:

```text
run_YYYYMMDD_HHMMSS_<8-char uuid>.json
```

`task_id` remains deterministic and groups repeated task text; `run_id` identifies one execution and should be used for per-run artifacts, trace correlation, and health/report links.

### 3. Move temporary skills to run-scoped artifacts
Generated temporary skills should no longer mutate durable `skills_dir`. The exact artifact layout is tactical, but the invariant is fixed: generated temporary skills live under a per-run, inspectable artifact root tied to `run_id`, not under the durable seed library. A reasonable default is:

```text
runs/
  artifacts/
    <run_id>/
      skills/
        <temporary-skill-name>/
          SKILL.md
```

Key behavior:
- `agent_loop.run_task()` creates the per-run artifact root after `run_id` exists.
- `skillsmith.draft_temporary_skill()` accepts an explicit target root or context object rather than durable `skills_dir`.
- Successful generated skills validate against the temporary root and can load only for the current run.
- Failed generated Markdown stays under run artifacts for inspection/repair context but is never admitted or loaded.
- Durable `skills_dir` remains unchanged.
- `SkillRegistry.load()` should accept an ordered set of roots: durable root first, then zero or more per-run temporary roots for the active run only.
- Registry resolution should apply a run-local overlay: if a temporary `SkillRecord` has the same name as a durable record, the temporary record shadows the durable record only inside that run's registry instance.
- Each `SkillRecord` should carry a trusted `source_root` and lifecycle/provenance.
- `load_skill()` should validate containment against each `skill_record.source_root`, not a global `skills_dir`.

Prefer an explicit per-run registry overlay over globally scanning `runs/artifacts`; health and normal registry listing should not treat run artifacts as durable skills. `agent_loop.run_task()` creates the run-scoped registry instance after `run_id` exists, and `skillsmith.draft_temporary_skill()` receives an explicit target root so generated skills can only validate/load from the current run's temporary roots. This is the largest semantic correction and should land atomically with tests.

### 4. Add explicit safety control flow and result categories
Add a small safety classifier first, then fold it into the shared capability catalog when the catalog lands. Safety should not depend on the full catalog refactor.

Classification sources and precedence:
- **Task-text preflight** catches obvious unsafe requests before capability routing.
- **Capability safety metadata** classifies planned capabilities when catalog metadata is available.
- **Skill manifest permissions/risk** remain admission/routing inputs, but they do not replace task/capability safety checks.

Initial safety behavior:
- Secrets/API keys/payment/send email/delete files → `ABORT_UNSAFE`.
- File reads, external APIs, dependency installs, broad local mutation → `ASK_HUMAN`.
- Low-risk text/research transformations → normal routing.

Runtime behavior:
- `ASK_HUMAN`: do not draft, load, or execute; set `result_category = awaiting_human_approval`; exit nonzero; log the decision and approval reason.
- `ABORT_UNSAFE`: do not route/request/draft/load/execute; set `result_category = unsafe_aborted`; exit nonzero; log the unsafe reason.
- Missing skill, repair needed, route/load failure, and script failure should each receive distinct result categories instead of only `exit_code = 1`.

The final result category is determined by the precedence order below.

When multiple outcomes occur in one run, record all of them in trace/events, but choose one final `result_category` by precedence:
1. `unsafe_aborted`
2. `awaiting_human_approval`
3. `repair_requested`
4. `route_load_failed`
5. `script_failed`
6. `blocked_missing_skill`
7. `success`

### 5. Add structured observability without breaking text landmarks
Keep `RunLog.trace: list[str]` for compatibility and CLI readability, but add structured events. A small trace helper in `app/agent_loop.py` or `app/tracing.py` should append both a string landmark and a `TraceEvent`.

`ExecutionSummary` should summarize loaded skills, temporary skills, requests, repairs, script executions, failed scripts, rejected skills, and safety decisions. CLI output should print run ID, task ID, result category, exit code, and run-log path.

### 6. Consolidate capability definitions
Add a small local `app/capability_catalog.py`. This should not be a heavyweight plugin system; it is a deterministic catalog that removes duplicated rules/templates from `planner.py` and `skill_requester.py`.

The catalog should own:
- capability name
- trigger terms
- preferred/requested skill name
- safety risk/action
- input/output schemas
- success criteria
- failure modes

Use it from:
- `planner.plan_task()` for trigger matching
- `skill_requester.create_skill_request()` for request contracts
- `capability_checker.check_capabilities()` for safety decisions
- `skill_router` for additional scoring/explanation context, if useful

Preserve current behavior for bundled/demo capabilities before adding safety trap capabilities.

### 7. Improve router explanations before changing routing behavior
Add ranked candidates and scoring component details, but keep the current threshold and winning behavior unless tests show clear regressions. This is primarily observability and debuggability.

`RouteDecision` should keep `best_match` for compatibility and add a stable `ranked_candidates` list for JSON output and debugging.

### 8. Harden scripted skills while labeling the boundary honestly

Implementation note: Chunk 4 aligned the P0 risk-vs-complexity concern by making `detect contradictions` safety-low while recording its medium complexity separately in the catalog. The repair demo now uses the explicitly medium-risk `run local python analysis` capability, so validation failure demonstrates code-execution risk rather than text-task difficulty.

Scripted skills remain opt-in and should be described as restricted local subprocesses, not a true sandbox.

Harden the current path by:
- capping stdout/stderr before logging
- parsing stdout as JSON on successful return
- validating parsed output against the declared `output_schema`
- categorizing failures: timeout, nonzero exit, invalid JSON, output schema mismatch, output too large
- limiting pytest validation output
- keeping existing path containment checks

Script failures should set `result_category = script_failed` unless a higher-priority safety/repair category already applies.

### 9. Expand health and JSON surfaces
Use schema-v2 logs in `app/librarian.py` while tolerating v1 logs. Health should report result categories, temporary outcomes, repair counts, safety stops, human approval waits, script failure categories, and duplicate/stale capability signals.

Add JSON output for:
- `skill-agent run --json`
- `skill-agent registry --json`

Keep human-readable text as the default.

## Work Items

### Item 1 — Schema foundation
**Goal:** Add the contracts for schema versioning, `run_id`, lifecycle/provenance, result categories, safety decisions, structured trace events, execution summaries, ranked candidates, and richer script logs.

**Done when:**
- `app/models.py` supports the new fields with defaults where compatible.
- `CapabilityDecisionType` includes `ASK_HUMAN` and `ABORT_UNSAFE`.
- `RunLog` can represent schema v2 while old logs can still be read by health code once later migration work lands.
- No runtime behavior changes are required yet.

**Key files:** `app/models.py:9`, `app/models.py:12`, `app/models.py:178-224`, `app/models.py:227-230`

**Dependencies:** None

**Size:** Medium

### Item 2 — Run identity and schema-v2 logging
**Goal:** Add unique per-execution `run_id` while preserving deterministic `task_id`.

**Done when:**
- Every new run log contains `schema_version`, `run_id`, and existing `task_id`.
- `write_run_log()` uses the `run_id`-based filename.
- `librarian.py` treats logs without `schema_version` or `run_id` as legacy v1 logs.
- Existing tests that construct `RunLog` directly are updated.

**Key files:** `app/run_log.py:11-23`, `app/agent_loop.py:133-148`, `app/librarian.py:122-133`, `tests/test_loader_and_run_log.py:34-52`, `tests/test_librarian.py:18-39`

**Dependencies:** Item 1

**Size:** Medium

### Item 3 — Structured trace and execution summary
**Goal:** Supplement existing string trace with `trace_events` and `execution_summary`.

**Done when:**
- Existing CLI landmarks still print.
- Run logs contain ordered structured trace events.
- `execution_summary` accurately reports loaded skills, temporary skills, requests, repairs, rejected skills, scripts, failed scripts, and safety decisions.
- Acceptance tests assert both text landmarks and structured log fields.

**Key files:** `app/agent_loop.py:25-147`, `app/models.py:206-224`, `app/cli_output.py:10-82`, `tests/test_v0_acceptance.py`

**Dependencies:** Items 1–2

**Size:** Medium

### Item 4 — Run-scoped temporary skill storage
**Goal:** Stop writing generated temporary skills into durable `skills_dir`.

**Done when:**
- Temporary skills are written under `runs/artifacts/<run_id>/skills`.
- Durable `skills_dir` is unchanged after temporary-skill demos.
- Successful temporary skills can be validated and loaded for the current run.
- Failed temporary skills are retained under run artifacts but never loaded.
- Health does not treat run-scoped temporary skills as durable registry entries.
- Existing tests are updated away from durable-temp expectations.

**Key files:** `app/skillsmith.py:16-49`, `app/agent_loop.py:48-105`, `app/registry.py:16-35`, `app/skill_validator.py:53-56`, `app/loader.py:13-39`, `tests/test_skillsmith.py:24-33`, `tests/test_v0_acceptance.py:105-114`

**Dependencies:** Items 1–2

**Size:** Large

### Item 5 — Capability catalog
**Goal:** Consolidate planner triggers, request templates, risk, and safety metadata into a shared local catalog.

**Done when:**
- A new `app/capability_catalog.py` owns current known capability definitions.
- `planner.py` uses catalog trigger terms instead of local `RULES`.
- `skill_requester.py` uses catalog schemas/success criteria instead of contradiction-only special casing where possible.
- Current known capabilities preserve behavior.
- Tests cover catalog lookup and existing contradiction-request compatibility.

**Key files:** `app/planner.py:8-37`, `app/skill_requester.py:11-63`, `app/capability_checker.py:8-11`, `app/skill_router.py:51-76`, `tests/test_skill_requester.py`, new `tests/test_capability_catalog.py`

**Dependencies:** Item 1

**Size:** Medium

### Item 6 — Explicit safety decisions
**Goal:** Implement `ASK_HUMAN` and `ABORT_UNSAFE` as first-class control-flow outcomes.

**Done when:**
- Unsafe tasks do not route, request, draft, load, or execute.
- Approval-needed tasks stop with `result_category = awaiting_human_approval`.
- Unsafe tasks stop with `result_category = unsafe_aborted`.
- CLI output has safety-specific cards rather than treating these as missing-skill requests.
- Run logs preserve decision reason, approval/unsafe rationale, and structured trace events.

**Key files:** `app/models.py:12`, `app/capability_checker.py:8-11`, `app/agent_loop.py:39-129`, `app/cli_output.py:27-82`, `docs/contracts/data-contracts.md:53-59`, new `tests/test_safety_decisions.py`

**Dependencies:** Items 1 and 3. Item 5 should eventually supply the catalog-backed safety metadata, but this item can start with a small task-text/capability safety classifier so P0 safety does not wait on the full catalog refactor.

**Size:** Medium

### Item 7 — Result category normalization
**Goal:** Make final outcomes clearer than raw exit code.

**Done when:**
- Every run has exactly one `result_category`.
- Existing missing-skill, repair-request, route/load failure, and script-failure paths map to distinct categories.
- CLI `RESULT` prints result category, run ID, task ID, exit code, and run-log path.
- Tests still pass for existing success and blocked flows, with updated assertions for categories.

**Key files:** `app/agent_loop.py:39-129`, `app/cli_output.py:73-82`, `tests/test_v0_acceptance.py`, `tests/test_cli_m1.py`, `tests/test_demo_suite.py`

**Dependencies:** Items 1, 3, 6

**Size:** Medium

### Item 8 — Router ranked candidates and explanations
**Goal:** Preserve routing behavior while exposing better machine-readable explanations.

**Done when:**
- `RouteDecision` includes ranked candidates with scoring components.
- Existing best-match selection remains stable for seed-skill demos.
- JSON output can inspect why a skill won or missed threshold.
- Tests assert exact/schema-compatible skills outrank weaker lexical matches without broad threshold churn.

**Key files:** `app/skill_router.py:8-76`, `app/models.py:91-127`, `tests/test_skill_router.py`

**Dependencies:** Item 1

**Size:** Small

### Item 9 — JSON CLI surfaces
**Goal:** Add stable machine-readable output for `run` and `registry`.

**Done when:**
- `skill-agent run --json` emits structured result data without human-readable sections.
- `skill-agent registry --json` emits accepted/rejected records.
- Text output remains the default.
- JSON output includes `run_id`, `task_id`, `exit_code`, `result_category`, `run_log_path`, `execution_summary`, decisions, requests, repairs, and script executions.

**Key files:** `app/cli.py:17-47`, `app/cli_output.py:10-82`, `tests/test_cli_m1.py`, `tests/test_v0_acceptance.py`

**Dependencies:** Items 2–3, 7–8

**Size:** Medium

### Item 10 — Scripted-skill hardening
**Goal:** Make opt-in scripted skills more inspectable and failure-safe without claiming true sandboxing.

**Done when:**
- stdout/stderr are capped in logs.
- successful stdout is parsed as JSON.
- parsed output is validated against the declared output schema.
- script failure categories are logged and surfaced.
- script failures set `result_category = script_failed` when no higher-priority category applies.
- Tests cover invalid JSON, schema mismatch, huge output, timeout, and existing scripted success.

**Key files:** `app/script_executor.py:11-49`, `app/script_validator.py:10-33`, `app/env_utils.py`, `app/models.py:162-192`, `app/agent_loop.py:124-129`, `tests/test_scripted_skills.py`

**Dependencies:** Items 1, 7

**Size:** Medium

### Item 11 — Library health v2 metrics
**Goal:** Use new run-log fields to improve health reporting while remaining compatible with old logs.

**Done when:**
- Health reports result categories, temporary outcomes, repair counts, safety stops, human approval waits, route/load failures, and script failure categories.
- Existing `health --json` output includes the new metrics in a stable additive shape.
- Legacy handmade-log tests still pass.
- Health does not scan run-scoped temporary artifacts as durable accepted skills.
- Health remains read-only.

**Key files:** `app/librarian.py:12-143`, `app/models.py` health models, `app/cli.py` health command, `tests/test_librarian.py`

**Dependencies:** Items 2–3, 7, 10

**Size:** Medium

### Item 12 — Documentation and demo contract update
**Goal:** Align public docs with the hardened behavior.

**Done when:**
- Docs explain run-scoped temp artifacts, `run_id` vs `task_id`, safety decisions, result categories, JSON surfaces, and scripted-skill limitations.
- Demo/acceptance docs stop implying temporary skills are promoted or durable by default.
- Scripted skills are described as restricted local subprocesses, not a true sandbox.

**Key files:** `docs/contracts/data-contracts.md`, `docs/demo-suite.md`, `docs/build-map.md`, `docs/dev-log.md`, `docs/safety-model.md`, `docs/skill-lifecycle.md`, `README.md`, this plan

**Dependencies:** Items 1–11

**Size:** Medium

### Item 13 — Acceptance and CI finalization
**Goal:** Lock the improved behavior into the regression suite.

**Done when:**
- Full pytest suite passes.
- `compileall` passes if that remains part of the local validation habit.
- Acceptance tests cover existing skill, run-scoped temporary success, blocked missing skill, repair request, safety abort, human approval, malicious rejection, scripted success, and scripted failure.
- CI needs no special changes unless new tests require them.

**Key files:** `tests/test_v0_acceptance.py`, `tests/test_demo_suite.py`, `.github/workflows/tests.yml`

**Dependencies:** Items 1–12

**Size:** Medium

## Risks and Migration

### Run-log compatibility
Existing `runs/run_*.json` logs lack `schema_version`, `run_id`, `result_category`, and `trace_events`. Mitigate by treating missing schema version as v1, keeping `librarian.py` tolerant of raw dicts, and preserving `run_*.json` discovery.

### Demo/test behavior changes
Current tests assert temporary skill creation under durable `skills_dir`. This should intentionally change: tests should assert no durable mutation and validate the generated artifact under `runs/artifacts/<run_id>/skills` instead.

### Failed temporary skill retention
Retaining failed generated Markdown creates more artifacts. Keep them run-scoped, never include run artifacts in the durable registry by default, and let health report failed generated artifacts only through run-log data.

### Script hardening compatibility
Stricter stdout/schema validation may break future scripted fixtures. Current `count-words` already emits JSON matching `word_count: integer`; add clear failure categories for negative cases and keep scripted execution opt-in.

### Scope control
This plan intentionally does not implement full skill-guided Markdown execution, real sandboxing, marketplace behavior, or a web UI. Those remain later work after identity, observability, safety, and JSON surfaces are stable.

## Resolved Design Decisions
The implementation agent should preserve these locked decisions:
- Use an explicit per-run temporary registry overlay rather than globally scanning run artifacts.
- Ship minimal explicit safety decisions before the full capability catalog if that unblocks P0.
- Use the documented result-category precedence when multiple outcomes occur.
- Keep health JSON changes additive to the existing `health --json` surface.

Tactical choices should stay small unless tests reveal a better seam.

## References
- `docs/mvp-plan.md`
- `docs/adr/0001-markdown-only-mvp.md`
- `docs/safety-model.md`
- `docs/skill-lifecycle.md`
- `docs/contracts/data-contracts.md`
- `docs/evaluation-plan.md`
- Pydantic docs via Context7: `/pydantic/pydantic`
