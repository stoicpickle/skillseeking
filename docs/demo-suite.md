# Core Demo Suite

M8 defines the repeatable demos that prove the v0 loop.

Use a fresh temporary copy of the seed skills so the demos do not mutate the
checkout:

```bash
DEMO_DIR=$(mktemp -d)
cp -R skills "$DEMO_DIR/skills"
RUNS_DIR="$DEMO_DIR/runs"
```

For another pass through the suite, create a new `DEMO_DIR`.

## Launch Demo

Command:

```bash
bash scripts/run_launch_demo.sh --keep-workspace
```

Expected status: `0`

Expected sections:

```text
LAUNCH DEMO
Capability gap run
Candidate decision
Boundary check
```

Expected landmarks:

```text
BLOCKED_MISSING_SKILL
REQUESTING_SKILL
DRAFTING_TEMP_SKILL
VALIDATION_PASSED
LOADING_TEMP_SKILL
ROUTE_COMPLETE
Durable skills mutated: no
Stable routing enabled: no
Hosted service used: no
Sandbox provided: no
```

Proves:
The local CLI can demonstrate the governed capability-gap loop in one short path without mutating durable `skills/`, using a hosted service, claiming sandboxing, admitting generated skills, or enabling stable routing. See [Launch demo transcript](launch-demo-transcript.md) for the cold-user walkthrough.

Follow-up operator index:

```bash
.venv/bin/skill-agent operator-summary --runs-dir "$RUNS_DIR"
```

Expected sections:

```text
OPERATOR_SUMMARY
OPERATOR_DECISIONS
BLOCKED_ITEMS
HUMAN_INPUT
PROMOTION_READY_CANDIDATES
MISSING_EVIDENCE
UNSAFE_OR_NEGATIVE
CHECKPOINT_CHANGES
MUTATION_BOUNDARY
```

Proves:
The existing evidence surfaces can be compressed into one advisory operator summary with a prioritized `OPERATOR_DECISIONS` front door, without approving, promoting, routing, appending checkpoint evidence, mutating ledgers, mutating durable skills, mutating registries, or steering the governor.

## 1. Existing Skill

Command:

```bash
.venv/bin/skill-agent run "Extract claims from this article and write a structured summary with source-quality notes." --skills-dir "$DEMO_DIR/skills" --runs-dir "$RUNS_DIR"
```

Expected status: `0`

Expected trace landmarks:

```text
PLANNING
CHECKING_SKILLS
LOADING_SKILL
ROUTE_COMPLETE
RESULT
```

Expected output landmarks:

```text
USE_SKILL extract-claims
USE_SKILL source-quality-check
USE_SKILL write-structured-answer
Exit code: 0
```

Proves:
The agent can map a task to existing local skills and load them without making a
skill request.

## 2. Temporary Skill

Command:

```bash
.venv/bin/skill-agent run "Cluster arguments from these sources." --skills-dir "$DEMO_DIR/skills" --runs-dir "$RUNS_DIR"
```

Expected status: `0`

Expected trace landmarks:

```text
PLANNING
CHECKING_SKILLS
BLOCKED_MISSING_SKILL
REQUESTING_SKILL
DRAFTING_TEMP_SKILL
VALIDATION_PASSED
LOADING_TEMP_SKILL
ROUTE_COMPLETE
RESULT
```

Expected output landmarks:

```text
Temporary skill: argument-clustering
Validation passed: True
Loaded: True
Temporary skills: argument-clustering
Exit code: 0
```

Proves:
The agent can identify a low-risk missing capability, draft a Markdown-only
temporary skill under `runs/artifacts/<run_id>/skills`, validate it, load it for the run, and finish with a visible trace without mutating the durable skills library.

## 3. Blocked Skill

Command:

```bash
.venv/bin/skill-agent run "Extract claims from these two sources and identify contradictions." --no-temporary-skills --skills-dir "$DEMO_DIR/skills" --runs-dir "$RUNS_DIR"
```

Expected status: `1`

Expected trace landmarks:

```text
PLANNING
CHECKING_SKILLS
BLOCKED_MISSING_SKILL
REQUESTING_SKILL
ROUTE_COMPLETE
RESULT
```

Expected output landmarks:

```text
REQUEST_SKILL - :: detect contradictions
Missing capability: detect contradictions
Requested skill: detect-contradictions
Exit code: 1
```

Proves:
The agent can stop cleanly and emit a structured skill request when a required
capability is missing and temporary skill creation is disabled.

## 4. Repair Request

Command:

```bash
.venv/bin/skill-agent run "Run local Python analysis on this text." --skills-dir "$DEMO_DIR/skills" --runs-dir "$RUNS_DIR"
```

Expected status: `1`

Expected trace landmarks:

```text
DRAFTING_TEMP_SKILL
VALIDATION_FAILED
REQUESTING_REPAIR
REPAIR_REQUESTED
RESULT
```

Expected output landmarks:

```text
Temporary skill: local-python-analysis
Failure reason: non-scripted skills must be low risk
Result category: repair_requested
```

Proves:
A medium-risk local-code request is not silently downgraded into a Markdown-only temporary skill. The repair demo is intentionally about code-execution risk; contradiction detection remains safety-low even though it can be medium complexity.

## 5. Malicious Skill Rejected

Command:

```bash
.venv/bin/skill-agent registry --skills-dir tests/fixtures/malicious-skills
```

Expected status: `0`

Expected trace landmarks:

```text
n/a: this demo uses registry quarantine output, not a run trace.
```

Expected output landmarks:

```text
safe-research-note
REJECTED
metadata-routing-attack
body-prompt-injection
obfuscated-instruction
secrets-permission-attack
```

Proves:
The registry accepts the safe control fixture and rejects suspicious or unsafe
skills before they can influence routing or loading.

## Skill Gauntlet

Command:

```bash
.venv/bin/python scripts/run_gauntlet_demo.py
```

Shareable terminal proof:

![Skill Gauntlet terminal demo](assets/skill-gauntlet-terminal.svg)

Expected demo sections:

```text
SKILL GAUNTLET
TASK
REGISTRY
TRACE
RESULT
```

Expected output landmarks:

```text
Accepted skills: 3
Rejected skills: 2
LOADING_SKILL extract-claims
LOADING_SKILL source-quality-check
LOADING_SKILL write-structured-answer
DRAFTING_TEMP_SKILL argument-clustering
VALIDATION_PASSED argument-clustering
LOADING_TEMP_SKILL argument-clustering
VALIDATION_FAILED local-python-analysis
REQUESTING_REPAIR local-python-analysis
Safe skills loaded: extract-claims, source-quality-check, write-structured-answer
Temporary skills loaded: argument-clustering
Repair requests: local-python-analysis
Result category: repair_requested
```

Proves:
The agent can survive one mixed-pressure scenario: accepted safe skills are
loaded, malicious fixtures are rejected before routing, one missing low-risk
capability is drafted and loaded temporarily, one medium-risk local-code
capability emits a repair request, and the run log captures the full trail.

Validation:

```bash
.venv/bin/python -m pytest -q tests/test_gauntlet_demo.py
```

## JSON Surfaces

The same contracts are available without human-readable sections:

```bash
.venv/bin/skill-agent run "Cluster arguments from these sources." --json --skills-dir "$DEMO_DIR/skills" --runs-dir "$RUNS_DIR"
.venv/bin/skill-agent registry --json --skills-dir "$DEMO_DIR/skills"
.venv/bin/skill-agent health --json --skills-dir "$DEMO_DIR/skills" --runs-dir "$RUNS_DIR"
```

## Capability-Gap Eval Smoke

Command:

```bash
.venv/bin/skill-agent eval --suite evals/capgap_smoke.jsonl --skills-dir skills --runs-dir runs/evals
```

Expected status: `0`

Expected output landmarks:

```text
EVAL
Total: 4
Passed: 4
Failed: 0
Average request quality:
JSON report:
Markdown summary:
```

Proves:
The agent can be checked as a regression harness, not only a demo: existing skills load, missing skills are requested, unsafe tasks are aborted, approval-sensitive tasks pause for a human, and request quality is scored deterministically.

To inspect a generated run:

```bash
.venv/bin/skill-agent explain "$(ls -t runs/evals/202*/run_*.json | head -1)"
```
