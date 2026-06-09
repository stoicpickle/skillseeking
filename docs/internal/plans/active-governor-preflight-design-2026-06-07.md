# Active Governor Preflight Design

Status: design only

This design names the evidence required before the governor can move from
advisory reporting toward any active behavior. It does not implement active
steering.

## Product Question

What would have to be true before a governor signal can influence execution
instead of only explaining it?

Answer for this design: the repo needs reversible, narrow, human-reviewable
control gates with eval proof before any governor signal can block, authorize,
route, promote, install, widen permissions, or change dependencies.

## Definitions

- Advisory: a report or trace explains current evidence and recommends a next
  action. It cannot change execution.
- Blocking: a future control may stop a narrow action when evidence is missing
  or unsafe. Blocking must be visible in run logs, explain output, eval reports,
  and `operator-summary`.
- Authorizing: a future control may allow a previously blocked action only when
  exact human approval and evidence digests match. Authorization is not planned
  for the next implementation slice.

## Current Boundary

Current governor surfaces are advisory or trace-only:

- capability governor decisions in run logs;
- `skill-agent evidence-governor` recommendations;
- `operator-summary` decision compression;
- eval assertions over governor decisions.

They must not steer routing, promotion, durable admission, dependency
installation, permission widening, managed-prefix writes, stable routing, or
marketplace behavior.

## Smallest Reversible Future Behavior

The first active-governor candidate should be a reversible blocker, not an
authorizer:

```text
If evidence checkpoint verification fails, block a future positive stable
routing attempt and emit a visible governor blocker.
```

This is intentionally narrower than changing route scoring. It can be tested
without granting new skill authority, and it has an obvious operator repair
command: `skill-agent evidence-checkpoint --runs-dir <runs-dir> --verify`.

## Required Gates Before Any Active Slice

- Existing advisory reports stay green and read-only.
- `operator-summary` exposes the blocker and primary repair command.
- Run logs and `skill-agent explain` show the governor signal and final result.
- Eval rows prove both allowed and blocked paths.
- Human override and revoke records are append-only, digest-bound, and expiring.
- The behavior is disabled by default until the active slice is explicitly
  enabled and documented.
- Stable routing, durable admission, permission widening, dependency install,
  and marketplace behavior remain out of scope unless they have their own
  separate reviewed implementation slice.

## Eval Failure Categories To Add Before Rollout

- `governor_blocker_missing`
- `governor_overblocked`
- `governor_authorized_without_approval`
- `checkpoint_mismatch_not_blocked`
- `override_digest_mismatch`
- `override_expired`
- `route_visibility_missing`

## Human Override And Revoke

A future override must name:

- reviewer;
- reason;
- candidate or route target;
- exact evidence checkpoint hash;
- exact plan digest, when a plan exists;
- expiry;
- revoke command or reversal path.

Revocation must leave a visible append-only record and make later attempts fail
closed until fresh approval exists.

## Non-Goals

- No code path starts consulting the governor for new authority.
- No routing, promotion, durable admission, permission, dependency, marketplace,
  hosted, or UI behavior changes.
- No broad planner or router rewrite.
- No true sandbox or production safety claim.
