# V1.0 Release Tasking

Status: complete for v1.0 local CLI release

This is the working tasking list for getting Skill-Seeking Agent to v1.0. It should guide current building after the candidate-decision slice. V1.0 means a stable local CLI product for governed skill acquisition, not a hosted platform, production agent framework, marketplace, or true sandbox.

Context7 release note: current Python Semantic Release guidance treats `pyproject.toml:project.version` as the version stamp and supports changelog/release-note generation from release history. For this repo, moving to `1.0.0` should be a deliberate compatibility promise over stable CLI commands, JSON contracts, lifecycle states, eval meanings, and safety boundaries.

## V1.0 Target

V1.0 should mean:

```text
A local operator can rely on the CLI to identify capability gaps, validate temporary skills, preserve evidence, ask for human decisions, and admit or route skills only through explicit reviewed paths.
```

V1.0 does not mean:

- production-safe hosted agent framework;
- external skill marketplace;
- true sandboxing unless actually implemented and tested;
- autonomous promotion from temporary output to durable skills;
- automatic stable routing without human approval evidence;
- permission widening without explicit review.

## Tasking List

### 1. Ship Current Decision-Compression Slice

Status: complete as `2397dae feat: add candidate decision summary`

Goal:
Finish the current `candidate-decision` slice and get it reviewed, committed, and pushed.

Tasks:

- Keep `skill-agent candidate-decision <candidate-id>` as the compact operator entrypoint for candidate review.
- Preserve source-backed `why` items and advisory-only mutation flags.
- Run local validation, self-review, CodeRabbit, then commit/push to the private branch.

Checks:

- `candidate-decision` returns `ask_human`, `test_more`, `deny`, or `defer` with source evidence.
- Full repo validation passes.
- CodeRabbit has no blocking findings or any stall is reported with local proof.

### 2. Define The V1.0 Contract

Status: complete in [V1 Contract And Fresh-Checkout Operator Path](plans/v1-contract-and-fresh-checkout-operator-path-2026-06-06.md)

Goal:
Create one release contract that names what v1.0 promises and what it explicitly does not promise.

Tasks:

- Add `docs/v1-release-contract.md`.
- Define stable CLI commands, JSON outputs, lifecycle states, eval meanings, and safety boundaries.
- Define non-goals: hosted mode, marketplace, production safety, true sandboxing, autonomous promotion, active governor steering.
- Name versioning expectations for `pyproject.toml`, changelog, release notes, and tags.

Checks:

- A new operator can read one document and understand what v1.0 promises.
- The contract distinguishes local v1 stability from production safety.
- The contract is consistent with README, roadmap, data contracts, and safety model.

### 3. Fresh-Checkout Operator Path

Status: complete in [V1 Contract And Fresh-Checkout Operator Path](plans/v1-contract-and-fresh-checkout-operator-path-2026-06-06.md)

Goal:
Make the first-run path boring and repeatable from a clean clone.

Tasks:

- Add one canonical v1 smoke helper, such as `scripts/v1_smoke.sh`.
- Cover install, gauntlet/demo execution, eval smoke, and one candidate-decision inspection path.
- Keep the smoke path safe for an empty `runs/` directory.
- Document the exact command in README and the v1 contract.

Checks:

- Fresh checkout can run the canonical path without repo-specific handholding.
- The smoke helper fails loudly and points to the failing command.
- No durable skills are copied or promoted during the smoke path.

### 4. One Complete Human-Governed Promotion Path

Status: complete with managed-prefix-first local use through `skill-agent shadow-managed-write` and the read-only `skill-agent v1-local-use` checklist.

Goal:
Provide one safe local path from temporary candidate evidence to durable local skill admission or an explicitly chosen managed-prefix stable lane.

Tasks:

- Decide whether v1 admits into durable `skills/` or keeps stable use in a managed prefix.
- Require human approval, exact digests, unchanged source hashes, permission checks, and rollback/reversibility evidence.
- Keep candidate evidence separate from stable routing.
- Add tests for success, stale digest, source drift, collision, permission widening, and rollback blockers.

Checks:

- One candidate can move through review into a stable local-use state without mutating unrelated evidence.
- Permission widening remains blocked unless explicitly approved.
- No generated skill can self-promote.

Evidence:

- V1 chooses managed-prefix-first local use, not durable `skills/` admission.
- `shadow-managed-write --no-dry-run` is the only real write surface in this lane, and it is confined to the managed prefix.
- The path requires human promotion review, exact source/durable/shadow/rollback/acceptance/managed-write digests, latest checkpoint hash, and a separate non-expired write approval id.
- `tests/test_shadow_activation.py` covers success, idempotent rerun, stale/mismatched digest and checkpoint blockers, approval blockers, conflicting managed-prefix bytes, symlink escape blocking, rollback/interruption behavior, and no durable skills/registry/ledger/governor mutation.
- `tests/test_v1_local_use.py` keeps the v1-facing operator checklist aligned to that boundary.

### 5. Stable Routing Policy

Status: complete for v1 as deferred/disabled in [Stable Routing Policy](stable-routing-policy.md)

Goal:
Define when a stable skill is eligible for normal routing.

Tasks:

- Add a stable routing policy document and data-contract section.
- Keep candidate, durable admission, and stable routing as separate states.
- Implement routing only after stable-review/admission evidence is proven.
- Add eval rows proving candidates are not routed early and approved stable skills can be routed.

Checks:

- Stable routing cannot activate from candidate status alone.
- Evals prove ready-for-review is still not stable-routed.
- Stable routing is visible in explain/run logs when it is used in a future post-v1 routing workflow.

V1 policy:

- Stable routing is not enabled in v1.
- Stable-readiness remains advisory evidence only.
- Candidate readiness does not authorize stable review, stable promotion, durable `skills/` admission, or normal routing.
- Managed-prefix-first local use through `shadow-managed-write` remains the v1 stable local-use path.
- Positive stable routing is post-v1 work and requires a separate human-approved workflow plus run/run-json/explain visibility.

Evidence:

- `docs/stable-routing-policy.md` defines the v1 deferred policy.
- `evals/v1_release.jsonl` includes `v1_release_stable_routing_policy_deferred_even_when_ready`.
- `tests/test_v1_release_eval.py` requires all stable-readiness rows to keep stable review, promotion, and routing disabled.
- `tests/test_stable_readiness.py` verifies ready-for-review reports keep stable routing disabled and point to a post-v1 workflow.
- `tests/test_v1_local_use.py` and `scripts/v1_smoke.sh` verify `v1-local-use --json` reports `stable_routing_policy=deferred_for_v1`.

### 6. Release Eval Suite

Status: Task 6A complete with `evals/v1_release.jsonl`; future expansion is required only if v1 includes positive stable routing.

Goal:
Create the v1 release gate as a named eval suite.

Tasks:

- Add `evals/v1_release.jsonl`.
- Include happy path, missing capability, unsafe stop, approval required, malicious skill rejection, repair needed, duplicate candidate, negative evidence, durable/stable review, and stable routing cases.
- Add documented thresholds for pass rate, trace completeness, request quality, and unauthorized mutation.
- Wire the suite into `scripts/v1_smoke.sh` so the fresh-checkout path exercises the release gate.

Checks:

- `skill-agent eval --suite evals/v1_release.jsonl` is required before v1 release.
- Failures are categorized into actionable dimensions.
- The suite catches unauthorized promotion, install, routing, or permission widening.
- Current stable-routing coverage proves candidates are not routed early; a positive stable-routing row should be added only if Task 5 includes stable routing in v1.

### 7. Evidence Simplification Pass

Goal:
Make the operator path clear enough that users do not need to understand every report.

Tasks:

- Make `candidate-decision` the default candidate review starting point.
- Ensure it points to deeper reports only when needed.
- Reduce duplicated or conflicting language across `stable-readiness`, `skill-receipt`, `admission-plan`, `evidence-governor`, and docs.

Checks:

- A candidate review can be performed from one top-level command plus linked source reports.
- Docs explain when to use each report.
- New proof surfaces are rejected unless they reduce decision load.

### 8. Safety Boundary Audit

Goal:
Make every write and authority boundary explicit and tested.

Tasks:

- Audit every command that can write to `runs/`, managed prefixes, ledgers, or skills.
- Confirm mutation flags are accurate.
- Confirm scripted skills are described as trusted-local, not sandboxed.
- Add shared no-mutation guardrails where current tests are repetitive or incomplete.

Checks:

- Docs and behavior agree on every mutation boundary.
- No command claims sandboxing without actual isolation.
- Unauthorized durable skill writes, routing, registry mutation, and permission widening are tested.

### 9. Versioned Data Contract Freeze

Status: complete in [V1 Data Contract Freeze](plans/v1-data-contract-freeze-2026-06-06.md)

Goal:
Define v1 JSON and ledger compatibility surfaces.

Tasks:

- Mark v1 public JSON contracts in `docs/contracts/data-contracts.md`.
- Add schema/version notes for run logs, candidate ledgers, input resolutions, checkpoints, decision reports, and eval reports.
- Add representative fixture compatibility tests for v1 outputs.

Checks:

- Breaking a public JSON field becomes a deliberate versioned change.
- Existing v1 fixture outputs remain readable.
- Contract docs match model fields.

Evidence:

- `docs/contracts/data-contracts.md` marks the v1 public JSON contract freeze and schema/version notes.
- `tests/fixtures/v1_contracts/` stores representative v1 payloads for run logs, candidate ledgers, input resolution ledgers, evidence checkpoint ledgers, candidate decision reports, and eval reports.
- `tests/test_v1_fixture_compatibility.py` validates model-backed fixtures with Pydantic v2 and checks the eval report dict envelope.
- `scripts/v1_smoke.sh` runs the fixture compatibility test.

### 10. Release Documentation

Status: complete in [V1 Release Candidate Documentation](plans/v1-release-candidate-docs-2026-06-06.md)

Goal:
Move from research-only docs to local-v1 docs without overstating safety.

Tasks:

- Update README when gates pass from "research prototype only" to "local v1 CLI with explicit boundaries."
- Add `CHANGELOG.md`.
- Add `docs/v1-release-notes.md`.
- Keep positioning focused on governed capability acquisition, not generic agent framework.

Checks:

- A new user can understand what to try, what to trust, and what not to trust.
- Release notes name known limitations clearly.
- Version and changelog are ready for a `1.0.0` tag.

Evidence:

- `README.md` positions the repo as a v1.0 local CLI release for governed capability acquisition.
- `CHANGELOG.md` records an Unreleased release-candidate section without claiming a stamped `1.0.0`.
- `docs/v1-release-notes.md` summarizes current abilities, boundaries, verification commands, and the remaining final gate.
- `tests/test_v1_release_docs.py` keeps release docs honest about local-only scope, no version stamp, no tag, no publish, deferred stable routing, and non-sandboxed scripted skills.
- `scripts/v1_smoke.sh` checks the release docs exist and runs the release-doc regression test.

### 11. Final V1 Gate

Status: complete in [Final V1 Release Gate](plans/v1-final-release-gate-2026-06-06.md)

Goal:
Only stamp and tag `1.0.0` after proof is clean.

Tasks:

- Run the full test suite.
- Run compileall and `git diff --check`.
- Run capgap smoke, capgap v0, lifecycle, diagnostic, and v1 release evals.
- Run fresh-checkout smoke.
- Run CodeRabbit or record an explicit bounded-stall fallback with local proof.
- Update `pyproject.toml` to `1.0.0`, update changelog/release notes, and tag only after gates pass.

Checks:

- Every release gate is green.
- Version, changelog, release notes, and intended tag agree.
- Public docs do not claim production safety, marketplace support, true sandboxing, or autonomous promotion.

## Likely Next Slice

The next slice should be **post-v1 routing/admission planning**.

Reason:
The v1 local CLI release is bounded around governed capability acquisition, managed-prefix-first local use, and deferred stable routing. The next product question is whether post-v1 should add positive stable routing, durable `skills/` admission, or a cleaner operator dashboard over the existing evidence surfaces.
