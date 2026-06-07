# Operator Summary Review Pack

Status: public-dev-preview design-partner review pack

This pack is the shortest review path for a technical design partner. It uses
`operator-summary` as the front door after the launch demo so the reviewer sees
the next operator decision before digging into raw ledgers.

This is a local CLI review path. It is not a hosted service, production safety
claim, marketplace, true sandbox, autonomous promotion path, durable generated
skill admission path, positive stable-routing path, or active governor steering
path.

## One Short Path

Install or use an existing editable install:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Run the launch demo:

```bash
bash scripts/run_launch_demo.sh
```

For an interactive design-partner session, keep the demo workspace path printed
by the script and inspect the run evidence:

```bash
.venv/bin/skill-agent operator-summary --runs-dir <demo-workspace>/runs
.venv/bin/skill-agent explain <demo-workspace>/runs/run_<timestamp>_<run-id>.json
.venv/bin/skill-agent candidate-decision candidate_<id> --runs-dir <demo-workspace>/runs --skills-dir <demo-workspace>/skills
```

`operator-summary` should be the first inspection command. `explain` and
`candidate-decision` are supporting evidence when the reviewer wants the trace
or candidate-specific proof.

## Expected Operator Summary Shape

The exact IDs and paths vary by run. The stable review landmarks are:

```text
OPERATOR_SUMMARY
Advisory only: true
OPERATOR_DECISIONS
- review_candidate_promotion_evidence
  Primary command: skill-agent candidates --runs-dir <demo-workspace>/runs
MUTATION_BOUNDARY
Run logs mutated: false
Candidate ledger mutated: false
Resolution ledger mutated: false
Checkpoint ledger mutated: false
Durable skills mutated: false
Registry mutated: false
Governor steering enabled: false
```

If blockers, missing evidence, unsafe evidence, or checkpoint problems exist,
`OPERATOR_DECISIONS` should put those before candidate promotion review. The raw
sections remain below the decision summary for auditability.

## Operator Decision

The review pack should end on one decision:

```text
Should this candidate remain review-only while the operator gathers more
evidence or records human approval?
```

The expected answer for the launch demo is yes. Candidate evidence means
review evidence, not admission. A temporary skill that succeeded in one run is
not a durable skill, not stable routing, and not approval to widen permissions.

## Evidence Map

- Run log: immutable task trace and capability decisions under the run
  directory.
- Candidate ledger: repeated demand, temporary validation/use evidence, and
  candidate review state.
- Input request / resolution ledger: append-only human decision evidence for
  safety, repair, promotion, and durable review blockers.
- `operator-summary`: first inspection command; compresses local evidence into
  prioritized operator decisions.
- `candidate-decision`: supporting per-candidate proof and next command.
- `skill-agent explain`: supporting trace view for one run log.
- `scripts/v1_smoke.sh`: release gate and no-mutation proof for durable
  `skills/` and stable-routing policy docs.

## What Does Not Happen

- No durable generated-skill admission into `skills/`.
- No positive stable routing.
- No hosted service behavior.
- No marketplace behavior.
- No true sandbox claim.
- No autonomous promotion.
- No active governor steering.
- No permission widening without explicit review.

## Feedback Prompts

Ask the reviewer:

- Could you identify the next operator decision from `OPERATOR_DECISIONS`?
- Did any label make candidate evidence sound like admission?
- Did the mutation boundary make the no-write promise clear?
- Which raw evidence section was necessary after `operator-summary`?
- Which command would you run next, and why?
