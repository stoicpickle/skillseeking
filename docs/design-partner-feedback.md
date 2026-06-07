# Design Partner Feedback

Status: public-dev-preview feedback runbook

This runbook is for learning from 3 to 5 design partners who can try the local
CLI on contained workflows with real capability gaps and review pressure. It is
not a sales launch, hosted beta, production service, marketplace program, true
sandbox, or autonomous promotion path.

## Target Partners

Good early partners are local operators who:

- can run a Python CLI locally;
- have a contained workflow where missing capabilities are easy to notice;
- care about human review before skill admission, permission widening, or stable
  routing;
- are willing to report confusion instead of only feature requests.

Avoid workflows that require untrusted scripted skills, production secrets,
hosted deployment, marketplace distribution, or irreversible writes.

## Session Path

Use one short path for each partner:

1. Install the repo locally.
2. Read [Operator Summary Review Pack](operator-summary-review-pack.md).
3. Run `bash scripts/run_launch_demo.sh`.
4. Run one contained missing-skill task through `skill-agent` if the launch demo
   is not enough.
5. Inspect `operator-summary` first, then use the run log, `explain`, candidate
   evidence, and `candidate-decision` as supporting proof.
6. Inspect `new-authority-readiness` only as a phase statement: planning-ready,
   enablement-blocked.
7. Record the session in [Design Partner Feedback Log](design-partner-feedback-log.md).
8. Stop before durable generated-skill admission, stable routing, hosted
   deployment, marketplace behavior, or sandbox claims.

The goal is to learn where the governed capability-gap loop is clear or
confusing, not to prove broad production readiness.

## Feedback Template

Use this template for each partner:

```md
## Partner Feedback

- Partner alias:
- Date:
- Workflow type:
- Local environment:
- Setup friction:
- Launch-demo comprehension:
- Operator-summary decision clarity:
- Evidence-surface confusion:
- Candidate-decision confusion:
- Safety-boundary confusion:
- Stable-routing deferral confusion:
- New-authority readiness confusion:
- Most useful proof surface:
- Least useful or most confusing proof surface:
- Desired next action:
- Captured as issue or docs note:
```

## Prioritization Rule

Prioritize repeated confusion from real runs before imagined feature expansion.
The first public users should drive clearer setup, demo framing, evidence
compression, candidate decisions, safety wording, and stable-routing deferral
language before the project adds hosted service behavior, marketplace support,
durable generated-skill admission, or positive stable routing.
