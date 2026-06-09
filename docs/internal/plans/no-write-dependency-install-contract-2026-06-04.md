# No-Write Dependency Install Contract: Plan

## Goal
Define the next no-write dependency install contract for durable admission before candidate-to-stable promotion, durable `skills/` admission, or stable routing gains more authority.

The slice should extend `admit-candidate --dry-run` so dependency install feasibility becomes proof-carrying evidence: run-scoped, digest-bound, approval-aware, and explicit about unresolved dependencies while leaving durable skills, ledgers, registry, governor steering, and stable routing unchanged.

## Background
- Roadmap ordering: `docs/operating-roadmap.md:83-87` names no-write dependency install contract as the next coverage after the managed-prefix write boundary, before candidate-to-stable workflow design, promotion review queues, durable `skills/` admission, and stable routing.
- Current dependency gap: `docs/contracts/data-contracts.md:894` states the permission/dependency diff packet is evidence-only; exact `dependency_realization` can clear `dependency_realization_missing`, but install remains blocked until a future no-write install contract exists. `docs/contracts/data-contracts.md:994` lists both `dependency_realization_missing` and `dependency_install_unsupported` as blockers.
- Durable admission command surface: `app/cli.py:1022-1093` defines `admit-candidate` with `--dry-run/--no-dry-run`, collision policy, permission approval, plan approval, `--prepare-write-evidence`, `--expected-source-sha256`, and JSON output. `app/durable_admission.py:49-53` rejects write mode outright.
- Dependency extraction seam: `app/admission_plan.py:244-391` parses candidate `SKILL.md` metadata and records recognized dependency declarations from `dependencies`, `dependency_realization`, `dependency_lock`, `requirements`, and `packages` on `AdmissionSourceArtifact.dependency_declarations`.
- Dependency blocker seam: `app/durable_admission.py:341-400` builds `AdmissionPermissionDependencyDiff`; `app/durable_admission.py:372-376` emits `dependency_realization_missing` when declared dependencies lack exact realization and `dependency_install_unsupported` when every declared dependency has exact realization but install support is absent.
- Dependency name/realization parsing: `app/durable_admission.py:402-440` extracts names from declaration keys and lock entries; `app/durable_admission.py:443-463` recognizes realized dependencies only when `dependency_realization` entries include `name`, `version`, and `sha256`.
- Digest/approval precedent: `app/durable_admission.py:154-181` computes and checks an exact plan digest; `app/durable_admission.py:623-659` includes source, target, snapshot/staging paths, collision policy, permission approval, permission/dependency diff, evidence-prep flags, and expected source hash in that digest. `docs/contracts/data-contracts.md:887-892` documents digest approval invalidation when source, destination, policy, approval, or evidence-preparation options drift.
- Run-scoped evidence precedent: `app/durable_admission.py:672-693` names snapshot/staging paths under `runs/admission_snapshots/` and `runs/admission_staging/`; `app/durable_admission.py:737-776` prepares only those artifacts. `tests/test_durable_admission_acceptance.py:114-200` verifies hash-matched run-scoped evidence creation/reuse while durable skills remain unchanged.
- No-write proof convention: `app/models.py:676-739` keeps durable mutation booleans false in `DurableAdmissionWritePlan` and `DurableAdmissionPreviewReport`; `tests/test_durable_admission_acceptance.py:732-748` asserts report and write-plan mutation flags remain false. `tests/test_durable_admission_preview.py:500-534` verifies CLI text/JSON report no mutation support and `--no-dry-run` rejection.
- Evidence checkpoint precedent: `app/evidence_checkpoint.py:44-115` has dry-run and verify paths that compute evidence without appending to the checkpoint ledger; `tests/test_evidence_checkpoint.py:12-34` asserts dry-run checkpoint leaves the run tree unchanged. This is useful precedent for distinguishing computed proof from explicit evidence writes.
- Prior plan pattern: `docs/internal/plans/durable-admission-workflow-design-2026-06-03.md:52-70` defines a dry-run contract that names future copy/install intent while keeping mutation flags false; `docs/internal/plans/durable-admission-workflow-design-2026-06-03.md:92-105` requires future install/copy slices to add explicit command contract, dry-run mode, immutable source evidence, staged destination evidence, collision policy, separate permission approval, and tests proving historical evidence is not rewritten.
- Managed-prefix boundary precedent: `docs/internal/plans/human-approved-durable-write-mode-2026-06-04.md:31` confines true mutation flags to managed-prefix/profile writes, while durable skills, registry, ledgers, run logs, permission widening, stable routing, and governor steering remain false. `docs/internal/plans/human-approved-durable-write-mode-2026-06-04.md:50-55` explicitly excludes dependency installation.
- Lifecycle boundary: `docs/skill-lifecycle.md:43-50` keeps temporary-to-candidate as ledger approval only, with no copy/install/admission/routing; `docs/skill-lifecycle.md:55-59` defines candidate-to-stable as later evidence and maintainer approval.
- Up-front user decisions for this plan: allow run-scoped evidence artifacts under `runs/`; include unresolved dependency path; extend `admit-candidate --dry-run` rather than introduce a separate command; reserve an evidence-only approval/digest hook now while still performing no dependency install or durable mutation.

## Approach
Extend the existing `admit-candidate --dry-run` preview rather than adding a new command. This keeps dependency install feasibility inside the durable admission proof surface that already knows the selected source, source hash, target path, permission/dependency diff, plan digest, human approval evidence, CLI output, and no-write mutation flags.

The slice adds a dependency install **contract preview**, not dependency installation. The preview should live inside `DurableAdmissionWritePlan` alongside the existing `permission_dependency_diff`, likely as a strict nested model such as `AdmissionDependencyInstallContract`. It should report:

- a deterministic `dependency_plan_digest`;
- normalized declared, realized, and unresolved dependency items;
- optional run-scoped evidence manifest paths under a deterministic `runs/` namespace, for example `runs/admission_dependency_evidence/<candidate_id>/<source_sha256>/dependency_plan.json`;
- preparation/reuse/verification booleans for that manifest;
- optional evidence-only approval fields using `dependency_plan_digest=<sha256>` and `expires_at=<timestamp>` note tokens;
- hard boundary flags such as `install_supported=false`, `install_attempted=false`, and `dependencies_installed=false`.

Keep the existing blockers meaningful. Unresolved dependencies still produce `dependency_realization_missing`; exact realization still clears that missing-realization blocker but leaves `dependency_install_unsupported` until a later actual-install slice exists. A valid dependency approval or prepared manifest records review/proof only; it does not authorize installation, remove install blockers, mutate durable skills, promote candidates, or enable stable routing.

Allow a prepare-dependency-evidence option to write a deterministic run-scoped manifest even when dependency blockers are present, because unresolved dependencies are part of the evidence this slice is meant to preserve. Separate blockers that prevent manifest writes from blockers that are merely recorded in the manifest: source/read failures, source hash mismatch, expected dependency digest mismatch, and conflicting existing manifest bytes should prevent evidence writes; `dependency_realization_missing` and `dependency_install_unsupported` should be recorded as dependency status/blockers without preventing the no-write manifest itself. This follows the existing `--prepare-write-evidence` pattern while making the dependency artifact narrower and explicitly non-installing.

Treat the `## Background` findings and up-front user decisions as implementation constraints unless fresh repo evidence contradicts them. The implementation agent should not reopen the settled product choices: extend `admit-candidate --dry-run`, include unresolved and exact-realization paths, allow only run-scoped dependency evidence, and keep approval evidence non-installing.

## Work Items

### Item 1 — Define the dependency install contract model

**Goal:** Add a strict output contract for no-write dependency install evidence without changing runtime behavior.

**Done when:**
- `app/models.py` defines a nested model such as `AdmissionDependencyInstallContract`.
- `DurableAdmissionWritePlan` includes `dependency_install_contract`.
- The contract carries policy, digest, normalized dependency items, evidence paths/booleans, optional approval fields, blockers, warnings, and boundary flags: `install_supported=false`, `install_attempted=false`, `dependencies_installed=false`.
- Existing durable mutation fields remain false by default and in all current preview paths.

**Key files:** `app/models.py`, `docs/contracts/data-contracts.md`

**Dependencies:** None

**Size:** Small

### Item 2 — Normalize dependency declaration details

**Goal:** Preserve item-level dependency proof for both unresolved and exact-realized paths while keeping today’s summary fields stable.

**Done when:**
- `app/durable_admission.py` produces normalized dependency items with name, declaration key/source, declared spec/version text when available, realization version/hash when present, and status such as `unresolved` or `exact_realized`.
- Normalization defines deterministic ordering, de-dupe behavior, and conflict handling across `dependencies`, `requirements`, `packages`, `dependency_lock`, and `dependency_realization` before digest work depends on it.
- Existing fields continue to work: `added`, `realized`, `unresolved`, `declaration_keys`, and `exact_realization_available`.
- Existing blocker behavior is preserved: unresolved dependencies produce `dependency_realization_missing`; exact realization produces `dependency_install_unsupported`.

**Key files:** `app/durable_admission.py`, `app/models.py`, `tests/test_durable_admission_preview.py`

**Dependencies:** Item 1

**Size:** Medium

### Item 3 — Compute a deterministic dependency plan digest

**Goal:** Bind dependency feasibility evidence to the selected source, target, no-write policy, and normalized dependency plan.

**Done when:**
- `app/durable_admission.py` computes `dependency_plan_digest` from stable JSON containing candidate ID, source path, source SHA-256, target skill path, normalized dependency items, evidence manifest path, and no-write policy constants.
- The dependency digest excludes volatile approval verification state, creation booleans, and timestamps.
- The existing durable admission `_plan_digest()` remains distinct from `dependency_plan_digest`: it should include stable dependency contract inputs and dependency-evidence option choices so source, dependency, policy, or evidence-option drift invalidates prior durable admission plan approval.

**Key files:** `app/durable_admission.py`, `app/models.py`, `tests/test_durable_admission_preview.py`

**Dependencies:** Items 1–2

**Size:** Medium

### Item 4 — Extend `admit-candidate --dry-run` with dependency contract options

**Goal:** Add the no-write dependency proof surface to the existing durable admission command.

**Done when:**
- `app/cli.py` adds dependency evidence/expected-digest/approval options; names such as `--prepare-dependency-evidence`, `--expected-dependency-plan-digest`, and `--dependency-approval-id` are preferred but can be adjusted if the final CLI spelling preserves the contract and docs/tests.
- The options pass through to `build_durable_admission_preview()`.
- `--no-dry-run` remains rejected exactly as today.
- JSON output includes the nested contract through the model dump.
- Text output surfaces dependency digest, evidence path, approval verification, install-supported false, and dependency blockers without implying install readiness.

**Key files:** `app/cli.py`, `app/cli_output.py`, `app/durable_admission.py`

**Dependencies:** Items 1–3

**Size:** Small

### Item 5 — Prepare optional run-scoped dependency evidence

**Goal:** Create deterministic dependency evidence artifacts under `runs/` only, with no durable mutation.

**Done when:**
- The prepare-dependency-evidence path may create or reuse a deterministic manifest under a run-scoped namespace such as `runs/admission_dependency_evidence/<candidate_id>/<source_sha256>/dependency_plan.json`.
- The manifest includes schema version, candidate/source/target identity, no-write policy constants, normalized dependency items, recorded dependency blockers, and `dependency_plan_digest`.
- Matching existing manifests are reused.
- Conflicting existing manifests block with a stable blocker such as `dependency_evidence_manifest_hash_mismatch` and are not overwritten.
- Manifest bytes are computed from source/dependency/policy inputs before approval verification state is attached, so approval mismatch/expiry is reported but does not make the deterministic manifest content depend on time-sensitive review state.
- Preparation does not mutate durable skills, run logs, candidate ledger, resolution ledger, registry, checkpoint ledger, governor state, candidate-to-stable state, or stable routing.

**Key files:** `app/durable_admission.py`, `tests/test_durable_admission_acceptance.py`

**Dependencies:** Items 1–4

**Size:** Medium

### Item 6 — Verify evidence-only dependency approval

**Goal:** Reserve a human review hook without authorizing dependency installation.

**Done when:**
- `--dependency-approval-id` verifies an append-only resolved input request resolution record.
- Valid approval must follow the existing plan-approval identity pattern: the supplied ID may match `InputRequestResolutionRecord.id` or `input_request_id`; the record must be `decision == "approve_review"`, `status == "resolved"`, `source_request.kind == "durable_admission_review"`, and `source_request.related_candidate_id == candidate_id`; notes must contain matching `dependency_plan_digest=<digest>` and a non-expired `expires_at=<timestamp>`.
- Missing dependency approval is not a blocker by default.
- Supplied invalid, mismatched, expired, or expiry-missing approval is reported as a blocker.
- Valid approval sets contract fields but does not remove `dependency_realization_missing` or `dependency_install_unsupported`.

**Key files:** `app/durable_admission.py`, `app/input_resolution_ledger.py`, `tests/test_durable_admission_preview.py`

**Dependencies:** Items 1–5, plus the approval-linkage data contract documented before or alongside this item

**Size:** Medium

### Item 7 — Extend tests for both dependency paths and no-mutation guarantees

**Goal:** Prove the contract is informative, digest-bound, approval-aware, and non-mutating.

**Done when:**
- Tests cover unresolved dependencies retaining `dependency_realization_missing`.
- Tests cover exact realization retaining `dependency_install_unsupported`.
- Tests show `dependency_plan_digest` changes when dependency declarations or realization data change.
- Tests show `--prepare-dependency-evidence` creates/reuses only run-scoped manifest files.
- Tests show expected dependency digest mismatch blocks without writing.
- Tests show existing manifest mismatch blocks without overwrite.
- Tests show valid dependency approval is recorded as verified and mismatched/expired approval is rejected.
- Tests assert durable skills, ledgers, registry, governor steering, candidate-to-stable, stable routing, and actual install remain unchanged, preferably through one shared no-mutation helper rather than bespoke assertions for every subsystem.

**Key files:** `tests/test_durable_admission_preview.py`, `tests/test_durable_admission_acceptance.py`, `tests/test_evidence_checkpoint.py`

**Dependencies:** Items 1–6

**Size:** Medium

### Item 8 — Update contracts, roadmap, and docs guardrails

**Goal:** Document the no-write dependency contract without weakening lifecycle boundaries.

**Done when:**
- `docs/contracts/data-contracts.md` documents the dependency install contract fields, blockers, evidence manifest path, digest semantics, and approval hook.
- `docs/operating-roadmap.md` records the slice as dependency evidence only and keeps candidate-to-stable/stable routing later.
- Add one lifecycle/guardrail note, either in `docs/skill-lifecycle.md` or the most relevant existing docs-test surface, stating dependency evidence is not durable admission, stable promotion, routing, or install.
- Docs tests assert the core no-install/no-routing/no-ledger-mutation language only where this repo already maintains wording guardrails.

**Key files:** `docs/contracts/data-contracts.md`, `docs/operating-roadmap.md`, `docs/skill-lifecycle.md`, `tests/test_durable_admission_workflow_docs.py`

**Dependencies:** Items 1–7

**Size:** Small

### Item 9 — Validate the slice in the repo’s proof style

**Goal:** Prove the implementation lands inside the current no-write boundaries.

**Done when:**
- Targeted tests pass:
  - `.venv/bin/python -m pytest -q tests/test_durable_admission_preview.py`
  - `.venv/bin/python -m pytest -q tests/test_durable_admission_acceptance.py`
  - `.venv/bin/python -m pytest -q tests/test_durable_admission_workflow_docs.py`
- Full local gates pass:
  - `.venv/bin/python -m pytest -q`
  - `.venv/bin/python -m compileall -q app`
  - `git diff --check`
- Any eval impact is limited to additive JSON shape changes and documented as such.

**Key files:** `tests/`, `app/`, `docs/`

**Dependencies:** Items 1–8

**Size:** Small

## Implementation Progress
- [x] Items 1–7 — Code, CLI, dependency contract model, run-scoped evidence manifest, approval verification, and targeted tests implemented and verified with `.venv/bin/python -m pytest -q tests/test_durable_admission_preview.py tests/test_durable_admission_acceptance.py`, `.venv/bin/python -m compileall -q app`, and `git diff --check`. Review follow-up also tightened dependency evidence manifest confinement and unsafe-source preparation blockers; final full validation passed with `.venv/bin/python -m pytest -q` (237 passed), `.venv/bin/python -m compileall -q app`, and `git diff --check`.
- [x] Item 8 — Contracts, roadmap, lifecycle/guardrail docs updated.
- [x] Item 9 — Docs workflow tests and full validation bundle passed after review safety fixes.
- [x] 2026-06-05 acceptance-matrix hardening — Added black-box acceptance coverage proving a valid dependency approval verifies the digest but does not remove unresolved dependency blockers, does not mark installs supported/attempted/complete, and does not mutate durable skills or run evidence. Focused validation passed with `.venv/bin/python -m pytest -q tests/test_durable_admission_acceptance.py tests/test_durable_admission_preview.py` (34 passed), `.venv/bin/python -m compileall -q app`, and `git diff --check`.

## Open Questions
No product-scope questions. The plan intentionally locks down the user-selected boundaries: run-scoped evidence is allowed, unresolved dependency evidence is in scope, `admit-candidate --dry-run` is the command surface, and the approval hook is evidence-only.

## References
- `docs/operating-roadmap.md:83-87`
- `docs/contracts/data-contracts.md:884-901`, `docs/contracts/data-contracts.md:994`
- `docs/internal/plans/durable-admission-workflow-design-2026-06-03.md:52-105`
- `docs/internal/plans/human-approved-durable-write-mode-2026-06-04.md:31`, `docs/internal/plans/human-approved-durable-write-mode-2026-06-04.md:50-55`
- `docs/skill-lifecycle.md:43-59`
- `app/cli.py:1022-1093`
- `app/admission_plan.py:244-391`
- `app/durable_admission.py:49-53`, `app/durable_admission.py:154-181`, `app/durable_admission.py:341-463`, `app/durable_admission.py:623-776`
- `app/models.py:539-568`, `app/models.py:676-739`
- `tests/test_durable_admission_preview.py:289-383`, `tests/test_durable_admission_preview.py:500-534`
- `tests/test_durable_admission_acceptance.py:114-200`, `tests/test_durable_admission_acceptance.py:732-748`
