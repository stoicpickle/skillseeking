# MVP Plan

## Product Wedge

The MVP is a CLI/API research workflow agent that can:

1. Plan a task as capabilities.
2. Check a small local skill library.
3. Admit when a required capability is missing.
4. Produce a structured skill request.
5. Draft or load a Markdown-only temporary skill.
6. Validate the skill with lightweight checks.
7. Continue the task.
8. Show a skill trace in the final output.

The next planned addition is a homeostatic governor: a small control layer that records confidence, risk, reversibility, approval need, and related signals for every capability decision.

## Why Research First

Research is a good first domain because:

- Skills are easy to name.
- Inputs and outputs can be inspected.
- Quality failures are visible.
- The final artifact can include citations and a trace.
- The demo does not need risky side effects.

## Initial Skills

```text
extract-claims
compare-claims
source-quality-check
write-structured-answer
validate-skill-md
```

Intentionally omit `detect-contradictions` in the first demo library so the system must request it.

## v0 Constraints

```text
CLI/API only
Markdown-only skills
Local skills folder only
No generated executable code
No external skill marketplace
No package installs
No network access from skills
No secrets
No filesystem writes outside project
No autonomous promotion to stable
No generated or temporary skill self-promotion
```

## Phase 1: Static Skill Loader

Goal: choose from existing skills.

Build:

- `skills/` folder.
- `SKILL.md` metadata parser.
- Skill registry index.
- Skill router.
- `load_skill` function.
- Run logs.
- CLI command for `skill-agent run`.

Out of scope:

- Generated skills.
- Executable scripts.
- External skill import.

## Phase 2: Skill Request Mode

Goal: expose missing capability as product output.

Build:

- Capability checker.
- Skill request JSON schema.
- Blocked state.
- Skill request UI card.
- Human approval path for generated or risky requests.

This is the core demo.

## Phase 3: Temporary Markdown Skills

Goal: allow simple skill creation without code execution risk.

Build:

- Skillsmith role.
- `SKILL.md` generator.
- Static validator.
- Temporary skill loader.
- One-run skill usage log.

Rules:

- No scripts.
- No new dependencies.
- No network.
- No filesystem writes outside the run log.

## Phase 4: Scripted Skills

Goal: allow executable skills only after validation.

Build:

- `scripts/` support.
- Pytest validation.
- JSON Schema checks.
- Restricted subprocess or Docker sandbox.
- Dependency allowlist.
- Execution logs.

## Phase 5: Skill Maintenance

Goal: keep the library useful.

Build:

- Usage metrics.
- Failure logs.
- Duplicate detection.
- Stale dependency checks.
- Repair workflow.
- Retirement workflow.

## Suggested Repo Structure

```text
skill-seeking-agent/
  app/
    main.py
    agent_loop.py
    planner.py
    capability_checker.py
    skill_router.py
    skill_requester.py
    skillsmith.py
    validator.py
    sandbox.py
    librarian.py
  skills/
    extract-claims/
      SKILL.md
      examples/
    source-quality-map/
      SKILL.md
      references/
  runs/
    run_2026_05_29_001.json
  evals/
    tasks.jsonl
    expected_outputs/
  ui/
    ...
```

## First Demo Script

Task:

```text
Analyze these three short articles and find where they agree, disagree, or make unsupported claims.
```

Expected trace:

```text
1. Agent extracts needed capabilities.
2. Agent finds extract-claims.
3. Agent finds source-quality-map.
4. Agent cannot find contradiction-detection.
5. Agent requests contradiction-detection.
6. Skillsmith drafts it.
7. Validator runs sample checks.
8. Agent loads temporary skill.
9. Final answer includes agreement map, disagreement map, unsupported claims, and skill trace.
```

## Required v0 Demo Cases

```text
1. Existing-skill task:
   Agent finds the right skills and completes the task.

2. Missing-skill task:
   Agent detects a gap, requests a skill, validates it, and continues.

3. Malicious-skill task:
   Agent rejects a skill with suspicious metadata or unsafe permissions.
```
