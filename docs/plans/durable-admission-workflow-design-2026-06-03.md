# Durable Admission Workflow Design

Status: design/proof slice complete

This plan defines the next durable admission workflow before any copy/install mutation exists. The current repo already has `skill-agent admission-plan`, an output-only dry-run planner. This slice keeps that planner as the evidence source and defines the review gate that must be proven before any future durable install/copy implementation.

## Product Question

Can an operator inspect a candidate's path from temporary evidence to durable admission review without mutating `skills/`, rewriting ledgers, widening permissions, or letting the governor steer execution?

Answer for this slice: yes, as a workflow contract and proof checklist. Real durable admission remains future work.

## Current Evidence Surfaces

- Skill Candidate Ledger: records requested, draft, temporary, candidate, blocked, validation, promotion, and evidence-run state.
- Run logs: immutable per-run evidence for temporary skill generation, validation, loading, and source artifact paths.
- `skill-agent promote-candidate`: records reviewer/notes promotion approval and can move eligible temporary entries to `candidate` evidence status.
- `skill-agent admission-plan`: dry-run report for candidate readiness, source artifact validation, durable registry collisions, blockers, warnings, next steps, and `durable_admission_review` input requests.
- `skill-agent input-requests`: advisory queue for promotion approval, durable admission review, repair, missing evidence, ambiguity, and safety approval boundaries.
- `skill-agent resolve-input-request`: dry-run or append-only resolution evidence. `approve_review` may resolve a `durable_admission_review` input request, but it does not copy, install, admit, promote to stable, widen permissions, or steer the governor.
- `skill-agent admit-candidate --dry-run`: previews the future write-mode contract with source and target paths, source hash, collision policy, permission policy, source snapshot retention path, required approval evidence, and false mutation flags.
- Eval reports: capability-gap, lifecycle, and agent diagnostic suites prove routing, lifecycle evidence, input focus, and resolution-ledger state.

## Workflow

The durable admission workflow is: candidate -> review gate -> admission-plan dry run -> required proof -> human approval boundary.

```text
temporary evidence
  -> candidate ledger entry
  -> human promotion approval
  -> admission-plan dry run
  -> durable_admission_review input request
  -> optional append-only approve_review resolution evidence
  -> admit-candidate --dry-run mutation preview
  -> future durable install/copy slice, only after new proof gates exist
```

## Checkpoints

| Checkpoint | Required Proof | Boundary |
| --- | --- | --- |
| Candidate exists | Candidate ledger entry has `evidence_run_ids`, request count, validation counters, and source contract evidence | Ledger evidence does not control routing |
| Promotion approval | `promotion_approved_by`, `promotion_approved_at`, and notes are recorded by `promote-candidate` | Candidate status is evidence only, not durable admission |
| Admission dry run | `admission-plan` returns one of `ready_for_durable_review`, `needs_promotion_approval`, `evidence_incomplete`, or `blocked` | Dry run does not mutate ledger, registry, durable skills, or governor state |
| Source proof | Selected source artifact is inside `runs_dir`, exists, parses, validates, is Markdown-only, and does not request permission widening | Scripted or permission-widening candidates stay blocked |
| Registry proof | Durable registry checks report accepted/rejected same-name collisions and contract overlaps | Collisions block or warn; no registry record is admitted |
| Input request proof | `durable_admission_review` or blocker input request is visible through `input-requests` | Queue remains advisory |
| Resolution proof | Optional `approve_review` record is appended to `input_request_resolutions.json` | Resolution evidence is not install/copy approval |
| Mutation preview proof | `admit-candidate --dry-run` reports source hash, target durable path, future snapshot path, collision policy, permission policy, required human records, write blockers, and false mutation flags | `--no-dry-run` is rejected |

## Dry-Run Write-Mode Contract

The current dry-run write plan is intentionally more specific than the existing write capability. It describes future copy/install intent while keeping every mutation flag false.

The write plan fields are:

- `operation`: `copy_new_skill`, `replace_existing_skill`, or `blocked`.
- `source_skill_path` and `source_sha256`: the selected temporary `SKILL.md` and its fingerprint.
- `target_skill_dir` and `target_skill_path`: the exact future durable destination under `skills/`.
- `snapshot_dir`, `snapshot_skill_path`, and `snapshot_sha256`: the future retained source snapshot under `runs/admission_snapshots/<candidate_id>/<source_sha256>/`.
- `collision_policy`: `block_existing` by default, or `allow_replace_with_approval` for an explicitly approved replacement preview.
- `permission_policy`: `block_widening_without_approval`.
- `permission_approval_id`: optional resolution record ID for separate permission-widening approval evidence.
- Mutation booleans: `durable_skill_installed`, `ledger_mutated`, `registry_mutated`, `resolution_ledger_mutated`, `source_snapshot_created`, and `governor_steering_enabled` all remain `false`.
- `blockers` and `warnings`: the write-plan reasons that prevent a future mutation preview from becoming ready.

Collision policy:

- `block_existing` keeps same-name durable skills blocked.
- `allow_replace_with_approval` can preview `replace_existing_skill` only when append-only `approve_review` evidence exists for the same candidate.
- Replacement preview does not rewrite or delete the existing durable skill in this slice.

Permission approval policy:

- Any permission widening remains blocked unless separate resolved approval evidence is named with `--permission-approval-id`.
- Permission approval evidence does not override broader source validation failures, scripted-skill blockers, or unsafe text blockers.
- No permission is widened in this slice.

Source snapshot retention:

- The dry run computes the future snapshot location from candidate ID and source SHA-256.
- No snapshot directory or file is created in this slice.
- Future write mode must verify the source hash before retaining or copying the source.

## Future Install/Copy Preconditions

A future durable install/copy slice must first add proof that is not present today:

- A new explicit command or subcommand contract for durable admission mutation. Status: `admit-candidate --dry-run` preview exists.
- A dry-run mode for that command before any write mode. Status: write mode is unavailable and `--no-dry-run` is rejected.
- A destination preview that names the exact target path under durable `skills/`.
- A source snapshot hash or equivalent immutable source evidence reference. Status: previewed by `write_plan.snapshot_*` fields; no snapshot is created.
- A collision policy for same-name durable skills and rejected durable records. Status: `block_existing` and `allow_replace_with_approval` are dry-run preview policies.
- A permission and risk comparison that blocks widening unless a separate human approval record explicitly authorizes it. Status: `permission_policy` and `--permission-approval-id` are previewed; no widening occurs.
- A stable-promotion policy that remains separate from file copy/install.
- Tests proving run logs, historical candidate ledger entries, and historical resolution ledger records are not rewritten.
- Eval or acceptance proof that future mutation remains human-gated and cannot be triggered by planner/router/governor state.

## Non-Goals

- Do not copy or install a durable skill in this slice.
- Do not add an `admit-candidate` write command in this slice.
- Do not mutate historical run logs, candidate ledgers, input request resolution ledgers, source snapshots, or durable skill files.
- Do not widen permissions.
- Do not promote any candidate to `stable`.
- Do not add active governor steering.
- Do not rewrite the planner or router.

## Acceptance For This Slice

- This workflow plan is present under `docs/plans/`.
- Build-map and operating-roadmap references point to the design without claiming durable install/copy exists.
- Data contracts state that `approve_review` resolution evidence is not install/copy approval.
- A focused preview test protects the collision policy, destination write plan, source snapshot retention path, permission approval record hook, and historical-evidence immutability.
- A docs test protects the no-copy/no-install/no-governor/no-permission-widening boundary for this plan.
- Validation passes with targeted preview/docs tests, the repo validation bundle, and `git diff --check`.
