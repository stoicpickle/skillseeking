# Skill-Seeking Agent

Skill-Seeking Agent is a documentation-first concept for an agent that can recognize capability gaps, request the missing skill, validate it, load it temporarily, and continue the task with a visible trace.

The product is not "a chatbot with many tools." The product is the agent's ability to say:

> I am blocked because I lack capability X. I need a skill with input Y, output Z, and success test W.

That capability-gap loop is the core demo, the trust surface, and the long-term product wedge.

## Current Documentation

- [Product brief](docs/product-brief.md)
- [System architecture](docs/architecture.md)
- [Skill lifecycle](docs/skill-lifecycle.md)
- [MVP plan](docs/mvp-plan.md)
- [v0 build guardrails](docs/v0-build-guardrails.md)
- [Build map](docs/build-map.md)
- [Data contracts](docs/contracts/data-contracts.md)
- [Evaluation plan](docs/evaluation-plan.md)
- [Safety model](docs/safety-model.md)
- [Roadmap](docs/roadmap.md)
- [Dev log](docs/dev-log.md)
- [Clarifying questions](docs/clarifying-questions.md)
- [References](docs/reference/references.md)
- [ADR 0001: Markdown-only MVP](docs/adr/0001-markdown-only-mvp.md)

## North Star

Build an agent that becomes more capable by maintaining a validated library of reusable skills while staying transparent about what it can and cannot do.

The mature system should:

- Plan tasks in terms of required capabilities.
- Check current skills before executing.
- Produce structured skill requests when blocked.
- Retrieve, draft, validate, and provisionally load skills.
- Log outcomes and maintain the skill library over time.
- Keep unsafe or unvalidated capabilities out of the execution path.

## MVP Boundary

Start with research workflows and Markdown-only skills.

Initial capabilities:

- Search sources.
- Extract claims.
- Score source quality.
- Detect contradictions.
- Build evidence tables.
- Write cited summaries.

The first public demo should show:

```text
BLOCKED -> REQUESTED SKILL -> VALIDATED -> LOADED -> CONTINUED
```

That trace is more important than the final answer. The hook is visible capability self-awareness.

## Implementation Bias

Keep the first build boring:

- Python + FastAPI for the backend.
- SQLite for records and run logs.
- Agent Skills-style folders with `SKILL.md`.
- BM25 plus schema matching before embeddings-only retrieval.
- JSON Schema for contracts.
- Pytest once executable skills are introduced.
- No generated executable code in the first phase.

## M1 Quick Start

Set up the local environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

List local skills:

```bash
.venv/bin/skill-agent registry
```

Run the M1 existing-skill demo:

```bash
.venv/bin/skill-agent run "Extract claims from this article and write a structured summary with source-quality notes."
```

Run the M2 blocked-only skill request demo:

```bash
.venv/bin/skill-agent run "Extract claims from these two sources and identify contradictions." --no-temporary-skills
```

Run the M3 temporary Markdown skill demo:

```bash
.venv/bin/skill-agent run "Cluster arguments from these sources."
```

Run the M7 canonical v0 trace demo:

```bash
.venv/bin/skill-agent run "Cluster arguments from these sources."
```

Expected landmarks: `PLANNING`, `CHECKING_SKILLS`, `BLOCKED_MISSING_SKILL`, `REQUESTING_SKILL`, `VALIDATION_PASSED`, `LOADING_TEMP_SKILL`, `ROUTE_COMPLETE`, and `RESULT`.

Run the M4 scripted-skill demo:

```bash
.venv/bin/skill-agent run "Count words in one two three." --scripted-skills --no-temporary-skills --skills-dir tests/fixtures/scripted-skills
```

Run the M5 library health report:

```bash
.venv/bin/skill-agent health
.venv/bin/skill-agent health --json
```

Run the M6 malicious-skill rejection demo:

```bash
mkdir -p /tmp/skillseeking-empty-runs
.venv/bin/skill-agent registry --skills-dir tests/fixtures/malicious-skills
.venv/bin/skill-agent health --skills-dir tests/fixtures/malicious-skills --runs-dir /tmp/skillseeking-empty-runs
```

Run tests:

```bash
.venv/bin/python -m pytest -q
```
