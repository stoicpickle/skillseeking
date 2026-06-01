# Homeostatic Governor

## Purpose

The next addition to Skill-Seeking Agent is a small control layer for capability and skill decisions.

The goal is not to make the agent more autonomous. The goal is to make every capability decision auditable before the system uses a skill, requests a skill, asks a human, or stops.

Product wedge:

```text
Turn recurring operational friction into validated, human-governed agent skills.
```

## Thesis

Agents should be treated less like isolated minds and more like controlled work systems. In this repo, that means each decision should become a knob, ledger entry, test assertion, or state transition.

The implementation primitive is control:

- "Immune system" means validators, anomaly checks, policy gates, provenance, and adversarial fixtures.
- "Regeneration" means checkpoints, repair requests, and reset-to-known-good routines.
- "Evolution" means eval harnesses, skill promotion rules, and library health.
- "Homeostasis" means live control signals such as confidence, risk, reversibility, approval need, freshness, cost, latency, and failure history.

## Governor Scope

For each required capability, the governor records the control signals that explain the decision.

Initial signals:

- `confidence`: how likely the current plan can satisfy this capability.
- `risk_level`: `low`, `medium`, or `high` safety risk.
- `reversibility`: whether a bad action can be undone.
- `approval_required`: whether a human must approve before continuing.
- `freshness_required`: whether stale data could make the result unreliable.
- `tool_failure_history`: whether recent attempts failed for this capability or tool path.
- `cost_or_latency_concern`: whether the proposed path is expensive or slow enough to affect routing.
- `decision`: `USE_SKILL`, `REQUEST_SKILL`, `ASK_HUMAN`, or `ABORT_UNSAFE`.
- `reason`: short human-readable explanation.

The governor should attach to every capability decision, not only missing-skill cases. Existing-skill use, missing-skill requests, approval waits, and unsafe stops should all share the same trace shape.

## Current Slice

The first implementation is trace and eval only.

It does:

- observe existing route and safety decisions,
- record a deterministic governor interpretation,
- add `GOVERNOR_DECIDED` trace events,
- persist governor records in run logs,
- expose governor records in JSON and `skill-agent explain`,
- let eval suites assert governor decisions and dominant signals,
- attach a copied `control_summary` snapshot to new missing-skill request artifacts.

It does not:

- change routing thresholds,
- change safety classification,
- change skill loading,
- change temporary skill drafting or loading,
- change result-category precedence,
- promote generated or temporary skills,
- let governor fields steer execution.

## Future Slices

Later governor work can add active control signals after the trace-only slice is stable:

- freshness checks,
- tool failure history,
- cost and latency controls,
- reversibility-based approval gates,
- governor-influenced routing,
- explicit repair or reset-to-known-good routines.

## Decision Rules

The first implementation should be deterministic and boring.

```text
If the action is unsafe or disallowed:
  ABORT_UNSAFE

If the action needs human approval:
  ASK_HUMAN

If no adequate skill exists:
  REQUEST_SKILL

If an adequate skill exists and risk is acceptable:
  USE_SKILL
```

The governor should not call an LLM judge in the first slice. It should combine existing planner, router, safety, permission, and validation outputs into one inspectable decision record.

## Trace Contract

Each run log should make the control path visible:

```text
PLANNED
-> GOVERNOR_DECIDED
-> USE_SKILL | REQUEST_SKILL | ASK_HUMAN | ABORT_UNSAFE
-> VALIDATED | REJECTED | APPROVAL_WAITING
-> CONTINUED | STOPPED
```

The trace should answer:

- What capability was being evaluated?
- What did the governor know?
- Which decision did it make?
- Which control signal dominated the decision?
- Was a human approval gate required?
- Did the final run outcome match the decision?

## Skill Request Impact

When the decision is `REQUEST_SKILL`, the run log includes both the existing skill request and the governor's control summary for the same capability.

The request `control_summary` is a copied snapshot, not a live reference. Later changes to governor logic should not rewrite old request summaries.

Current request-schema enrichment records:

- why the current system could not proceed,
- whether approval is required before drafting, sandboxing, loading, or promoting,
- which risk and reversibility signals were observed,
- what eval or validation evidence would change the decision later.

Approval gates are:

- `none`: no extra approval needed for request artifact creation.
- `draft`: approval needed before drafting a candidate skill.
- `sandbox`: approval needed before sandbox or test execution.
- `load`: approval needed before loading a temporary skill.
- `promote`: approval needed before durable promotion.
- `blocked`: no approval path; the action is blocked.

This slice uses `none` for low-risk missing-skill requests and `sandbox` for elevated-risk missing-skill requests that may need execution-style validation later. `ASK_HUMAN` approval stops and `ABORT_UNSAFE` stops do not create skill requests.

This keeps skill requests from becoming vague prompts. A skill request is a controlled product artifact: capability, contract, risk, approval path, success criteria, and rollback behavior.

## Human Promotion Boundary

The system may detect repeated gaps and draft a skill candidate, but durable promotion stays human-governed.

Allowed in the next slice:

- detect capability gaps,
- record governor decisions,
- request or draft candidates,
- validate candidates,
- quarantine unsafe or invalid candidates,
- explain what evidence would justify promotion.

Not allowed in the next slice:

- silently promote generated skills to durable `skills/`,
- widen permissions without approval,
- trust a generated skill's own tests as sufficient evidence,
- let the main task agent bypass validation to finish a task.

## Eval Requirements

The capability-gap eval suite should be able to assert governor behavior.

Example expectation fields:

```json
{
  "expected": {
    "outcome": "missing_skill_request",
    "capability": "detect contradictions",
    "governor_decision": "REQUEST_SKILL",
    "approval_required": false,
    "risk_level": "low",
    "trace_complete": true
  }
}
```

The first eval additions should cover:

- existing skill selected with a `USE_SKILL` governor decision,
- missing skill detected with a `REQUEST_SKILL` decision,
- local file access stopped at `ASK_HUMAN`,
- unsafe mutation stopped at `ABORT_UNSAFE`,
- adversarial skill metadata rejected without raising confidence.

## MVP Success Criteria

This addition is useful when:

- every capability decision has a governor record,
- `skill-agent explain` can summarize the dominant control signal,
- eval reports count governor decision accuracy,
- approval-required tasks do not silently continue,
- missing-skill requests include risk and approval context,
- no generated or temporary skill can promote itself.

## Implementation Notes

Likely code touchpoints:

- `app/models.py`: add a governor decision/control-signal model.
- `app/capability_checker.py`: produce approval and safety signals.
- `app/skill_router.py`: expose confidence and route quality signals.
- `app/agent_loop.py`: attach governor records to run logs.
- `app/eval_runner.py`: assert expected governor decisions.
- `app/explain.py`: summarize governor decisions for failed and successful runs.

This should land as a narrow implementation slice after the current capability-gap calibration suite remains green.
