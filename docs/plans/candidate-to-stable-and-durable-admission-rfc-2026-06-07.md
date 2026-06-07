# Candidate-To-Stable And Durable Admission RFC

Status: design only

This RFC refreshes the post-v1 boundary between candidate evidence, durable
admission review, managed-prefix local use, and future stable routing. It is a
review contract, not an implementation slice.

## Product Question

What proof must exist before a generated or temporary skill can move from
review evidence toward any durable or stable local-use state?

Answer for this RFC: the product should keep `operator-summary` as the review
front door, require exact evidence-bound human decisions, and continue to fail
closed until a later implementation slice proves new authority.

## Current State

- Candidate evidence lives in the Skill Candidate Ledger and matching run logs.
- Promotion approval can mark a ledger entry as `candidate` evidence, but does
  not install, admit, route, or mark a skill stable.
- `stable-readiness` is advisory candidate-to-stable review rehearsal.
- `admission-plan` and `admit-candidate --dry-run` preview durable admission
  evidence and future write intent without copying into durable `skills/`.
- `shadow-managed-write` is a human-approved managed-prefix local-use write,
  not durable `skills/` admission and not positive stable routing.
- `operator-summary` should be the first inspection command for a reviewer.

## Vocabulary Boundary

| Concept | Meaning | Not Authority For |
| --- | --- | --- |
| Candidate evidence | Ledger and run-log proof that a temporary skill may deserve review | Durable admission, stable status, routing, permission widening |
| Promotion approval | Human notes that allow the ledger status to become `candidate` evidence | Durable `skills/` copy, stable routing, dependency install |
| Durable admission review | Human review of source, path, collision, permission, dependency, digest, and checkpoint evidence | Write mode by itself |
| Managed-prefix local use | Human-approved write into the shadow managed prefix after exact gates | Durable `skills/` admission or normal routing |
| Stable routing | Future positive route selection for stable skills | Out of scope for v1 and this RFC |

## Required Proof Before Any Future Authority

Future durable admission or stable routing work must require all applicable
proof before it can change behavior:

- Source hash for the selected `SKILL.md`.
- Exact plan digest for the proposed operation.
- Latest evidence checkpoint hash.
- Human approval ID tied to the same candidate and operation.
- Approval expiry that has not passed.
- Collision policy and any replacement approval evidence.
- Permission diff and separate approval for permission widening.
- Dependency diff and no-write dependency evidence; dependency installation is
  still unsupported.
- Rollback or deactivation evidence for any managed or stable-use path.
- No unresolved negative evidence, duplicate contract, repair requirement,
  stale source, symlink/path escape, or checkpoint blocker.

## Failure Cases That Must Fail Closed

| Failure Case | Expected Result | Existing Proof Surface |
| --- | --- | --- |
| Stale source hash | Block write-evidence preparation with `source_hash_mismatch` | `tests/test_durable_admission_acceptance.py` |
| Expired approval | Block preview with `plan_digest_approval_expired` | `tests/test_durable_admission_preview.py` |
| Digest mismatch | Block preview with `plan_digest_approval_mismatch` | `tests/test_durable_admission_preview.py` |
| Permission widening | Require separate permission approval and still block unsafe source state | `tests/test_durable_admission_preview.py` |
| Duplicate candidate | Block stable readiness and surface negative evidence | `tests/test_stable_readiness.py` |
| Negative evidence present | Block or warn before stable review or promotion | `tests/test_stable_readiness.py`, `tests/test_operator_summary.py` |
| Missing checkpoint | Surface `verify_or_checkpoint_evidence` in `operator-summary` | `tests/test_operator_summary.py` |
| Symlink or path escape | Block source path outside `runs_dir` before admission review | `tests/test_durable_admission_acceptance.py` |
| Repaired history with unresolved blockers | Keep repair evidence visible and prevent review shortcutting | `tests/test_operator_summary.py`, `tests/test_stable_readiness.py` |

## Future Test And Eval Plan

Before enabling any new authority, add or preserve proof that:

- no adversarial lifecycle case mutates durable `skills/`;
- no stable routing flag becomes true without an explicit stable-routing slice;
- no governor report becomes an authorization record;
- `operator-summary` places unsafe, blocked, missing, or checkpoint evidence
  before promotion or stable-use review;
- eval reports include clear failure categories and next-action guidance for
  stale evidence, approval mismatch, negative evidence, duplicates, and
  checkpoint blockers.

## Non-Goals

- No durable generated-skill admission into `skills/`.
- No positive stable routing.
- No dependency installation.
- No new write authority.
- No active governor steering.
- No permission widening without exact human approval.
- No marketplace, hosted service, or production safety claim.
