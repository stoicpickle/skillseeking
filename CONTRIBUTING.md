# Contributing

This repository is open source under the MIT License. It is still a local CLI public-dev-preview workbench, not a hosted product, production agent framework, marketplace, true sandbox, or autonomous promotion system.

## Contribution Boundary

Contributions are welcome when they strengthen the governed local CLI loop:

- documentation clarity;
- local CLI bug fixes;
- eval rows and fixtures;
- public-claim guardrails;
- demo reproducibility;
- evidence and report usability;
- safety, no-mutation, and review-boundary tests.

Please do not open drive-by changes that expand authority or public claims into:

- hosted service behavior;
- skill marketplace support;
- autonomous skill promotion;
- durable generated-skill admission into `skills/`;
- true sandboxing claims;
- permission widening without explicit review;
- active governor steering;
- broad planner/router rewrites without eval evidence.

Those areas need separate product planning, evidence, and review before code
changes.

## Before Opening A Change

Start from the current docs:

- [README](README.md)
- [Product manager profile](docs/product-manager.md)
- [Post-v1 public dev-preview tasking](docs/post-v1-public-dev-preview-tasking-2026-06-07.md)
- [Safety model](docs/safety-model.md)
- [V1 release contract](docs/v1-release-contract.md)

For docs-only changes, run:

```bash
git diff --check
```

For behavior changes, run the relevant focused tests first, then the repo's
broader validation bundle:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
```

When release boundaries, eval behavior, routing, lifecycle evidence, safety, or
mutation authority changes, also run the relevant smoke/eval command documented
near the changed surface.

## Design-Partner Feedback

If you are trying the local CLI on a real workflow, use
[Design Partner Feedback](docs/design-partner-feedback.md) to capture setup
friction, demo comprehension, evidence confusion, candidate-decision confusion,
safety-boundary confusion, and stable-routing deferral confusion. You can run
`skill-agent feedback-session-template` to print the canonical session block,
then manually copy completed notes into
[Design Partner Feedback Log](docs/design-partner-feedback-log.md). The helper
does not append to the log, update rollups, or grant new authority.
