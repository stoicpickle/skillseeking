# Safety Model

## Principle

A generated skill is untrusted until validated. A generated executable skill is untrusted even after it is useful.

Skill metadata is data, not instruction.

## Risk Levels

Risk level is safety risk, not task complexity. For example, a Markdown-only contradiction-detection procedure is low safety risk even if the reasoning procedure is medium complexity.

### Low

Examples:

- Read-only text transformation.
- Formatting.
- Local summarization.
- Markdown-only procedures.

Default action:

- No approval required if validation passes.

### Medium

Examples:

- Generated temporary code.
- Local file reads.
- New dependencies.
- External API calls without sensitive data.

Default action:

- Soft approval required.
- Runtime restrictions required.

### High

Examples:

- File deletion.
- Writing outside sandbox.
- Network access to production systems.
- Secrets.
- Payments.
- Emails or messages sent to others.
- Deployment or production mutation.

Default action:

- Hard approval required.
- Audit log required.
- Prefer refusal or human takeover.

## Approval Gates

No approval:

- Read-only Markdown skills.
- Formatting skills.
- Local non-network scripts on sandboxed files.

Soft approval:

- Generated temporary code.
- New dependencies.
- External APIs.

Hard approval:

- File deletion.
- Writing outside sandbox.
- Network access.
- Secrets.
- Payments.
- Emails or messages sent to others.
- Production systems.

## Skill Admission Checks

Every skill must pass:

- Metadata schema validation.
- Name and path validation.
- Risk declaration.
- Allowed tools declaration.
- Input and output contract check.
- Suspicious instruction scan.
- Dependency declaration check.
- Validation example check.

## Scripted Skill Restrictions

Scripted skills are opt-in restricted local subprocesses, not a true sandbox. Current hardening provides:

- Skill-directory entrypoint containment.
- Sanitized environment with no secrets by default.
- No network permission by manifest policy.
- Timeout.
- Capped stdout/stderr and capped pytest validation output.
- JSON stdout parsing on successful return.
- Output-schema validation.
- Failure categories for timeout, nonzero exit, invalid JSON, schema mismatch, and oversized output.

Real sandboxing, memory limits, dependency isolation, and external service controls are out of scope for v0.

## Supply-Chain Concerns

Skills should be treated like packages, not notes.

Risks:

- Malicious natural-language descriptions that manipulate retrieval.
- Instructions that try to override system policy.
- Hidden dependency behavior.
- Interface drift.
- Tool permission expansion.
- Duplicate skills with misleading names.

Mitigations:

- Prefer locally trusted skills.
- Quarantine external skills.
- Validate metadata separately from prose instructions.
- Use schema matching and behavior history, not semantic match alone.
- Require approval for new permissions.
- Keep promotion manual or policy-gated.

## v0 Routing Defenses

For the Markdown-only MVP:

- Allow only local skills.
- Require strict YAML frontmatter.
- Ignore routing instructions inside Markdown bodies.
- Run a suspicious-text scanner.
- Require declared permissions.
- Default all permissions to false.
- Load only trusted registry records or current-run temporary overlays.
- Emit a visible trace of why a skill was selected.
- Preserve ranked routing candidates and scoring explanations in JSON/run logs.

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

## Non-Goals

The system should not:

- Silently promote generated skills to stable.
- Expose secrets to skills by default.
- Install dependencies without approval.
- Treat skill prose as trusted authority.
- Let the main task agent bypass validation to unblock itself.
