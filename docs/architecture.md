# Architecture

## System Shape

```text
+------------------+
| User Task        |
+--------+---------+
         |
         v
+------------------+
| Task Planner     |
+--------+---------+
         |
         v
+------------------+
| Capability Check |
+--------+---------+
         |
         v
+------------------+
| Homeostatic      |
| Governor         |
+---+----------+---+
    |          |
    |          v
    |   +-----------------+
    |   | Skill Requester |
    |   +--------+--------+
    |            |
    v            v
+--------------+ +-----------------+
| Skill Router | | Skillsmith      |
+------+-------+ +--------+--------+
       |                  |
       v                  v
+--------------+ +-----------------+
| Load Skill   | | Validator/Test  |
+------+-------+ +--------+--------+
       |                  |
       +---------+--------+
                 |
                 v
+--------------------------------------+
| Execute Task With Selected Skills    |
+------------------+-------------------+
                   |
                   v
+--------------------------------------+
| Evaluate Outcome + Update Skill Log  |
+--------------------------------------+
```

## Components

### Task Planner

Breaks a user task into required capabilities without executing the task.

Example:

```text
Task: Compare these two PDFs and find contradictions.

Capabilities needed:
- read PDF text
- extract claims
- normalize claims
- compare claims
- classify contradictions
- cite source locations
```

### Capability Checker

The central product component.

For every required capability, it decides:

```text
- USE_SKILL
- REQUEST_SKILL
- ASK_HUMAN
- ABORT_UNSAFE
```

The checker should explicitly distinguish:

- Existing skill use.
- Missing skill request.
- Missing data.
- Insufficient confidence.
- Unsafe operation.
- Permission needed.

Temporary skill drafting is represented as run-scoped evidence on missing-skill requests, not as a separate durable capability decision type.

### Homeostatic Governor

The governor is the control layer around each capability decision. It does not replace the planner, checker, router, validator, or safety model. It records the signals that explain why the system should use a skill, request a skill, ask a human, or stop.

Initial control signals:

- Confidence.
- Safety risk.
- Reversibility.
- Approval requirement.
- Data freshness concern.
- Tool failure history.
- Cost or latency concern.

The governor emits one of the same decision types used by capability decisions:

```text
USE_SKILL
REQUEST_SKILL
ASK_HUMAN
ABORT_UNSAFE
```

The first implementation should be deterministic and auditable. It should combine existing planner, router, safety, permission, and validation outputs into a visible governor record in the run log.

More detail lives in `docs/homeostatic-governor.md`.

### Skill Registry

A local skill library using Agent Skills-style folders:

```text
skills/
  extract-claims/
    SKILL.md
    scripts/
    tests/
    examples/
  compare-claims/
    SKILL.md
    scripts/
    tests/
  source-quality-map/
    SKILL.md
    references/
```

At startup, only compact metadata should be loaded. The full `SKILL.md` is loaded only when the router selects that skill.

### Skill Router

Ranks available skills by multiple signals:

```text
score =
  semantic_match * 0.35
+ schema_match * 0.25
+ prior_success * 0.20
+ compatibility * 0.10
+ freshness * 0.05
+ risk_penalty * -0.20
```

The exact weights are provisional. The important decision is to avoid embeddings-only routing.

Required router inputs:

- Capability request.
- Skill metadata.
- Input and output schema.
- Risk level.
- Allowed tools.
- Test status.
- Compatibility.
- Prior performance.

### Skill Requester

Turns a missing capability into a structured request.

The request must include:

- Desired capability.
- Reason the task is blocked.
- Minimum viable input contract.
- Minimum viable output contract.
- Success criteria.
- Risk classification.
- Approval requirements.

### Skillsmith

Creates or repairs skills. This should be a separate role from the main task agent.

Skillsmith output should include:

- `SKILL.md`.
- Input and output contract.
- Example inputs.
- Example outputs.
- Tests or validation criteria.
- Dependencies.
- Risk classification.
- Rollback instructions.

For Phase 1 through Phase 3, Skillsmith creates Markdown-only skills.

### Validator

Validates candidate skills before loading.

Static checks:

- Valid `SKILL.md` metadata.
- Allowed name format.
- No suspicious instructions.
- Declared dependencies.
- Permission scope.

Behavior checks:

- Happy path.
- Empty input.
- Malformed input.
- Large input.
- Adversarial input.

Runtime checks for scripted skills:

- Timeout.
- Memory limit.
- No unexpected network access.
- No file access outside sandbox.
- Logs captured.

### Execution Sandbox

Generated or external scripted skills run in a controlled environment:

- Isolated working directory.
- No secrets by default.
- No network by default.
- Limited filesystem access.
- Timeout.
- Memory cap.
- Dependency allowlist.
- Captured logs.

### Skill Librarian

Maintains the library over time.

Responsibilities:

- Version skills.
- Track usage.
- Track failures.
- Merge duplicates.
- Retire stale skills.
- Add validators.
- Detect dependency drift.
- Review risky skills.

## Agents SDK Fit

Current OpenAI Agents SDK concepts map naturally onto this design:

- Function tools can wrap skill registry, routing, validation, and execution functions.
- Agents-as-tools can separate Main Agent, Skillsmith, Validator, and Librarian roles.
- Handoffs can delegate from the Main Agent to Skillsmith or Validator.
- Dynamic tool filtering can expose only safe or relevant tools for a given agent state.
- Guardrails can enforce skill request schema, approval gates, and unsafe operation blocks.
- Tracing and sessions can provide the visible run history needed for debugging and demos.

This documentation treats those as implementation options, not hard commitments.
