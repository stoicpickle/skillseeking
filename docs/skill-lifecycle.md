# Skill Lifecycle

## Lifecycle States

```text
requested   missing capability has been identified
draft       skill has been created but not validated
temporary   passed minimal validation and can be used for one task from run-scoped artifacts
candidate   passed broader checks and can be reused with caution
stable      repeatedly useful and maintained
deprecated  replaced, stale, or scheduled for retirement
blocked     unsafe, broken, or disallowed
```

## Pipeline

```text
1. Requested
2. Drafted
3. Validated
4. Used temporarily
5. Evaluated
6. Promoted
7. Monitored
8. Repaired
9. Retired
```

## Example Lifecycle

```text
Skill request:
semantic-claim-deduper

Draft:
Created SKILL.md and examples.

Validation:
Passed 8/10 checks.
Failed on negated claims.

Temporary use:
Allowed, but negated or scoped claims are marked low confidence.

Repair:
Added negation examples and a clearer procedure.

Promotion:
Candidate after 5 successful uses.

Retirement:
Merged later into compare-claims v0.4.
```

## Promotion Rules

Draft to temporary:

- The draft lives under `runs/artifacts/<run_id>/skills`, not durable `skills/`.
- Metadata is valid.
- Inputs and outputs are explicit.
- At least one example is present.
- Risk level is declared.
- Validation checks pass.

Temporary to candidate:

- Requires an explicit human promotion workflow; run artifacts are never scanned as durable registry entries by default.
- The first workflow records reviewer and notes approval in the ledger only; it does not copy, install, admit, route, or score a durable skill.
- Used successfully at least once for the initial ledger-candidate slice; later durable admission should raise this to repeated successful use.
- Human correction rate is acceptable.
- No unresolved safety flags, block/quarantine reasons, duplicate flags, validation failures, or repair requirements.
- Failure cases are documented.

Candidate to stable:

- Used successfully at least 10 times.
- Tests or validation examples cover common edge cases.
- No duplicate stable skill exists.
- Owner or maintainer approval is recorded.

Any state to blocked:

- Prompt injection or malicious instructions detected.
- Undeclared network, filesystem, or secret access.
- Repeated output schema failures.
- Repeated user corrections for the same behavior.
- Dependency or environment drift makes the skill unreliable.

## Skill Record Fields

Every skill should track:

- Name.
- Version.
- Description.
- Status.
- Owner.
- Risk level.
- Allowed tools.
- Dependencies.
- Input schema.
- Output schema.
- Test status.
- Usage count.
- Success rate.
- Failure rate.
- Human correction rate.
- Last used.
- Last tested.
- Known limitations.
- Replacement skill, if deprecated.

