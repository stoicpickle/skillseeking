# Stable Routing Policy

Status: v1 deferred

Stable routing is not enabled for the v1 local CLI release.

The v1 routing policy is:

- `stable-readiness` may report advisory evidence that a candidate is ready for human stable review.
- `candidate-decision` may explain that a candidate is ready for review.
- `shadow-managed-write` may perform a human-approved managed-prefix local-use write.
- None of those surfaces authorize stable review, stable promotion, durable `skills/` admission, or normal routing.
- `stable_routing_enabled` must remain `false` in v1 reports.
- `stable_routing_policy` must remain `stable_routing_unchanged` for managed-prefix writes.

Positive stable routing is post-v1 work. It requires a separate human-approved workflow that proves:

- stable review authorization;
- stable promotion authorization;
- exact evidence and source digests;
- managed-prefix or durable admission state;
- rollback or deactivation proof;
- route visibility in `run`, `run --json`, and `explain`;
- eval coverage for approved stable routing and early-routing blockers.

V1 intentionally chooses managed-prefix-first local use instead of normal stable routing. This keeps generated skill evidence separate from routine task routing until a future routing workflow is explicitly designed, reviewed, and tested.

The current design-only preflight for that future work is
[Candidate-To-Stable And Durable Admission RFC](plans/candidate-to-stable-and-durable-admission-rfc-2026-06-07.md).
It does not enable stable routing.

## Release Gate

Before `1.0.0`, the release gate must prove:

- `bash scripts/v1_smoke.sh` passes.
- `evals/v1_release.jsonl` includes a named stable-routing policy row.
- Stable-readiness eval rows assert `stable_review_authorized=false`.
- Stable-readiness eval rows assert `stable_promotion_authorized=false`.
- Stable-readiness eval rows assert `stable_routing_enabled=false`.
- `skill-agent v1-local-use --json` reports `stable_routing_policy=deferred_for_v1`.

## Non-Goals

This policy does not add:

- a stable route registry;
- automatic stable skill selection;
- candidate-to-stable promotion;
- durable `skills/` admission;
- dependency installation;
- governor steering;
- a production safety claim.
