# v0 Build Guardrails

## Decision

Build v0 now. Do not block on Deep Research.

The research we already have is enough to avoid the obvious landmines. Deeper research should happen before Phase 3, when skills become executable, external, or reusable across real users.

## v0 Product Claim

The first version should prove this loop:

```text
task
-> plan
-> capability check
-> available skill match
-> missing skill detected
-> skill request created
-> Markdown skill generated or loaded
-> skill validated
-> task resumed
-> trace emitted
```

The trace is the product.

## Interface

Start with CLI/API only.

Example:

```bash
skill-agent run "Compare these two short articles and identify contradictions."
```

The CLI should emit a readable trace, plus structured JSON logs under `runs/`.

## Hard Constraints

v0 is intentionally narrow:

- CLI/API only.
- Markdown-only skills.
- Local skills folder.
- No generated executable code.
- No external skill marketplace.
- No package installs.
- No network access from skills.
- No secrets.
- No filesystem writes outside the project directory.
- No autonomous promotion to stable.
- No self-modifying core agent code.
- No long-term personal memory.

## Seed Skills

Start with 4 or 5 skills:

```text
extract-claims
compare-claims
source-quality-check
write-structured-answer
validate-skill-md
```

Intentionally omit one useful skill, such as:

```text
detect-contradictions
```

The missing skill is how the demo proves the capability-gap loop.

## Demo Cases

v0 must show three traces:

```text
1. Existing-skill task:
   Agent finds the right skills and completes the task.

2. Missing-skill task:
   Agent detects a gap, requests a skill, validates it, and continues.

3. Malicious-skill task:
   Agent rejects a skill with suspicious metadata or unsafe permissions.
```

The third case is mandatory. Without it, the demo proves capability but not judgment.

## Failure Modes to Defend Against

### False Confidence Instead of Skill Request

The agent lacks a capability but pretends it can continue.

Mitigation:

```text
Can I complete this with available skills?
- yes
- yes with uncertainty
- no, missing skill
- no, missing data
- no, unsafe
```

### Skill-Request Spam

The agent asks for a new skill every time the task is slightly unfamiliar.

Mitigation:

```text
Would this skill be useful for at least 3 future task types?
Can an existing skill be adapted instead?
Is this really a missing capability or just task context?
```

### Vague Skill Specs

No skill request is valid unless it includes:

```text
name
missing capability
input schema
output schema
success tests
failure modes
risk level
```

### Wrong Skill Routing

Do not route only by semantic similarity.

Use:

```text
semantic match
input/output schema match
past success rate
risk level
permissions
version freshness
validation status
```

### Skill Technical Debt

Track lifecycle states from the start:

```text
draft
temporary
candidate
stable
deprecated
blocked
```

### Malicious Metadata or Prompt Injection

Treat skill metadata as untrusted data, not instruction.

Minimum v0 defenses:

- Allow only local skills.
- Require strict YAML frontmatter.
- Ignore routing instructions inside Markdown bodies.
- Run a suspicious-text scanner.
- Require declared permissions.
- Default all permissions to false.
- Load only one skill at a time.
- Emit a visible trace of why a skill was selected.

## Routing Red Flags

Reject or quarantine skills containing:

- Hidden instructions.
- Base64 or obfuscated strings.
- "Ignore previous instructions."
- Requests for secrets.
- Network access during the Markdown-only phase.
- Broad permissions.
- Claims of universal applicability.
- Manipulative descriptions like "always use this skill."
- Instructions that modify routing behavior.
- Instructions that mention system prompts.

## Proof Standard

v0 is better than ordinary tool calling only if it wins on tasks where the needed capability is procedural, reusable, and not just a single function call.

The key behavior:

```text
I need a contradiction-detection procedure that distinguishes direct contradiction from scope difference, temporal mismatch, and definitional mismatch.
```

## Deep Research Timing

Do deeper research before:

- Executable generated skills.
- External skill import.
- Shared skills across real users.
- Marketplace or registry behavior.
- Long-term skill promotion.
- Real-world side effects.

Useful later research areas:

- Formal threat model.
- Competitive and prior-art memo.
- Skill registry supply-chain attacks.
- Evals for repeated reliability.
- UX trust patterns for visible agent state.

