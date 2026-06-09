# Launch Demo Transcript

Status: local public-dev-preview demo

The launch demo is the shortest path through the product wedge: the agent notices a missing capability, requests the skill it needs, validates a temporary Markdown skill for one run, records candidate evidence, and stops with human review and stable routing boundaries still intact.

Run it after local setup:

```bash
.venv/bin/python -m pip install -e '.[dev]'
bash scripts/run_launch_demo.sh --keep-workspace
```

## Expected Flow

The demo runs this local task in an isolated temporary copy of `skills/`:

```text
Cluster arguments from these sources.
```

Expected landmarks:

```text
LAUNCH DEMO
BLOCKED_MISSING_SKILL
REQUESTING_SKILL
DRAFTING_TEMP_SKILL
VALIDATION_PASSED
LOADING_TEMP_SKILL
ROUTE_COMPLETE
OPERATOR_SUMMARY
OPERATOR_DECISIONS
Candidate decision
Durable skills mutated: no
Stable routing enabled: no
Hosted service used: no
Sandbox provided: no
```

## What It Proves

- The local CLI can identify a low-risk missing capability.
- The CLI emits a structured skill request instead of pretending the capability exists.
- A temporary Markdown skill can be drafted, validated, loaded, and used for the current run.
- `operator-summary` is the first inspection surface after the run.
- Candidate evidence is available for `skill-agent candidate-decision` as supporting proof.
- Human review remains in the path before stable local use.
- Durable `skills/` admission remains disabled.
- Stable routing remains disabled.

## What It Does Not Prove

- It is not a hosted service.
- It is not production-safe.
- It is not a marketplace.
- It is not a sandbox and does not provide a sandbox.
- It does not run untrusted scripted skills.
- It does not copy generated skills into durable `skills/`.
- It does not autonomously promote candidates.
- It does not enable positive stable routing.

For the broader mixed-pressure showcase, run the Skill Gauntlet in `scripts/run_gauntlet_demo.py`. For the full release gate, run `bash scripts/v1_smoke.sh`.
