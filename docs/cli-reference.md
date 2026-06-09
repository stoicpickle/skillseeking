# CLI Reference

This is the compact command map for the local `skill-agent` CLI. Install the package first:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

Use `.venv/bin/skill-agent --help` for Typer's generated command help. The
top-level help intentionally groups the full command surface into operator-path
panels so reviewers do not have to scan a flat command list.

## Recommended Reviewer Path

1. `skill-agent banner`: confirm the local CLI identity and no-hidden-authority promise.
2. `skill-agent run "<task>"`: create fresh run evidence against local skills.
3. `skill-agent operator-summary --runs-dir <runs-dir>`: inspect prioritized operator decisions first.
4. `skill-agent candidate-decision <candidate-id>` or `skill-agent explain <run-log>`: drill into candidate-specific or run-specific proof only when needed.
5. `skill-agent feedback-session-template` / `feedback-session-append`: capture design-partner feedback without granting authority.

## Start Here

- `skill-agent banner`: print the compact human-facing CLI banner.
- `skill-agent v1-local-use`: print the managed-prefix local-use checklist.
- `skill-agent new-authority-readiness`: explain why new-authority planning is ready while enablement remains disabled.
- `skill-agent operator-summary`: show prioritized operator decisions before raw evidence sections.

## Core Task Loop

- `skill-agent registry`: list local skills.
- `skill-agent run "<task>"`: run a local task against the durable skill registry.
- `skill-agent run "<task>" --temporary-skills`: allow a run-scoped temporary Markdown skill when the agent is blocked.

## Eval And Diagnostics

- `skill-agent explain <run-log>`: explain a JSON run log.
- `skill-agent eval --suite <path>`: run an eval suite and write reports.

## Candidate Evidence

- `skill-agent candidates`: list candidate ledger records.
- `skill-agent candidate-decision <candidate-id>`: summarize the next human decision for a candidate.
- `skill-agent candidate-usefulness <candidate-id>`: report candidate usefulness evidence.
- `skill-agent skill-receipt <candidate-id>`: show source and validation receipts.
- `skill-agent stable-readiness <candidate-id>`: review candidate-to-stable evidence while keeping stable routing disabled.
- `skill-agent negative-evidence <candidate-id>`: show blocked or rejected evidence.
- `skill-agent evidence-checkpoint --runs-dir <runs-dir> --verify`: verify evidence checkpoints.
- `skill-agent evidence-governor <candidate-id>`: produce a read-only recommendation report.
- `skill-agent admission-plan <candidate-id>`: inspect durable-admission readiness without copying or installing skills.

## Human Input And Approvals

- `skill-agent input-requests`: list active human input requests.
- `skill-agent resolve-input-request <input-request-id>`: dry-run or append an input-request resolution.
- `skill-agent promote-candidate <candidate-id>`: record human approval for candidate status without durable admission.
- `skill-agent admit-candidate <candidate-id> --dry-run`: preview durable admission evidence; write mode remains intentionally unavailable.

## Managed-Prefix Local Writes

- `skill-agent shadow-activation-plan <candidate-id>`: build a shadow activation plan.
- `skill-agent shadow-rollback-plan <candidate-id>`: build rollback proof.
- `skill-agent shadow-activation-acceptance <candidate-id>`: exercise activation mechanics inside a run-scoped acceptance prefix.
- `skill-agent shadow-write-gate <candidate-id>`: verify the write gate.
- `skill-agent shadow-managed-write <candidate-id>`: perform the managed-prefix local-use lane when every expected digest and approval is supplied.

## Operator Decision Review And Reviewer Feedback

- `skill-agent health`: summarize local skill library, run evidence, input focus, and candidate queues.
- `skill-agent candidate-decision <candidate-id>`: compress candidate evidence into one advisory next human decision.
- `skill-agent feedback-session-template`: print the read-only reviewer feedback template.
- `skill-agent feedback-session-append --feedback-log docs/reviewer-feedback-log.md --partner-alias <alias> --date <YYYY-MM-DD> --dry-run`: preview a feedback-log append.
- `skill-agent feedback-log-summary --feedback-log docs/reviewer-feedback-log.md`: summarize recorded feedback sessions.

## Release And Boundary Checks

- `skill-agent v1-local-use`: print the managed-prefix local-use checklist.
- `skill-agent new-authority-readiness`: report why planning is ready but new authority remains disabled.
- `python scripts/cli_doctor.py`: smoke the representative CLI surface.
- `bash scripts/v1_smoke.sh`: run the v1 release smoke gate.
- `python scripts/security_check.py`: run Bandit, pip-audit, and detect-secrets.
