# Start Here

Status: public-dev-preview first-run path

This is the shortest path for a new local user. It proves the CLI works, shows
the product loop, and stops before any new authority.

## 1. Install

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

## 2. Check The CLI

```bash
.venv/bin/python scripts/cli_doctor.py
```

Expected result:

```text
CLI DOCTOR
Status: passed
Issues: 0
```

## 3. Run The Launch Demo

```bash
bash scripts/run_launch_demo.sh --keep-workspace
```

The demo uses a temporary copy of `skills/`. It does not mutate durable
`skills/`, enable stable routing, install dependencies, call a hosted service,
or claim sandboxing.

The demo prints `operator-summary` before candidate-specific proof. That is the
intended inspection order for new users.

At the end, the script also prints a command like this:

```bash
.venv/bin/skill-agent operator-summary --runs-dir <demo-workspace>/runs
```

Run that command again if you want to inspect the saved evidence. `operator-summary`
is the front door: it tells you what happened, what needs review, and which
existing command to run for supporting proof.

## 4. Stop At The Human Decision

For the launch demo, the expected answer is:

```text
Keep the candidate review-only until a human gathers more evidence or records
approval.
```

Candidate evidence is not durable admission. A temporary skill that worked once
is not a permanent skill. Stable routing remains disabled.

## 5. Full Release Gate

Run the full local release-style check when changing behavior:

```bash
bash scripts/v1_smoke.sh
```

## What This Is Not

- Not a hosted service.
- Not production-safe.
- Not a marketplace.
- Not a true sandbox.
- Not autonomous skill promotion.
- Not durable generated-skill admission into `skills/`.
- Not positive stable routing.
- Not active governor steering.
