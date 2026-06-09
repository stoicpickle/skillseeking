# Roadmap

## Public Sharing Note

This repo should be framed publicly as an early research/prototype repo, not a production agent framework. Known next steps are roadmap items, not surprise defects: richer skill-guided execution, stronger sandboxing, broader SkillOps, and eventual UI/API surfaces.

The current repo source boundary is resolved as MIT-licensed open source for the local CLI dev-preview. That license does not imply hosted service availability, production safety, marketplace support, true sandboxing, or support commitments. Contribution expectations live in [Contributing](../CONTRIBUTING.md).

## Phase 1: Static Skill Loader

Goal: the agent can choose from existing skills.

Deliverables:

- `skills/` folder convention.
- `SKILL.md` metadata parser.
- Skill registry index.
- Skill router.
- Run log.
- CLI or API endpoint for "plan and route".

Demo:

```text
User task -> capability plan -> skills selected -> skill trace
```

## Phase 2: Skill Request Mode

Goal: the agent can say what it lacks.

Deliverables:

- Capability checker.
- Skill request contract.
- Blocked response.
- UI card for missing capability.
- Approval state model.

Demo:

```text
User task -> missing capability -> structured skill request
```

## Phase 3: Markdown-Only Skillsmith

Goal: the system can draft temporary skills without code execution.

Deliverables:

- Skillsmith role.
- Markdown skill generator.
- Static validator.
- Temporary skill state.
- One-run loading.

Demo:

```text
BLOCKED -> REQUESTED SKILL -> DRAFTED -> VALIDATED -> LOADED -> CONTINUED
```

## Phase 4: Scripted Skills

Goal: executable skills can be used with explicit opt-in trusted-local guardrails. This is not a true sandbox yet.

Deliverables:

- Script execution interface.
- JSON Schema I/O validation.
- Pytest runner.
- Restricted local subprocess now; Docker/true sandboxing later.
- Dependency allowlist.
- Runtime logs.

Demo:

```text
PDF table task -> request script skill -> validate -> execute in restricted local subprocess
```

## Phase 5: SkillOps

Goal: the skill library improves instead of decaying.

Deliverables:

- Skill metrics.
- Duplicate detection.
- Repair workflow.
- Deprecation workflow.
- Library health dashboard.
- Periodic validation job.

Demo:

```text
High-failure skill -> repair request -> validator -> candidate replacement
```

## Later Questions

- Should skills be shareable across users or local-only?
- Should external skills require signatures?
- A public skill marketplace remains deferred; any commercial exploration should stay secondary to policy, evidence, approval, and audit surfaces.
- Should Skillsmith use templates per domain?
- Should the first UI be web, CLI, or both?
