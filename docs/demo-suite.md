# Core Demo Suite

M8 defines the four repeatable demos that prove the v0 loop.

Use a fresh temporary copy of the seed skills so the demos do not mutate the
checkout:

```bash
DEMO_DIR=$(mktemp -d)
cp -R skills "$DEMO_DIR/skills"
RUNS_DIR="$DEMO_DIR/runs"
```

For another pass through the suite, create a new `DEMO_DIR`.

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
temporary skill, validate it, load it for the run, and finish with a visible
trace.

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

## 4. Malicious Skill Rejected

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
