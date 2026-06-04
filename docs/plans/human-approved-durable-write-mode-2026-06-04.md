# Human-Approved Durable Write Mode: Plan

## Goal
Design the first tiny, human-approved real write-mode slice for skill admission. The slice consumes existing receipt, checkpoint, and shadow write-gate evidence; requires exact digest matches; writes only to a managed shadow prefix; proves rollback before and after the write; and does not touch stable skill routing, durable `skills/` admission, or governor authority.

## Background
- Durable admission currently refuses real mutation: `build_durable_admission_preview(..., dry_run=False)` raises `"durable admission mutation is not implemented; rerun with --dry-run"` in `app/durable_admission.py:45`, while CLI help keeps write mode intentionally unavailable in `app/cli.py:902`.
- The current preview pipeline already computes source, target, snapshot, destination-staging paths, collision policy, permission approval, expected hash, and a plan digest. `_plan_digest(...)` binds `candidate_id`, operation, source path/hash, target path, snapshot/stage paths, collision policy, permission/dependency diff, `prepare_write_evidence`, and `expected_source_sha256` in `app/durable_admission.py:620`.
- Run-scoped write evidence exists but does not install: `_snapshot_paths(...)` and `_destination_stage_paths(...)` place retained source and staged destination copies under `runs/admission_snapshots/...` and `runs/admission_staging/...` in `app/durable_admission.py:668` and `app/durable_admission.py:678`.
- `SkillReceiptReport` composes candidate usefulness plus durable admission preview in `app/skill_receipt.py:23`. Its proof categories include origin, utility, containment, compatibility, approval, and reversibility; reversibility is always partial with blocker `write_mode_rollback_not_implemented` in `app/skill_receipt.py:208`.
- Evidence checkpointing is the existing tamper-evidence surface for `runs/`: `build_evidence_checkpoint_report(..., verify=True)` blocks when current evidence differs from the latest checkpoint in `app/evidence_checkpoint.py:44`.
- Shadow activation already models a managed-prefix gate. `build_shadow_write_gate_report(...)` verifies source hash, acceptance store/generation files, pointer restoration to rollback target, rollback marker, and exact acceptance-plan digest before reporting `ready_for_human_managed_prefix_write` in `app/shadow_activation.py:417`.
- The evidence governor remains advisory. It composes receipt, negative evidence, and checkpoint verification but has no approval, install, promotion, permission widening, or route-steering authority per `app/models.py:942` and the roadmap boundary in `docs/plans/proof-carrying-capability-roadmap-2026-06-03.md:78`.
- Prior durable admission plans intentionally stop at proof surfaces: `docs/plans/durable-admission-workflow-design-2026-06-03.md:84` calls for future write mode to consume run-scoped snapshot/staging evidence and require a separate human-approved write gate before copying into durable `skills/`; `docs/build-map.md:482` still lists durable candidate copy/install workflow and active governor steering as future boundaries.
- The lifecycle contract keeps temporary generated skills under `runs/artifacts/<run_id>/skills` and treats promotion/admission as explicit human workflow, not automatic durable routing, in `docs/skill-lifecycle.md:43`.

## Approach
Choose a separate shadow-specific write command/contract, `shadow-managed-write`, instead of enabling `admit-candidate --no-dry-run`. `admit-candidate` is already semantically tied to durable `skills/` copy/install, and the first safe real write should stay in the shadow lane that already has managed-prefix planning, acceptance evidence, rollback proof, and write-gate readiness.

The command should materialize only the already-proven shadow managed-prefix activation:

1. Verify the existing receipt and allow the current reversibility blocker only when it is exactly `write_mode_rollback_not_implemented`; this slice is the first missing managed-prefix write proof.
2. Verify the latest evidence checkpoint so approval, snapshot, staging, and shadow acceptance evidence have not drifted.
3. Verify the shadow write gate with the expected acceptance digest.
4. Compute a new `managed_write_plan_digest` that binds the candidate, source hash, durable/shadow/rollback/acceptance digests, managed prefix, profile, planned store/generation/pointer paths, rollback target, and explicit policies: managed-prefix-only write, profile-pointer switch, profile-pointer rollback, stable routing unchanged, governor advisory only. **Do not include latest checkpoint hash in this digest**; the approval must happen before the post-approval checkpoint, so checkpoint hash is verified separately at execution time to avoid a circular approval loop.
5. Require a separate human write approval tied to that managed-write digest and expiry. Durable review approval and durable plan approval are necessary evidence but are not sufficient write approval.
6. On `--no-dry-run`, require all expected source/hash/digest inputs and latest checkpoint hash to match before any mutation.
7. Write only under the resolved managed prefix: retain the content-addressed store file, retain the planned profile generation `SKILL.md`, atomically update the managed profile pointer, and write a managed-prefix-local receipt for idempotency.
8. Verify rollback readiness before the pointer switch and verify store/generation/pointer/rollback target after the write.

The report must make the boundary visible through one canonical mutation-flag contract: only managed-prefix/profile mutation flags may become true; durable `skills/`, registry, candidate ledger, resolution ledger, run logs, permission widening, stable routing, and governor steering remain false.

### Receipt validation rule
The write preflight should consume `SkillReceiptReport` concretely, not just check overall outcome. Block if origin is missing/blocked, containment is blocked, compatibility is blocked, approval is missing, utility is missing/blocked, or the receipt cannot be inspected cleanly. Allow reversibility to be partial only when its blocker set is exactly the existing `write_mode_rollback_not_implemented`; this command supplies that missing managed-prefix write proof. Any other reversibility blocker blocks.

### Approval parsing rule
Reuse the durable plan-approval parsing shape in `app/durable_admission.py:549`: comma or whitespace separated note tokens, ISO-8601 `expires_at` parsed with `Z` accepted as UTC, and naive timestamps treated as UTC. Candidate linkage must come from the approval record’s source request metadata for the same candidate, not from note text. A durable plan approval may use the same `approve_review` decision type, but it is not sufficient unless the selected `--write-approval-id` carries the matching `managed_write_plan_digest` token.

### Operator sequence
1. Prepare durable admission proof with `admit-candidate --dry-run`, including exact durable plan approval.
2. Prepare shadow acceptance evidence with `shadow-activation-acceptance --prepare-acceptance-evidence`.
3. Verify the shadow write gate with `shadow-write-gate --acceptance-plan-digest <digest>`.
4. Dry-run the managed write with `shadow-managed-write --dry-run ...` and capture `managed_write_plan_digest`.
5. Record separate human write approval whose notes include `managed_write_plan_digest=<digest>` and non-expired `expires_at=<timestamp>`.
6. Append and verify evidence checkpoint; capture the latest checkpoint hash.
7. Execute `shadow-managed-write --no-dry-run` with every expected digest/hash, the checkpoint hash, and `--write-approval-id`.
8. If the managed prefix is under `runs/managed_shadow`, run `evidence-checkpoint --no-dry-run` again after the write if the operator wants the new managed-prefix state checkpointed; the pre-write checkpoint may be stale after a successful write.

### Non-goals
- Do not enable `admit-candidate --no-dry-run`.
- Do not copy into durable `skills/`.
- Do not mutate the durable registry, candidate ledger, resolution ledger, or run logs from the write command.
- Do not promote a candidate to stable routing.
- Do not grant governor or evidence-governor authority to approve, install, promote, widen permissions, or steer routing.
- Do not support permission widening or dependency installation in this first slice.

## Work Items

### Item 1 — Lock the command and report contract
**Goal:** Add an implementation-ready contract for the managed-prefix write slice without changing behavior.

**Done when:**
- The plan names `shadow-managed-write` as the first real write surface.
- The report contract is specified as `ShadowManagedWriteReport` with identity, mode/outcome, paths, hashes/digests, verification booleans, mutation flags, nested evidence, blockers, warnings, and next steps.
- Outcomes cover at least `approval_required`, `blocked`, `ready_for_managed_prefix_write`, `managed_prefix_write_applied`, and `already_applied`.
- Mutation flags explicitly preserve `durable_skills_mutated=False`, `registry_mutated=False`, `candidate_ledger_mutated=False`, `resolution_ledger_mutated=False`, `run_logs_mutated=False`, and `governor_steering_enabled=False`.

**Key files:** `app/models.py:712`, `app/models.py:942`, `app/models.py:1100`; `app/cli.py:899`; `app/shadow_activation.py:417`.

**Dependencies:** Existing shadow activation, rollback, acceptance, and write-gate report models.

**Size:** Small.

### Item 2 — Add read-only managed-write preflight
**Goal:** Build the non-mutating planner that composes existing evidence and computes the managed-write digest.

**Done when:**
- `build_shadow_managed_write_report(..., dry_run=True)` composes `build_skill_receipt_report(...)`, `build_evidence_checkpoint_report(verify=True)`, and `build_shadow_write_gate_report(...)`.
- It computes `managed_write_plan_digest` from candidate identity, source hash, durable plan digest, shadow plan digest, rollback plan digest, acceptance plan digest, managed prefix, profile, store/generation/pointer paths, rollback target, and explicit policy strings; latest checkpoint hash is explicitly excluded and verified separately.
- It verifies supplied expected values when present and reports blockers without writing.
- It treats receipt reversibility as acceptable only when the sole relevant blocker is `write_mode_rollback_not_implemented`; other missing/blocked receipt proofs still block.

**Key files:** `app/shadow_activation.py:417`, `app/skill_receipt.py:23`, `app/evidence_checkpoint.py:44`, `app/durable_admission.py:620`.

**Dependencies:** Item 1.

**Size:** Medium.

### Item 3 — Add the CLI and output surface while initially proving dry-run
**Goal:** Expose the preflight in a way operators can use to capture the write digest before requesting human approval, while reserving the `--no-dry-run` path for later work items.

**Done when:**
- `skill-agent shadow-managed-write <candidate_id>` exists with `--dry-run/--no-dry-run`, defaulting to `--dry-run`.
- CLI options include existing context inputs (`--runs-dir`, `--skills-dir`, `--managed-prefix`, `--acceptance-prefix`, `--profile-name`, `--collision-policy`, `--permission-approval-id`, `--plan-approval-id`) plus expected digest/hash fields, `--expected-checkpoint-hash`, `--write-approval-id`, and `--json`.
- Dry-run output shows outcome, managed prefix, profile, source hash, managed-write digest, expected-match booleans, checkpoint status, approval status, rollback status, mutation flags, blockers, warnings, and next steps.
- `admit-candidate --no-dry-run` remains rejected exactly as today.

**Key files:** `app/cli.py:899`, `app/cli_output.py`, `app/shadow_activation.py:417`, `tests/test_durable_admission_preview.py:443`.

**Dependencies:** Items 1–2.

**Size:** Small.

### Item 4 — Require separate human write approval
**Goal:** Ensure real managed-prefix writes are authorized by a new human approval, not by durable review approval alone.

**Done when:**
- Real write preflight requires `--write-approval-id` for `--no-dry-run`.
- The approval must be a resolved `approve_review` record for the same candidate.
- Approval notes must include matching `managed_write_plan_digest=<digest>` and a non-expired ISO-8601 `expires_at=<timestamp>` parsed with the same token and timezone rules as durable plan approval.
- Durable review approval, durable plan approval, and permission approval remain separate signals and cannot substitute for managed-write approval.
- The write command only reads approval evidence; it does not mutate the resolution ledger.

**Key files:** `app/durable_admission.py:476`, `app/input_resolution_ledger.py`, `app/shadow_activation.py:417`, `tests/test_durable_admission_preview.py:20`.

**Dependencies:** Items 1–3.

**Size:** Medium.

### Item 5 — Enforce exact digest, hash, checkpoint, and gate matches
**Goal:** Make the mutating path impossible unless all proof surfaces match the operator’s expected values.

**Done when:**
- `--no-dry-run` requires expected source sha256, durable plan digest, shadow plan digest, rollback plan digest, acceptance plan digest, managed-write plan digest, latest checkpoint hash, and write approval id.
- The command blocks before any write if any expected value is missing or mismatched.
- `build_evidence_checkpoint_report(verify=True)` must return verified, and the latest checkpoint hash must match `--expected-checkpoint-hash`.
- `build_shadow_write_gate_report(...)` must report `ready_for_human_managed_prefix_write=True` with source hash, acceptance store/generation, restored pointer, rollback marker, rollback plan, and acceptance digest verified.

**Key files:** `app/evidence_checkpoint.py:44`, `app/shadow_activation.py:417`, `app/durable_admission.py:620`, `tests/test_evidence_checkpoint.py:11`, `tests/test_shadow_activation.py:690`.

**Dependencies:** Items 2–4.

**Size:** Medium.

### Item 6 — Implement managed-prefix-only mutation with rollback proof
**Goal:** Add the first actual write while keeping its scope confined to the managed prefix.

**Done when:**
- `--no-dry-run` writes only under the resolved managed prefix.
- Planned store and generation paths are resolved and rejected if they escape the managed prefix; the implementation may use existing shadow path helpers or a stricter confinement primitive to prevent symlink/path traversal surprises.
- Store and generation `SKILL.md` files are created if absent, reused if bytes/hash match, and blocked if existing bytes mismatch.
- The command verifies pre-write rollback target and current pointer state before switching.
- The activation pointer update is atomic and points only to the planned generation.
- Post-write verification confirms store hash, generation hash, pointer target, and rollback target.
- No path under `skills_dir`, `runs/admission_snapshots`, `runs/admission_staging`, or `runs/shadow_activation_acceptance` is written by this command.

**Key files:** `app/shadow_activation.py:26`, `app/shadow_activation.py:129`, `app/shadow_activation.py:212`, `app/shadow_activation.py:417`, `tests/test_shadow_activation.py:690`.

**Dependencies:** Items 1–5.

**Size:** Medium.

### Item 7 — Add idempotency and interruption recovery
**Goal:** Make retries safe when a previous write attempt partially completed.

**Done when:**
- The command writes a managed-prefix-local receipt, such as `<managed_prefix>/profiles/<profile>/write_receipts/<managed_write_plan_digest>.json`.
- If receipt, store, generation, and pointer already match, the report returns `already_applied`.
- If store/generation match but pointer remains at rollback target, rerun may complete the pointer switch after all gates still verify.
- If any receipt, store, generation, or pointer state conflicts with the expected digest/hash, the command blocks rather than overwriting.

**Key files:** `app/shadow_activation.py:417`, `app/models.py:1100`, `tests/test_shadow_activation.py:690`.

**Dependencies:** Items 1, 5, and 6.

**Size:** Small-to-medium.

### Item 8 — Add acceptance tests and regression guards
**Goal:** Prove the slice is real, narrow, idempotent, and non-routing.

**Done when:**
- New focused tests cover dry-run no-write behavior, happy-path real managed-prefix write, source/digest/checkpoint/approval mismatch blockers, expired approval, conflicting existing bytes, idempotent rerun, and interrupted retry.
- Existing durable admission tests still prove `admit-candidate --no-dry-run` is rejected.
- Existing shadow activation tests still prove acceptance evidence is run-scoped and write gate is read-only until the new command executes.
- Tests assert no durable `skills/`, registry, candidate ledger, resolution ledger, stable routing, or governor mutation occurs.

**Key files:** `tests/test_shadow_activation.py:690`, `tests/test_durable_admission_acceptance.py:90`, `tests/test_durable_admission_preview.py:443`, `tests/test_evidence_checkpoint.py:11`, new `tests/test_shadow_managed_write.py`.

**Dependencies:** Items 1–7.

**Size:** Medium.

### Item 9 — Update durable docs and roadmap boundaries
**Goal:** Make the new write capability understandable without weakening existing lifecycle promises.

**Done when:**
- `docs/build-map.md` records human-approved managed-prefix write mode as the next slice, distinct from durable `skills/` admission.
- `docs/operating-roadmap.md` explains the operator sequence and that stable routing remains later work.
- `docs/skill-lifecycle.md` clarifies managed-prefix activation is not candidate-to-stable promotion and does not admit to durable `skills/`.
- `docs/contracts/data-contracts.md` documents `ShadowManagedWriteReport` fields and mutation flags.
- Prior plan references are not rewritten; this plan remains the handoff document for implementation.

**Key files:** `docs/build-map.md:462`, `docs/operating-roadmap.md:184`, `docs/skill-lifecycle.md:43`, `docs/contracts/data-contracts.md:384`.

**Dependencies:** Items 1–8.

**Size:** Small.

## Validation Plan
- Targeted tests:
  - `.venv/bin/python -m pytest -q tests/test_shadow_managed_write.py`
  - `.venv/bin/python -m pytest -q tests/test_shadow_activation.py tests/test_evidence_checkpoint.py`
  - `.venv/bin/python -m pytest -q tests/test_durable_admission_preview.py tests/test_durable_admission_acceptance.py`
- Full local gates:
  - `.venv/bin/python -m pytest -q`
  - `.venv/bin/python -m compileall -q app`
- Documentation gates:
  - `.venv/bin/python -m pytest -q tests/test_durable_admission_workflow_docs.py` when durable admission workflow docs or related references change.
  - Add/extend the corresponding docs contract test if `docs/contracts/data-contracts.md` gains `ShadowManagedWriteReport` fields.
  - Confirm `git diff --check` is clean before review.

## Open Questions
None for the first slice. The plan chooses managed-prefix-only `shadow-managed-write`; durable `skills/` install, stable promotion, and governor steering stay out of scope.

## Implementation Progress
- [x] Chunk 1 — Command/report contract and read-only dry-run surface. Implemented `ShadowManagedWriteReport`, `build_shadow_managed_write_report(..., dry_run=True)`, `shadow-managed-write` CLI/output, and dry-run/no-write tests. Validation reported by agent: `tests/test_shadow_activation.py` 16 passed; durable admission preview/acceptance tests 20 passed; compileall and `git diff --check` passed.
- [x] Chunk 2 — Separate human write approval plus exact digest/hash/checkpoint gates. Implemented write approval verification, exact expected-value checks, checkpoint hash matching, and `--no-dry-run` pre-mutation blockers. Validation reported by agent: `tests/test_shadow_activation.py` 18 passed; durable admission preview/acceptance plus checkpoint tests 25 passed; compileall and `git diff --check` passed.
- [x] Chunk 3 — Managed-prefix-only mutation, rollback proof, idempotency, and interruption recovery. Implemented managed-prefix store/generation/pointer/receipt writes, confinement checks, pre/post rollback verification, already-applied reruns, interrupted retry, and conflict blockers. Validation reported by agent: `tests/test_shadow_activation.py` 20 passed; durable admission preview/acceptance plus checkpoint tests 25 passed; compileall and `git diff --check` passed.
- [x] Chunk 4 — Docs/contracts updates, full validation, and final review. Documented `shadow-managed-write` in build map, operating roadmap, lifecycle, and data contracts; added docs regression coverage; fixed Oracle review blockers for mutation report flags, symlink confinement, post-switch failure handling, and missing-receipt interruption. Final validation: `.venv/bin/python -m pytest -q` 225 passed; `.venv/bin/python -m compileall -q app` passed; `git diff --check` passed.

## References
- `app/durable_admission.py:35`, `app/durable_admission.py:620`, `app/durable_admission.py:668`
- `app/skill_receipt.py:23`, `app/skill_receipt.py:208`
- `app/evidence_checkpoint.py:44`
- `app/shadow_activation.py:417`
- `app/models.py:712`, `app/models.py:942`, `app/models.py:1100`
- `app/cli.py:899`
- `docs/plans/durable-admission-workflow-design-2026-06-03.md`
- `docs/plans/durable-candidate-admission-plan-2026-06-02.md`
- `docs/plans/proof-carrying-capability-roadmap-2026-06-03.md`
- `docs/skill-lifecycle.md`
- `docs/build-map.md`
