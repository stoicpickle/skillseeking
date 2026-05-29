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
| Malicious skill rejection | not_started | Suspicious skill fixture is quarantined |
| v0 trace demo | not_started | CLI shows plan -> check -> blocked -> request -> validate -> load -> result |

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
