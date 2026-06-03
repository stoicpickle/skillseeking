# Remote Progress And Input Focus

The Remote Progress and Input Focus layer gives blocked work one shared, read-only contract. It does not add active autonomy. It summarizes what the agent already did, what can still be inspected safely, and what Russ must decide before durable state changes.

## Remote Progress Allowed

The current system may continue to gather and package evidence when the action is read-only or run-scoped:

- route through existing accepted skills,
- create missing-skill requests,
- draft and validate Markdown-only temporary skills,
- load validated temporary skills for one run,
- write immutable run logs,
- update rebuildable Skill Candidate Ledger evidence,
- derive advisory candidate review queues,
- run evals and diagnostics,
- create durable admission dry-run reports.

## Input Required

The system must surface an `InputRequest` when progress reaches a human decision boundary:

- `safety_approval`: the current task needs human approval before execution continues.
- `promotion_approval`: a candidate needs human review before promotion evidence can advance.
- `durable_admission_review`: admission evidence is ready or blocked, but durable install/copy remains human-governed.
- `repair_review`: a generated or candidate skill needs repair, rejection, or deferral.
- `ambiguity_resolution`: duplicate or ambiguous candidate evidence needs a decision.
- `missing_evidence`: required evidence is absent before durable review can continue.

Every input request includes a stable ID, kind, status, title, reason, blocked scope, requested decision, options, evidence refs, and suggested next command.

## Surfaces

- `skill-agent run` prints `INPUT_NEEDED` when the run log contains input requests.
- `skill-agent run --json` includes `input_requests`.
- `skill-agent input-requests --runs-dir runs` scans run logs and candidate ledger evidence into a read-only queue.
- `skill-agent input-requests --json` emits the same queue as JSON, plus source warnings when a ledger cannot be read.
- `skill-agent health` prints `INPUT_FOCUS` counts.
- `skill-agent health --json` includes `input_request_count` and `input_request_kind_counts`.
- `skill-agent explain <run-log.json>` prints the run-local input-needed summary.
- `skill-agent admission-plan` includes an `INPUT_NEEDED` summary when durable review, approval, repair, or missing evidence is the next boundary.

## Never Autonomous

The input-focus layer does not install durable skills, copy generated artifacts into `skills/`, promote stable skills, widen permissions, execute unsafe actions, or let the governor steer execution. Those remain explicit future designs.

## Eval Proof

Eval rows can require input-focus evidence with:

- `must_have_input_request`
- `input_request_kind`
- `input_request_status`

The diagnostic and lifecycle suites assert safety approval, promotion approval, and repair-review input requests so the remote-progress queue cannot silently disappear.
