# CLI Reference

This is the compact command map for the local `skill-agent` CLI. Install the package first:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Use `.venv/bin/skill-agent --help` for Typer's generated command help.

## Core Commands

- `skill-agent registry`: list local skills.
- `skill-agent run "<task>"`: run a local task against the durable skill registry.
- `skill-agent run "<task>" --allow-skill-generation`: allow a run-scoped temporary Markdown skill when the agent is blocked.
- `skill-agent explain --run-log <path>`: explain a JSON run log.
- `skill-agent eval --suite <path>`: run an eval suite and write reports.

## Candidate Evidence

- `skill-agent candidates`: list candidate ledger records.
- `skill-agent candidate-decision <candidate-id>`: summarize the next human decision for a candidate.
- `skill-agent candidate-usefulness <candidate-id>`: report candidate usefulness evidence.
- `skill-agent skill-receipt <candidate-id>`: show source and validation receipts.
- `skill-agent negative-evidence <candidate-id>`: show blocked or rejected evidence.
- `skill-agent evidence-checkpoint --runs-dir <runs-dir> --verify`: verify evidence checkpoints.
- `skill-agent evidence-governor <candidate-id>`: produce a read-only recommendation report.

## Human-Approved Local Writes

- `skill-agent admit-candidate <candidate-id> --dry-run`: preview durable admission evidence.
- `skill-agent shadow-activation-plan <candidate-id>`: build a shadow activation plan.
- `skill-agent shadow-rollback-plan <candidate-id>`: build rollback proof.
- `skill-agent shadow-write-gate <candidate-id>`: verify the write gate.
- `skill-agent shadow-managed-write <candidate-id>`: perform the managed-prefix local-use lane when every expected digest and approval is supplied.

## Reviewer Feedback

- `skill-agent feedback-session-template`: print the read-only reviewer feedback template.
- `skill-agent feedback-session-append --feedback-log docs/reviewer-feedback-log.md --partner-alias <alias> --date <YYYY-MM-DD> --dry-run`: preview a feedback-log append.
- `skill-agent feedback-log-summary --feedback-log docs/reviewer-feedback-log.md`: summarize recorded feedback sessions.

## Release And Boundary Checks

- `skill-agent v1-local-use`: print the managed-prefix local-use checklist.
- `skill-agent new-authority-readiness`: report why planning is ready but new authority remains disabled.
- `python scripts/cli_doctor.py`: smoke the representative CLI surface.
- `bash scripts/v1_smoke.sh`: run the v1 release smoke gate.
- `python scripts/security_check.py`: run Bandit, pip-audit, and detect-secrets.
