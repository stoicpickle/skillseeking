# General Public Readiness Tasking

Status: active hardening goal

This tasking list tracks the work to make Skill-Seeking Agent stronger for
broader public use without adding new autonomy. Recommendation 2, design-partner
recruitment and live observation, is intentionally excluded because it requires
real external users.

## Goal

Make the local CLI easier to start, easier to understand, harder to overclaim,
and better covered by real-world evals before any broader public release.

## Implemented In This Goal

### 1. Make First-Run Dead Simple

- Added `skill-agent banner` as a clearer terminal identity surface.
- Added `scripts/cli_doctor.py` for a fast CLI surface check.
- Added [Start Here](start-here.md) as the public-dev-preview first-run path.
- Added `bash scripts/run_launch_demo.sh --keep-workspace` so users can keep
  demo evidence and inspect it.

Proof:

```bash
.venv/bin/python scripts/cli_doctor.py
```

### 3. Make `operator-summary` The Main Front Door

- Updated the launch demo so `operator-summary` appears before
  candidate-specific proof.
- Updated Start Here, the launch transcript, the review pack, and feedback docs
  to point users to `operator-summary` first.

Proof:

```bash
bash scripts/run_launch_demo.sh --keep-workspace
.venv/bin/skill-agent operator-summary --runs-dir <demo-workspace>/runs
```

### 4. Improve Failure Messages

- Added `NEXT_ACTION` guidance to human `skill-agent run` output when a run
  fails or creates review work.
- The next action starts with `operator-summary`, then points to `explain`,
  input requests, candidate evidence, or repair guidance as applicable.
- JSON output remains unchanged.

### 5. Add More Real-World Evals

- Added public-use diagnostic rows for messy conflict wording and
  dependency/file-summary authority gating.
- The diagnostic suite now proves `22/22` rows locally.

Proof:

```bash
.venv/bin/skill-agent eval --suite evals/agent_diagnostic_v0.jsonl --skills-dir skills --runs-dir /tmp/skill-agent-diagnostic-public-use-check
```

### 6. Keep Authority Locked Down

- Added public authority-lock regression tests for:
  - `v1-local-use`;
  - `new-authority-readiness`;
  - feedback template / append / summary surfaces.
- These tests prove public-use polish does not silently grant durable admission,
  stable routing, dependency installation, hosted behavior, marketplace
  behavior, sandbox claims, or active governor steering.

### 7. Package The Public Story Better

- README now points to Start Here.
- README now opens with generated front-of-repo images, badges, and a
  reviewer-first proof table that points to the launch demo, `operator-summary`,
  and the v1 smoke gate.
- Package metadata now includes README, license, classifiers, keywords, and
  public repository URLs.
- Start Here keeps the public story short:
  install, doctor, launch demo, `operator-summary`, stop at the human decision.
- Public docs continue to say local CLI, trusted-local only, not hosted, not
  production-safe, not marketplace, not true sandbox, and not autonomous.

## Excluded

Recommendation 2 is not implemented by code:

```text
Test with 3 to 5 real people.
```

That remains the next user-owned learning loop. The repo now has the first-run
path and feedback capture surfaces needed to support it.

## Release Boundary

This hardening goal must not add:

- durable generated-skill admission into `skills/`;
- positive stable routing;
- dependency installation;
- hosted service behavior;
- marketplace behavior;
- true sandbox claims;
- autonomous promotion;
- active governor steering.

## Validation Bundle

Recommended proof before pushing this goal:

```bash
.venv/bin/python scripts/cli_doctor.py
.venv/bin/python scripts/security_check.py
.venv/bin/python -m pytest -q
bash scripts/v1_smoke.sh
.venv/bin/python -m compileall -q app scripts
git diff --check
```
