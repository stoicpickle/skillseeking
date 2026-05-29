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
