# Build Map

## Naming

Use this hierarchy:

```text
Milestone -> Slice -> Task -> Check
```

## Milestone

A milestone is a meaningful product capability.

Examples:

- Static skill loader.
- Skill request mode.
- Markdown Skillsmith.
- Scripted skills.
- Skill maintenance.

Milestones answer:

```text
What new product behavior exists after this work?
```

## Slice

A slice is a small, demoable piece of a milestone.

Examples:

- Parse local `SKILL.md` metadata.
- Route a task to an existing skill.
- Emit a blocked missing-skill response.
- Validate a Markdown skill.
- Reject suspicious skill metadata.

Slices answer:

```text
What can we build and verify in one focused pass?
```

Use "slice" as the main planning unit. It keeps the project practical and product-shaped.

## Task

A task is an implementation step inside a slice.

Examples:

- Add YAML frontmatter parser.
- Define `SkillRecord`.
- Add suspicious text scanner.
- Write CLI command.
- Add sample skill fixture.

Tasks answer:

```text
What concrete change needs to happen?
```

## Check

A check proves the task or slice works.

Examples:

- Unit test passes.
- CLI trace contains `BLOCKED`.
- Malicious skill fixture is rejected.
- Run log is written under `runs/`.

Checks answer:

```text
How do we know this did not just sound correct?
```

## Status Values

Use these statuses everywhere:

```text
not_started
working
blocked
complete
deferred
cut
```

## Status Meanings

### not_started

Defined, but no implementation work has begun.

### working

Currently being designed, implemented, or verified.

### blocked

Cannot continue without a decision, missing dependency, or failed prerequisite.

### complete

Implemented and verified against its checks.

### deferred

Still valid, but intentionally postponed.

### cut

Removed from the current plan. This is stronger than deferred.

## Build Map Format

Use this format for milestone tracking:

```markdown
## Milestone 1: Static Skill Loader

Status: working

Goal:
Load local Markdown skills and route a task to the best available skill.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Parse skill metadata | complete | Valid and invalid fixtures covered |
| Build skill registry | working | Registry lists local skills |
| Route by capability | not_started | Existing-skill demo chooses expected skill |
| Emit run trace | not_started | JSON log written under `runs/` |
```

## v0 Milestones

| Milestone | Status | Product Proof |
| --- | --- | --- |
| Static skill loader | complete | Existing-skill task selects and loads local skill |
| Skill request mode | complete | Missing-skill task emits structured request |
| Markdown Skillsmith | complete | Temporary Markdown skill is drafted and validated |
| Scripted skills | complete | Scripted local skill validates and executes only when explicitly enabled |
| Skill maintenance | complete | Library health report summarizes usage, requests, failures, duplicates, and rejected skills |
| Malicious skill rejection | complete | Suspicious skill fixtures are quarantined and visible in registry/health reports |
| v0 trace demo | complete | CLI shows plan -> check -> blocked -> request -> validate -> load -> result |
| Core demo suite | complete | Four canonical demos document expected commands, statuses, and output landmarks |
| Skill repair request | complete | Failed temporary validation emits a structured repair request without auto-repairing |
| v0 acceptance harness | complete | End-to-end CLI cases verify traces, run logs, filesystem effects, and entrypoint smoke |
| Skill Gauntlet demo | complete | One scripted showcase combines safe loading, malicious rejection, temporary skill loading, repair request, and run-log proof |
| Capability-Gap Eval Harness | complete | JSONL eval suites run through the real loop with reports and trace explain output |
| Capability-Gap Calibration | complete | Twenty-task suite tracks classification, safety, approval, trace completeness, and failure taxonomy |
| Skill Candidate Ledger | complete | Repeated gaps, temporary outcomes, repair requirements, rejected skills, duplicate contracts, and promotion requirements are recorded and surfaced without auto-promotion |
| Lifecycle review queues and health expansion | complete | Candidate and health surfaces derive advisory promotion-ready, repair-needed, blocked/quarantined, duplicate, and repeated-gap review queues without steering execution |
| Durable candidate admission planning | complete | `admission-plan` reports durable review readiness, evidence gaps, source validation, and registry collisions without copying or installing skills |

## Current First Slice

Recommended first slice:

```text
Milestone: Static skill loader
Slice: Parse local skill metadata
Status: complete
```

Tasks:

- Define skill folder convention.
- Create sample seed skills.
- Parse YAML frontmatter from `SKILL.md`.
- Validate required metadata fields.
- Reject invalid names, missing risk, and missing permissions.
- Print registry contents from the CLI.

Checks:

- Valid seed skills are listed.
- Invalid sample skill is rejected.
- No Markdown body instructions are used for routing.
- CLI exits cleanly with a readable trace.

## Milestone 1: Static Skill Loader

Status: complete

Goal:
Load local Markdown skills and route a task to the best available existing skill or skills.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Project scaffold and CLI boundary | complete | `skill-agent run` and `skill-agent registry` are available |
| Local skill folder convention and seed skills | complete | Five normalized seed skills are listed |
| `SKILL.md` parser and compact metadata extraction | complete | Valid fixtures parse and malformed fixtures reject |
| Metadata validation and M1 safety admission | complete | Unsafe permissions, scripts, and suspicious text reject |
| Registry index | complete | Accepted and rejected local skills are tracked deterministically |
| Deterministic planner and capability checker | complete | Demo task maps to expected capabilities |
| Basic skill router | complete | Existing-skill demo selects expected skills |
| `load_skill` | complete | Full Markdown loads only after selection |
| Run trace and JSON run logs | complete | JSON logs are written under `runs/` without full Markdown bodies |
| Existing-skill demo | complete | CLI exits cleanly and emits the expected trace |

## Milestone 2: Skill Request Mode

Status: complete

Goal:
Expose missing capabilities as structured skill requests without generating or loading new skills.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Skill request data contract | complete | Pydantic model includes capability, schemas, success criteria, risk, and status |
| Skill requester | complete | Missing `detect contradictions` route creates `detect-contradictions` request |
| Blocked CLI trace | complete | CLI prints `BLOCKED_MISSING_SKILL`, `REQUESTING_SKILL`, and a blocked card |
| Run log persistence | complete | JSON run log includes `skill_requests` |
| No generation boundary | complete | Missing-skill demo does not create `skills/detect-contradictions` |

## Milestone 3: Markdown Skillsmith

Status: complete

Goal:
Draft, validate, and load Markdown-only temporary skills for missing capabilities.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Temporary skill writer | complete | Skillsmith writes `skills/<requested-name>/SKILL.md` only |
| Safe frontmatter generation | complete | Generated YAML validates through the existing parser and validator |
| Temporary validation | complete | Generated skills have `validation.status: temporary` |
| Agent-loop integration | complete | Missing capability drafts, validates, and loads the temporary skill |
| M2 compatibility mode | complete | `--no-temporary-skills` preserves blocked-only request behavior |
| Run log trace | complete | Logs include request plus temporary skill validation/load status |

## Milestone 4: Scripted Skills

Status: complete

Goal:
Allow local scripted skills to validate and execute only behind an explicit CLI flag.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Script manifest contract | complete | Scripted skills declare `script.entrypoint`, medium risk, `allowed_tools: [python]`, and `execute_code: true` |
| Explicit enablement | complete | Scripted skills are rejected unless `allow_scripts` / `--scripted-skills` is set |
| Pytest validation | complete | Scripted skill tests pass before the skill is admitted to the registry |
| Restricted subprocess execution | complete | Script runs with JSON stdin/stdout, timeout, captured logs, and a reduced environment |
| Run log trace | complete | Logs include script command, return code, stdout, stderr, and timeout status |

## Milestone 5: Skill Maintenance

Status: complete

Goal:
Report skill-library health from local skill metadata and run logs.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Health report model | complete | Structured report includes accepted/rejected counts, run-log count, metrics, and issues |
| Run-log metrics | complete | Loaded skills, temporary uses, requests, and script failures are counted |
| Library issue detection | complete | Rejected skills, duplicate contracts, failed temporary validation, failed script execution, and unused skills are reported |
| CLI report | complete | `skill-agent health` prints text and `skill-agent health --json` prints JSON |
| Local-only boundary | complete | Health reads local `skills/` and `runs/` only and does not modify files |

## Milestone 6: Malicious Skill Rejection

Status: complete

Goal:
Prove unsafe local skill packages are quarantined before routing or loading.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Malicious fixture set | complete | Safe control skill is accepted while metadata, body, obfuscated, and secrets attacks reject |
| Registry quarantine proof | complete | `skill-agent registry` shows accepted skills and `REJECTED` rows for malicious fixtures |
| Health visibility | complete | `skill-agent health` and `health --json` report rejected-skill issues |
| No new runtime surface | complete | M6 adds no new CLI command, execution path, network access, or generated code |

## Milestone 7: v0 Trace Demo

Status: complete

Goal:
Make the successful temporary-skill path the polished canonical v0 trace demo.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Stable CLI surface | complete | M7 uses `skill-agent run` with no new command or dependency |
| Trace landmarks | complete | Canonical run prints `PLANNING`, `CHECKING_SKILLS`, `BLOCKED_MISSING_SKILL`, `REQUESTING_SKILL`, `VALIDATION_PASSED`, `LOADING_TEMP_SKILL`, and `ROUTE_COMPLETE` |
| Result summary | complete | CLI prints `RESULT` with exit code, loaded skills, temporary skills, and run-log path |
| Regression coverage | complete | Existing-skill, blocked-only, scripted-skill, health, malicious-rejection, and failed-validation paths remain covered |

## Milestone 8: Core Demo Suite

Status: complete

Goal:
Make the v0 behavior easy to understand, rerun, test, and share.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Demo guide | complete | `docs/demo-suite.md` lists four canonical demos with commands, statuses, landmarks, and proof statements |
| README entrypoint | complete | README links the demo suite and includes copy-paste commands using an isolated skills copy |
| Existing-skill demo contract | complete | Test locks status and landmarks for the existing-skill path |
| Temporary-skill demo contract | complete | Test locks status and landmarks for the temporary skill success path |
| Blocked demo contract | complete | Test locks status and landmarks for blocked request mode |
| Malicious-skill demo contract | complete | Test locks registry quarantine output for malicious fixtures |

## Milestone 9: Skill Repair Request

Status: complete

Goal:
Turn failed temporary skill validation into a structured repair request without auto-repairing or auto-loading anything.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Repair request contract | complete | `SkillRepairRequest` records failed skill, capability, validation reasons, objective, constraints, and status |
| Failure-path integration | complete | Temporary validation failure appends `REQUESTING_REPAIR` and writes `skill_repair_requests` to the run log |
| CLI repair card | complete | `skill-agent run` prints `REPAIR_REQUESTED` with skill, capability, status, objective, and failure reasons |
| No auto-repair boundary | complete | M9 does not rewrite, validate, load, or promote a repaired skill |
| Regression coverage | complete | Tests prove an explicitly medium-risk `local-python-analysis` temporary validation failure emits a repair request while staying blocked |

## Milestone 10: v0 Acceptance Harness

Status: complete

Goal:
Prove the v0 loop end to end with isolated, repeatable CLI acceptance cases.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Acceptance helpers | complete | Shared helpers check ordered landmarks, run-log JSON, and no Markdown bodies |
| Core CLI matrix | complete | Existing, temporary, blocked, repair, malicious, scripted success, and scripted failure paths are covered |
| Run-log assertions | complete | Acceptance cases verify loaded skills, requests, repair requests, result categories, script executions, and script failure categories |
| Filesystem assertions | complete | Tests verify expected temporary skill creation or cleanup |
| Entrypoint smoke | complete | Subprocess smoke runs `.venv/bin/skill-agent` when available |

## Milestone 11: Skill Gauntlet Demo

Status: complete

Goal:
Create one screenshot-worthy pressure test that shows capability awareness and safety judgment together.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Gauntlet fixture library | complete | Dedicated fixture includes three safe skills and two malicious skills while omitting `argument-clustering` and `local-python-analysis` |
| Scripted showcase | complete | `scripts/run_gauntlet_demo.py` prints `SKILL GAUNTLET`, registry status, trace, and result summary |
| Mixed-pressure run | complete | Demo loads safe skills, rejects malicious fixtures, loads `argument-clustering` temporarily, and requests repair for `local-python-analysis` |
| Run-log proof | complete | Test verifies requested skills, rejected skills, repair request, temporary artifacts, and no `markdown_body` leakage |

## Milestone 12: Capability-Gap Eval Harness

Status: complete

Goal:
Turn the capability-gap loop into a repeatable eval harness with auditable reports.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Eval suite loader | complete | JSONL tasks load with line-numbered errors for invalid input |
| Eval runner | complete | `skill-agent eval --suite evals/capgap_smoke.jsonl --skills-dir skills --runs-dir runs/evals` executes real run-loop tasks |
| Request-quality scorer | complete | Deterministic 0-5 score covers specificity, contracts, success criteria, failure modes, risk correctness, and reuse potential |
| Reports | complete | Eval writes machine-readable JSON and human-readable Markdown summaries |
| Trace explainer | complete | `skill-agent explain <run-log.json>` summarizes task, capabilities, decisions, requests, safety stops, and trace stages |
| Regression coverage | complete | Tests cover loader, reports, CLI eval, request scoring, explain, and CI eval smoke |

## Milestone 13: Capability-Gap Calibration

Status: complete

Goal:
Prove the agent can classify capability gaps across varied normal, missing-skill, workflow-guidance, adversarial-routing, unsafe, and approval-required tasks.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| End-to-end calibration test | complete | `tests/test_capgap_eval_end_to_end.py` covers existing skill, missing skill, unsafe stop, approval wait, reports, and explain output |
| Twenty-task suite | complete | `evals/capgap_v0.jsonl` includes 5 existing-skill, 5 missing-skill, 3 workflow-guidance, 3 adversarial-routing, 2 unsafe, and 2 approval-required tasks |
| Failure taxonomy | complete | Failed eval tasks emit categories such as `wrong_route`, `missing_skill_not_detected`, `approval_not_requested`, and `trace_incomplete` |
| Diagnostic reports | complete | Markdown reports show summary metrics, failure categories, per-failure diagnostics, suggested next action, and `skill-agent explain` command |
| Calibration fix loop | complete | The first 20-task run exposed `approval_not_requested` for "read local files"; classifier coverage now catches that phrase |


## Milestone 14: Skill Candidate Ledger

Status: complete

Goal:
Turn repeated capability gaps and temporary-skill outcomes into durable, human-reviewable lifecycle evidence without changing routing, promotion, or governor behavior.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Ledger contract and persistence | complete | `runs/skill_candidate_ledger.json` records deterministic candidate entries and preserves evidence run IDs |
| Runtime evidence recording | complete | Run logs feed missing requests, temporary outcomes, repair requirements, rejected skills, and duplicate contracts into the ledger |
| Review surfaces | complete | `skill-agent candidates`, `health`, `explain --include-candidates`, and eval reports expose candidate evidence |
| Lifecycle eval smoke | complete | `evals/skill_lifecycle_v0.jsonl` proves repeated gaps, temporary success, and repair-required failure accumulate evidence without auto-promotion |
| Degraded ledger handling | complete | Corrupt ledger summaries do not prevent task/run-log completion; the run trace records `LEDGER_RECORD_FAILED` |

Boundaries:

- No generated or temporary skill is durably promoted.
- Ledger `human_approval_required` means promotion approval, not current-run approval.
- Governor behavior remains observational.


## Milestone 15: Testing/Iteration Readiness

Status: complete

Goal:
Prove the current CLI prototype can be tested and iterated locally without widening lifecycle, durable admission, or governor boundaries.

Slices:

| Slice | Status | Checks |
| --- | --- | --- |
| Lifecycle/admission acceptance proof | complete | `tests/test_testing_iteration_readiness.py` covers temporary skill creation, candidate approval, and `admission-plan` dry run without durable skill mutation |
| Lifecycle eval in validation bundle | complete | CI and the local validation bundle run `evals/skill_lifecycle_v0.jsonl` |
| Roadmap checkpoint docs | complete | README and operating roadmap distinguish local testing readiness from production readiness |

Boundaries:

- No durable candidate copy/install workflow is introduced.
- `ready_for_durable_review` remains review evidence, not admission to `skills/`.
- Active governor steering, stable promotion, permission widening, and true sandboxing remain future work.
