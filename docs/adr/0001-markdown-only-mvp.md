# ADR 0001: Start With Markdown-Only Skills

## Status

Accepted for MVP planning.

## Context

The full concept includes generated skills, optional scripts, tests, sandboxes, approvals, and long-term skill maintenance. That is the right long-term direction, but starting with executable generated skills would make safety, dependency management, and validation the main project before the product loop is proven.

The most important demo is:

```text
BLOCKED -> REQUESTED SKILL -> VALIDATED -> LOADED -> CONTINUED
```

That can be demonstrated with Markdown-only procedural skills.

## Decision

The MVP supports Markdown-only skills first.

Generated skills may include:

- `SKILL.md`
- Input and output contracts.
- Examples.
- Validation notes.
- Failure cases.

Generated skills may not include:

- Executable scripts.
- New dependencies.
- Network calls.
- Filesystem mutation.

## Consequences

Benefits:

- Lower safety risk.
- Faster path to a visible product demo.
- Easier validation.
- Better focus on capability-gap detection.

Tradeoffs:

- Some skills will be less powerful.
- PDF, table, image, browser, and code tasks may require pre-existing tools.
- Scripted automation waits until the lifecycle and validation surfaces are proven.

## Revisit

Revisit when:

- The static skill loader works.
- Skill request mode works.
- Temporary Markdown skills are validated and logged.
- The product loop is clear enough that scripted skills are worth the added risk.

