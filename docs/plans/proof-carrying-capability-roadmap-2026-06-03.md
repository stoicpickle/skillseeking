# Proof-Carrying Capability Roadmap

Date: 2026-06-03

This plan translates the external deep-research recommendations into repo-local goals for Skill-Seeking Agent. The product direction is to become a proof-carrying personal capability supply chain: durable skills should be admitted only when they carry origin, containment, utility, compatibility, and reversibility proof.

## Product Takeaway

Skill-Seeking Agent should not become a generic agent framework, marketplace, plugin runtime, or eval dashboard. Its strongest lane is governed capability acquisition: the agent can show what capability was missing, what temporary evidence exists, why durable admission is or is not ready, and what human decision is still required.

The most important risk is causal usefulness. A temporary skill that appears in one successful run has not necessarily improved the agent. The next proof surfaces should distinguish:

- presence: the skill existed,
- participation: the skill loaded in a run,
- success: the run completed,
- usefulness: a matched baseline would have failed or performed worse,
- durability readiness: the skill can be activated, rolled back, and constrained without rewriting evidence.

## Goals

| Goal | Status | Why It Matters | First Proof |
| --- | --- | --- | --- |
| Paired utility proof | working | Shows whether a temporary skill changed the outcome versus a matched control | `candidate-usefulness --baseline-run-id --treatment-run-id` read-only comparison |
| Exact admission bundle | working | Prevents approval drift by binding review to exact hashes, source snapshots, permissions, and destination plan | `admit-candidate --dry-run` emits a plan digest and verifies matching append-only approval notes |
| Permission/dependency diff approvals | working | Keeps human approvals sparse and meaningful | `admit-candidate --dry-run` emits semantic permission/tool/dependency diff evidence |
| Counterfactual skill receipt | working | Makes one candidate's proof bundle inspectable before any durable write mode exists | `skill-receipt` aggregates origin, utility, containment, compatibility, approval, and reversibility categories |
| Managed shadow activation | working | Tests real durable activation without arbitrary writes | `shadow-write-gate` verifies prepared run-scoped acceptance evidence, supplied exact digest, source hash, and rollback pointer before any real write mode exists |
| Generation rollback harness | complete | Makes durable admission reversible | `shadow-rollback-plan` verifies existing profile pointer/generation rollback evidence without writing |
| Negative evidence retention | working | Prevents survivor-biased ledgers | `negative-evidence` reports reject/defer/block/repair resolutions plus blocked/repair/duplicate candidate evidence |
| Tamper-evident checkpoints | working | Makes local append-only evidence verifiable later | `evidence-checkpoint` appends or verifies a local hash-chain over core `runs/` evidence |
| Non-steering evidence governor | working | Reduces review cost without granting install authority | `evidence-governor` recommends ask/test_more/deny/defer from existing proof surfaces only |

## Implementation Order

1. **Paired usefulness comparison**
   - Add a read-only baseline/treatment comparison to `candidate-usefulness`.
   - Require pinned run IDs so the evidence is inspectable and replayable.
   - Reject contaminated baselines where the candidate temporary skill loaded.
   - Do not claim statistical lift from one pair.

2. **Plan digest approval contract**
   - Extend durable admission dry-run output with a stable plan digest.
   - Bind approval evidence to candidate ID, source hash, destination plan, collision policy, permission approval, reviewer, and expiry.
   - Keep `--no-dry-run` rejected.
   - Current proof: dry-run preview computes a stable `sha256` plan digest and accepts only resolved `approve_review` evidence whose notes include matching `plan_digest=<digest>` and a non-expired `expires_at=<timestamp>`.

3. **Permission and dependency diff packet**
   - Show semantic permission classes and exact dependency realization before admission.
   - Block unpinned or unhashed dependency changes at the durable boundary.
   - Keep denial graceful and advisory until write mode exists.
   - Current proof: dry-run preview reports added permission classes, added tools, dependency declaration keys, whether exact realization exists, unresolved dependency names, and blockers for missing realization or unsupported dependency install.

4. **Counterfactual skill receipt**
   - Add a read-only CLI receipt for one candidate.
   - Aggregate existing proof surfaces instead of creating a new promotion path.
   - Keep missing promotion approval, exact plan approval, and rollback support visible as missing, blocked, or partial proof.
   - Current proof: `skill-receipt` nests candidate usefulness and durable admission preview evidence, classifies proof categories, and preserves no-mutation flags.

5. **Managed shadow activation design**
   - Design content-addressed installation under a managed prefix only.
   - Activation should be a pointer/generation switch, not direct overwrite.
   - Collision policies start as fail/shadow/adopt, with replace deferred.
   - Current proof: `shadow-activation-plan` computes a content-addressed store path, profile generation, activation pointer, previous generation, rollback target, and shadow plan digest without creating files or switching profiles.
   - Current acceptance proof: `shadow-activation-acceptance --prepare-acceptance-evidence` writes only run-scoped acceptance evidence, copies the source into an acceptance store/generation, simulates pointer switching, restores rollback, recovers an acceptance pointer left on the planned generation, blocks conflicting acceptance evidence, and leaves durable skills plus the real managed prefix untouched.
   - Current gate proof: `shadow-write-gate` is read-only and verifies the prepared acceptance store/generation copies, unchanged source hash, restored rollback pointer, rollback marker, rollback plan, and supplied exact acceptance digest before any future human-approved managed-prefix write mode.

6. **Rollback and negative evidence**
   - Current rollback proof: `skill-agent shadow-rollback-plan` reads an existing activation pointer and generation directory, reports current/planned/rollback generations plus rollback digest, and blocks when rollback evidence is missing, without creating generations or switching profiles.
   - Current proof: `skill-agent negative-evidence` reads existing candidate and input-request resolution ledgers to report unfavorable or limiting evidence without rewriting history.
   - Preserve failed approval, regression, collision, source drift, and rollback evidence.
   - Add tests that deliberate failed admissions remain visible and do not rewrite history.

7. **Checkpointed evidence**
   - Add local verification of append-only evidence after the admission ledger shape is stable.
   - Start with hash-chain or signed segment checkpoints, not public transparency infrastructure.
   - Current proof: `skill-agent evidence-checkpoint` dry-runs the next local checkpoint, `--no-dry-run` appends one record to `runs/evidence_checkpoints.json`, and `--verify` detects checkpoint-chain tampering or current evidence drift without rewriting run logs, candidate ledgers, resolution ledgers, durable skills, registry, or governor behavior.

8. **Narrow evidence governor**
   - Only after the above, allow a governor to recommend ask/test_more/deny/defer.
   - It must not grant approval, install, promote, widen permissions, or steer execution.
   - Current proof: `skill-agent evidence-governor` composes skill receipts, negative evidence, and checkpoint verification into deterministic ask/test_more/deny/defer recommendations while explicitly keeping approval, install, promotion, permission widening, routing, and active steering disabled.

## Non-Goals

- No remote skill marketplace.
- No arbitrary durable copy/install writes.
- No auto-promotion from temporary success.
- No learned reward governor for promotion decisions.
- No broad planner/router rewrite.
- No full public transparency service.
- No claim that provenance proves trust or safety.

## Review Questions

- Does the slice improve one proof category without widening autonomy?
- Are historical run logs, candidate ledgers, and resolution ledgers preserved?
- Can a human inspect the exact source, destination, approval, and evidence references?
- Does the slice retain negative evidence rather than filtering for successes?
- Is the proof replayable from existing run logs or explicitly retained snapshots?
- Does the wording avoid claiming stable/durable skill install capability before it exists?

## Current Slice

The current implementation target is the non-steering evidence governor. It summarizes existing proof surfaces into an advisory recommendation only. It does not approve durable admission, enable install/copy behavior, promote candidates, widen permissions, route work, or steer execution.
