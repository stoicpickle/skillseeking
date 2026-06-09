# No-Write Dependency Install Contract Plan Critique

## Context / Scope

Reviewed only `docs/internal/plans/no-write-dependency-install-contract-2026-06-04.md` and its original context-builder export copy. No broad codebase exploration performed.

## Findings

### 1. Top 3 under-specified seams

1. **Approval identity matching is too implicit.** Item 6 says a valid approval must be for a `durable_admission_review` request “related to the same candidate” (`docs/internal/plans/no-write-dependency-install-contract-2026-06-04.md:127-128`), but does not say which ledger fields establish that relationship. Implementers may guess between request id, candidate id, source path, target path, source SHA, or notes tokens.
2. **Dependency item normalization lacks canonical conflict rules.** Item 2 names fields for normalized dependency items (`docs/internal/plans/no-write-dependency-install-contract-2026-06-04.md:62-64`) but not ordering, de-dupe behavior, multi-declaration conflict handling, or whether `dependencies`, `requirements`, `packages`, `dependency_lock`, and `dependency_realization` have precedence. That matters because Item 3 binds the digest to normalized items (`docs/internal/plans/no-write-dependency-install-contract-2026-06-04.md:77-80`).
3. **Manifest write blocking rules need sharper separation from dependency blockers.** The approach allows evidence preparation even when dependency blockers exist (`docs/internal/plans/no-write-dependency-install-contract-2026-06-04.md:38`), while Item 5 says manifest content includes blockers (`docs/internal/plans/no-write-dependency-install-contract-2026-06-04.md:110-114`). The plan should say whether manifest bytes are computed before or after approval/blocker validation and which blockers prevent writes vs. are merely recorded.

### 2. Specificity balance

- **Over-specified:** The exact option names (`--prepare-dependency-evidence`, `--expected-dependency-plan-digest`, `--dependency-approval-id`) are locked in at plan level (`docs/internal/plans/no-write-dependency-install-contract-2026-06-04.md:92-94`). The implementation agent could own final CLI spelling if tests/docs preserve the contract.
- **Over-specified:** The exact manifest path `runs/admission_dependency_evidence/<candidate_id>/<source_sha256>/dependency_plan.json` appears in approach and Item 5 (`docs/internal/plans/no-write-dependency-install-contract-2026-06-04.md:31`, `:110`). The important invariant is run-scoped, digest-bound, deterministic, and non-durable; exact directory naming could remain an implementation choice.
- **Dropped useful framing:** The export explicitly says the existing in-progress plan’s Background contains “curated findings and user decisions” and should be built on rather than re-derived (`docs/internal/plans/no-write-dependency-install-contract-context-builder-export-2026-06-04.md:25`). The final plan embeds the findings, but loses that framing as an implementation constraint; that makes future implementers more likely to reopen settled decisions.

### 3. Contradictions or missing dependencies

- Item 3 says `_plan_digest()` should include stable dependency contract inputs so “dependency-evidence option drift” invalidates approval (`docs/internal/plans/no-write-dependency-install-contract-2026-06-04.md:80`), but also says the dependency digest excludes volatile approval/preparation state (`:79`). The plan should distinguish **dependency_plan_digest** from the existing durable admission **plan_digest** more explicitly.
- Item 6 depends on append-only input request resolution semantics (`docs/internal/plans/no-write-dependency-install-contract-2026-06-04.md:127-131`) but does not list docs/contracts updates for that approval shape until Item 8. If approval verification is implemented first, the data contract may be guessed.

### 4. Risk of over-planning

- Item 8’s roadmap/lifecycle/docs-test expansion (`docs/internal/plans/no-write-dependency-install-contract-2026-06-04.md:160-171`) is probably heavier than needed for this slice; `data-contracts.md` plus one guardrail note may be sufficient unless wording tests already cover the exact surface.
- Item 7’s no-mutation assertion list is exhaustive (`docs/internal/plans/no-write-dependency-install-contract-2026-06-04.md:143-153`). Keep one shared helper/assertion for durable invariants rather than bespoke tests for every named subsystem.
- “Open Questions: None” (`docs/internal/plans/no-write-dependency-install-contract-2026-06-04.md:196-197`) is too absolute for a plan with unresolved implementation-order seams; replace with “No product-scope questions.”

### 5. Questions that would change implementation order

1. Should the approval data contract be documented before implementing Item 6, or is the implementer allowed to infer candidate linkage from existing ledger fields?
2. Must the manifest path be exactly as written, or can implementation choose the path while preserving run-scoped deterministic evidence?
3. Should dependency normalization be implemented as a new model/API first, before CLI/digest work, to avoid digest churn once conflict/ordering rules are clarified?
