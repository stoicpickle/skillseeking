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
