# Data Contracts

Contracts are schema-v3 and serialized with Pydantic `model_dump(mode="json")`. Older run logs without `schema_version`, `run_id`, governor records, or request control summaries are tolerated by health analysis and explain output where applicable.

## V1 Public JSON Contract Freeze

For the v1 local CLI release, compatibility is frozen through representative fixture tests in `tests/fixtures/v1_contracts/` and `tests/test_v1_fixture_compatibility.py`. These fixtures are compatibility sentinels, not an exhaustive JSON Schema generator. They freeze required version fields, stable identity fields, required nested objects, and JSON-serializable Pydantic output shape for:

- run logs;
- skill candidate ledgers;
- input request resolution ledgers;
- evidence checkpoint ledgers;
- candidate decision reports;
- eval reports.

Version notes:

- Run logs use `SCHEMA_VERSION`, currently `3`, and serialize through `RunLog.model_dump(mode="json")`.
- Skill candidate ledgers use `SkillCandidateLedger.schema_version == 1`.
- Input request resolution ledgers use `InputRequestResolutionLedger.schema_version == 1`.
- Evidence checkpoint ledgers use `EvidenceCheckpointLedger.schema_version == SCHEMA_VERSION`, currently `3`.
- Candidate decision reports validate through `CandidateDecisionReport` with `extra="forbid"` and preserve the v1 no-authority fields for install, stable review, stable promotion, stable routing, durable skills, and registry mutation.
- Eval reports are currently plain dict reports from `skill-agent eval --json`; the v1 fixture freezes the public report envelope, aggregate summary, task result keys, routing decisions, governor decisions, and trace-completeness fields.

Fields derived from wall-clock time, local filesystem paths, temporary directories, process duration, random IDs, host environment, or non-deterministic ordering are not contract-stability guarantees unless explicitly documented. V1 fixtures use deterministic sample values for required fields of that kind.

Breaking a frozen public field should be treated as a deliberate versioned change after v1 is stamped.

## Skill Request

```json
{
  "id": "skillreq_001",
  "task_id": "task_001",
  "missing_capability": "detect contradictions",
  "reason": "No existing skill met threshold.",
  "desired_skill_name": "detect-contradictions",
  "input_schema": {"claims": "array"},
  "output_schema": {"contradictions": "array", "confidence": "number", "explanation": "string", "source_ids": "array"},
  "success_criteria": ["Finds direct contradiction", "Distinguishes contradiction from nuance or scope difference"],
  "failure_modes": ["If claims are unrelated, return no contradiction"],
  "risk_level": "low",
  "approval_required": false,
  "control_summary": {
    "governor_decision": "REQUEST_SKILL",
    "dominant_signal": "missing_skill",
    "confidence": 0.35,
    "risk_level": "low",
    "reversibility": "reversible",
    "approval_required": false,
    "approval_gate": "none",
    "blocked_reason": null,
    "evidence_to_promote": [
      "Metadata validation passes",
      "Input and output contracts are explicit",
      "Validation examples or tests pass",
      "Temporary use succeeds on the triggering task",
      "Human approval is recorded before durable promotion"
    ]
  },
  "status": "requested"
}
```

`risk_level` is safety risk, not task difficulty. A Markdown-only contradiction skill is low safety risk even if the procedure is medium complexity.

`control_summary` is optional for compatibility with older request records. New `REQUEST_SKILL` artifacts include it as a copied snapshot of the matching governor decision, not as a live reference.

## Skill Candidate Ledger

The Skill Candidate Ledger is a mutable evidence summary stored at `runs/skill_candidate_ledger.json`. Run logs remain the immutable per-run evidence source. The ledger does not promote, install, admit, route, or score skills; it only records lifecycle evidence for human review.

```json
{
  "schema_version": 1,
  "updated_at": "2026-06-01T12:00:00",
  "entries": [
    {
      "candidate_id": "candidate_abc123def456",
      "skill_name": "detect-contradictions",
      "capability": "detect contradictions",
      "status": "requested",
      "first_seen_run_id": "run_a",
      "last_seen_run_id": "run_b",
      "request_count": 2,
      "successful_temporary_uses": 0,
      "validation_pass_count": 0,
      "validation_failure_count": 0,
      "safety_flags": [],
      "duplicate_of": null,
      "duplicate_evidence": [],
      "quarantine_reason": null,
      "block_reason": null,
      "repair_requirements": [],
      "promotion_requirements": [
        "Metadata validation passes",
        "Input and output contracts are explicit",
        "Validation examples or tests pass",
        "Temporary use succeeds on the triggering task",
        "Human approval is recorded before durable promotion"
      ],
      "human_approval_required": true,
      "promotion_approved_by": null,
      "promotion_approved_at": null,
      "promotion_approval_notes": null,
      "governor_summary": {
        "governor_decision": "REQUEST_SKILL",
        "dominant_signal": "missing_skill",
        "approval_gate": "none"
      },
      "evidence_run_ids": ["run_a", "run_b"],
      "input_schema": {"claims": "array"},
      "output_schema": {"contradictions": "array"},
      "created_at": "2026-06-01T12:00:00",
      "updated_at": "2026-06-01T12:00:00"
    }
  ]
}
```

Allowed candidate statuses are `requested`, `draft`, `temporary`, `candidate`, `stable`, `deprecated`, and `blocked`. Runtime evidence recording writes `requested`, `draft`, `temporary`, and `blocked`. The explicit human promotion workflow may move an eligible `temporary` entry to ledger `candidate` status after reviewer/notes approval, but it still does not copy, install, admit, route, or score a durable skill. `stable` and `deprecated` remain future states.

Ledger updates currently record missing-skill requests, temporary draft validation outcomes, successful temporary loads, repair requirements, rejected/quarantined skills, duplicate input/output contracts, copied governor context, evidence run IDs, and promotion requirements. `human_approval_required` means durable promotion remains gated; it does not mean temporary one-run use is blocked. When `promote-candidate` records `promotion_approved_by`, `promotion_approved_at`, and `promotion_approval_notes`, the ledger entry can become `candidate` evidence, but no durable registry mutation occurs.

Candidate review queues are derived read-time summaries, not persisted lifecycle state. Current queue names are:

- `promotion_ready`
- `repair_needed`
- `blocked_or_quarantined`
- `duplicate_merge_needed`
- `repeated_requested_gap`

Candidate output and health output may include queue counts and per-entry queue names. Queues are advisory only; they do not promote, copy, install, route, score, or admit skills.

## Candidate Usefulness

`skill-agent candidate-usefulness <candidate-id>` is a read-only candidate evidence packet. It derives usefulness support from existing candidate ledger counters and matching run-log evidence. Optional `--baseline-run-id` and `--treatment-run-id` flags add a pinned paired comparison when the baseline is a no-temporary-skill control and the treatment is a matching temporary-skill run. The command does not rewrite run logs, mutate the candidate ledger, mutate the resolution ledger, copy or install durable skills, mutate the registry, create snapshots, create staging files, widen permissions, or steer the governor.

```json
{
  "candidate_id": "candidate_abc123def456",
  "skill_name": "argument-clustering",
  "capability": "argument clustering",
  "outcome": "usefulness_supported",
  "usefulness_supported": true,
  "baseline_comparison_available": false,
  "successful_temporary_uses": 1,
  "validation_pass_count": 1,
  "validation_failure_count": 0,
  "matching_successful_run_ids": ["run_abc123"],
  "evidence_runs": [
    {
      "run_id": "run_abc123",
      "run_log_path": "runs/run_20260603_abc123.json",
      "found": true,
      "result_category": "success",
      "matching_request_ids": ["skillreq_abc123"],
      "temporary_skill_paths": [
        "runs/artifacts/run_abc123/skills/argument-clustering/SKILL.md"
      ],
      "validation_passed": true,
      "loaded": true,
      "successful": true,
      "repair_requested": false
    }
  ],
  "comparison": null,
  "admission_plan_outcome": "needs_promotion_approval",
  "admission_plan_ready": false,
  "dry_run": true,
  "run_logs_mutated": false,
  "candidate_ledger_mutated": false,
  "durable_skills_mutated": false,
  "registry_mutated": false,
  "governor_steering_enabled": false,
  "blockers": [],
  "warnings": ["baseline_comparison_missing"],
  "next_steps": ["Record human promotion review or resolve admission blockers."]
}
```

When a pinned paired comparison is available, `comparison` has this shape:

```json
{
  "baseline_run_id": "run_baseline",
  "baseline_run_log_path": "runs/run_20260603_baseline.json",
  "baseline_result_category": "blocked_missing_skill",
  "baseline_exit_code": 1,
  "baseline_matches_candidate_request": true,
  "baseline_temporary_skill_present": false,
  "baseline_temporary_skill_loaded": false,
  "treatment_run_id": "run_treatment",
  "treatment_run_log_path": "runs/run_20260603_treatment.json",
  "treatment_result_category": "success",
  "treatment_exit_code": 0,
  "treatment_matches_candidate_request": true,
  "treatment_temporary_skill_present": true,
  "treatment_temporary_skill_loaded": true,
  "outcome": "improved",
  "blockers": [],
  "warnings": [],
  "summary": "Treatment succeeded with the candidate temporary skill while the baseline ended as blocked_missing_skill."
}
```

Allowed candidate usefulness outcomes are `usefulness_supported`, `needs_successful_temporary_use`, `repair_required`, `blocked`, and `evidence_missing`. `usefulness_supported` means matching preserved run-log evidence shows a temporary skill validated, loaded, and the run completed with `result_category: success`. `evidence_missing` covers missing evidence run IDs, missing run-log files, or run logs without a matching request. It is not durable admission approval.

Allowed comparison outcomes are `improved`, `no_clear_improvement`, `regressed`, and `invalid_comparison`. `baseline_comparison_available` is `true` only when the pinned pair is valid. A valid baseline must match the candidate request and must not include the candidate temporary skill. A contaminated baseline produces `invalid_comparison` with blocker `baseline_uses_candidate_skill`. A single valid pair is causal evidence for that pair only; it is not statistical lift or durable admission approval.

## Skill Receipt

`skill-agent skill-receipt <candidate-id>` is a read-only proof bundle for one candidate. It aggregates `candidate-usefulness` and `admit-candidate --dry-run` evidence into origin, utility, containment, compatibility, approval, and reversibility proof categories. The command does not rewrite run logs, mutate candidate ledgers, mutate resolution ledgers, copy or install durable skills, mutate the registry, create snapshots, create staging files, widen permissions, or steer the governor.

```json
{
  "candidate_id": "candidate_abc123def456",
  "skill_name": "argument-clustering",
  "capability": "argument clustering",
  "status": "temporary",
  "outcome": "blocked",
  "proofs": [
    {
      "category": "origin",
      "status": "present",
      "summary": "Source artifact, source hash, and future snapshot path are inspectable.",
      "evidence_refs": [
        "runs/artifacts/run_abc123/skills/argument-clustering/SKILL.md",
        "sha256:abc123..."
      ],
      "blockers": [],
      "warnings": []
    },
    {
      "category": "utility",
      "status": "present",
      "summary": "Pinned baseline/treatment evidence is available for this candidate.",
      "evidence_refs": ["run_treatment"],
      "blockers": [],
      "warnings": []
    },
    {
      "category": "approval",
      "status": "missing",
      "summary": "Human review or exact plan-digest approval is still missing.",
      "evidence_refs": ["def456..."],
      "blockers": [
        "durable_review_resolution_missing",
        "plan_digest_approval_missing"
      ],
      "warnings": []
    }
  ],
  "candidate_usefulness": {},
  "durable_admission_preview": {},
  "dry_run": true,
  "run_logs_mutated": false,
  "candidate_ledger_mutated": false,
  "resolution_ledger_mutated": false,
  "durable_skills_mutated": false,
  "registry_mutated": false,
  "governor_steering_enabled": false,
  "next_steps": ["Resolve missing or blocked proof categories before durable admission."]
}
```

Allowed receipt outcomes are `ready`, `incomplete`, and `blocked`. `ready` means every receipt proof category is present, but it is still review evidence only; it is not durable copy/install approval and does not enable write mode. `incomplete` means at least one category is missing or partial. `blocked` means at least one category has an explicit blocker such as missing promotion approval, dependency install unsupported, or absent write-mode rollback execution.

## Stable Readiness

`skill-agent stable-readiness <candidate-id>` emits a read-only `StableReadinessReport` for candidate-to-stable review. It composes the Skill Candidate Ledger, `skill-receipt`, `negative-evidence`, and the durable registry to answer whether a candidate is ready for human stable review. It does not mark the candidate stable, authorize stable promotion, enable stable routing, copy or install durable skills, mutate ledgers, mutate the registry, widen permissions, or steer the governor.

```json
{
  "candidate_id": "candidate_abc123def456",
  "skill_name": "argument-clustering",
  "capability": "argument clustering",
  "candidate_status": "candidate",
  "outcome": "ready_for_stable_review",
  "ready_for_stable_review": true,
  "required_successful_temporary_uses": 10,
  "successful_temporary_uses": 10,
  "validation_pass_count": 10,
  "validation_failure_count": 0,
  "stable_review_approval_required": true,
  "stable_review_authorized": false,
  "dry_run": true,
  "advisory_only": true,
  "stable_promotion_authorized": false,
  "stable_routing_enabled": false,
  "checks": [
    {
      "category": "stable_use_threshold",
      "status": "pass",
      "summary": "Successful temporary uses meet the stable-review threshold (10/10).",
      "evidence_refs": ["run_treatment"],
      "blockers": [],
      "warnings": []
    }
  ],
  "skill_receipt": {},
  "negative_evidence": {},
  "blockers": [],
  "warnings": ["approval", "reversibility"],
  "next_steps": [
    "Use this report as advisory stable-review evidence only.",
    "Record maintainer approval before any future candidate-to-stable workflow.",
    "Keep stable routing disabled until a separate human-approved stable workflow exists."
  ],
  "run_logs_mutated": false,
  "candidate_ledger_mutated": false,
  "resolution_ledger_mutated": false,
  "durable_skills_mutated": false,
  "registry_mutated": false,
  "governor_steering_enabled": false
}
```

Allowed outcomes are `ready_for_stable_review`, `needs_more_evidence`, `blocked`, and `already_stable`. `ready_for_stable_review` means candidate promotion is recorded, the stable-use threshold is met, no validation/repair/duplicate/negative evidence blocks review, no same-name durable registry conflict exists, and no receipt proof category is blocked. It is still advisory review evidence only: stable review is not authorized by the report, stable promotion remains unauthorized, and stable routing remains disabled. `needs_more_evidence` covers missing candidate promotion or too few successful temporary uses. `blocked` covers blocked/quarantined candidates, duplicate evidence, negative evidence, durable registry name conflicts, or blocked receipt proof. `already_stable` reports ledger state only and does not change routing.

## Stable Routing Policy

V1 stable routing is explicitly deferred. `stable_routing_enabled` must remain `false` in stable-readiness and candidate-decision reports, and managed-prefix writes must keep `stable_routing_policy: "stable_routing_unchanged"`. The v1 local-use checklist reports `stable_routing_policy: "deferred_for_v1"` to make the release policy visible to operators. Positive stable routing requires a separate post-v1 human-approved workflow and route visibility in `run`, `run --json`, and `explain`.

## Candidate Decision Summary

`skill-agent candidate-decision <candidate-id>` emits a read-only `CandidateDecisionReport`. It is a compact operator index over existing proof surfaces, not a new authority layer. The report builds `stable-readiness`, then summarizes its nested `skill-receipt`, `candidate-usefulness`, `admit-candidate` preview, and `negative-evidence` proof into one advisory next decision.

Allowed decisions are `ask_human`, `test_more`, `deny`, and `defer`.

- `ask_human` means the next useful action is human review, candidate promotion evidence, or exact digest-bound approval.
- `test_more` means candidate utility, lifecycle, validation, or source evidence is still incomplete and should be gathered or repaired before asking for stable review.
- `deny` means duplicate, block, durable registry conflict, reject, or other negative evidence should keep the candidate out of stable review until explicitly resolved.
- `defer` means the strongest current proof still depends on intentionally unavailable authority, such as dependency installation support, durable install/copy, stable promotion, or stable routing.

Each `why` item cites a `source_report`, `signal`, `status`, summary, evidence refs, blockers, and warnings. The report also includes `next_command`, currently `skill-agent stable-readiness <candidate-id>`, so the operator can inspect the underlying stable-review rehearsal.

```json
{
  "candidate_id": "candidate_abc123def456",
  "skill_name": "argument-clustering",
  "capability": "argument clustering",
  "decision": "ask_human",
  "decision_reason": "Human review or exact digest-bound approval is missing.",
  "allowed_decisions": ["ask_human", "test_more", "deny", "defer"],
  "advisory_only": true,
  "approval_granted": false,
  "install_authorized": false,
  "stable_review_authorized": false,
  "stable_promotion_authorized": false,
  "stable_routing_enabled": false,
  "permission_widening_authorized": false,
  "governor_steering_enabled": false,
  "why": [
    {
      "source_report": "stable-readiness",
      "signal": "stable_readiness",
      "status": "ready_for_stable_review",
      "summary": "Candidate is ready for human stable review, but this report does not authorize stable promotion or routing.",
      "evidence_refs": [],
      "blockers": ["stable_review_authorization_unavailable", "stable_routing_disabled"],
      "warnings": []
    }
  ],
  "next_command": "skill-agent stable-readiness candidate_abc123def456",
  "source_reports": ["stable-readiness", "skill-receipt", "candidate-usefulness", "admit-candidate", "negative-evidence"],
  "run_logs_mutated": false,
  "candidate_ledger_mutated": false,
  "resolution_ledger_mutated": false,
  "checkpoint_ledger_mutated": false,
  "durable_skills_mutated": false,
  "registry_mutated": false
}
```

The command does not append input resolutions, checkpoint evidence, run logs, candidate ledgers, or registries. It does not approve, install, copy into durable `skills/`, mark candidates stable, enable stable routing, widen permissions, or steer the governor.

## Negative Evidence

`skill-agent negative-evidence` is a read-only report over preserved unfavorable or limiting evidence. It reads `runs/input_request_resolutions.json` and `runs/skill_candidate_ledger.json` to surface rejected, deferred, blocked, and repair-class input request resolutions plus blocked, quarantined, duplicate, or repair-required candidate records. It does not append resolutions, rewrite run logs, mutate candidate ledgers, copy or install durable skills, mutate the registry, create snapshots, create staging files, widen permissions, or steer the governor.

```json
{
  "runs_dir": "runs",
  "candidate_id": null,
  "evidence_count": 2,
  "counts_by_type": {
    "resolution_defer": 1,
    "resolution_reject": 1
  },
  "items": [
    {
      "id": "resolution_abc123",
      "evidence_type": "resolution_reject",
      "candidate_id": "candidate_abc123def456",
      "skill_name": null,
      "input_request_id": "inputreq_abc123",
      "decision": "reject_candidate",
      "resolution_class": "reject",
      "status": "resolved",
      "reason": "Temporary evidence is ready for human promotion review.",
      "notes": "Do not promote this candidate.",
      "source": "runs/input_request_resolutions.json",
      "evidence_refs": ["run_abc123"],
      "remaining_blocked_scope": "durable promotion only",
      "created_at": "2026-06-03T12:00:00"
    }
  ],
  "dry_run": true,
  "run_logs_mutated": false,
  "candidate_ledger_mutated": false,
  "resolution_ledger_mutated": false,
  "durable_skills_mutated": false,
  "registry_mutated": false,
  "governor_steering_enabled": false
}
```

Negative evidence types are additive. Current types include `resolution_reject`, `resolution_defer`, `resolution_block`, `resolution_repair`, `candidate_blocked`, `candidate_repair_required`, and `candidate_duplicate`. The optional `--candidate-id` filter limits items to evidence tied to one candidate.

## Evidence Checkpoint

`skill-agent evidence-checkpoint` creates or verifies a local hash-chain over core evidence files under `runs/`. The current scope excludes eval reports, lock files, temporary checkpoint writes, and `runs/evidence_checkpoints.json` itself. It includes run logs, candidate/input-request ledgers, run artifacts, admission snapshots/staging evidence, and managed-prefix acceptance evidence when present. It is local tamper-evidence only; it does not sign evidence, prove trust, approve durable admission, mutate run logs, mutate candidate or resolution ledgers, copy or install durable skills, mutate the registry, widen permissions, or steer the governor.

```json
{
  "runs_dir": "runs",
  "ledger_path": "runs/evidence_checkpoints.json",
  "mode": "create",
  "outcome": "checkpoint_appended",
  "dry_run": false,
  "scope": "runs_core",
  "checkpoint_id": "checkpoint_abc123def456",
  "checkpoint_hash_algorithm": "sha256",
  "checkpoint_hash": "abc123...",
  "previous_checkpoint_hash": null,
  "latest_checkpoint_hash": "abc123...",
  "evidence_file_count": 3,
  "evidence_files": [
    {
      "path": "run_20260603_120000_abcd1234.json",
      "sha256": "def456...",
      "size_bytes": 1024
    }
  ],
  "checkpoint_count": 1,
  "checkpoints_verified": 0,
  "chain_valid": true,
  "current_evidence_matches_latest": true,
  "blockers": [],
  "warnings": [],
  "next_steps": [
    "Use this checkpoint hash as local tamper-evidence only."
  ],
  "checkpoint_ledger_mutated": true,
  "run_logs_mutated": false,
  "candidate_ledger_mutated": false,
  "resolution_ledger_mutated": false,
  "durable_skills_mutated": false,
  "registry_mutated": false,
  "governor_steering_enabled": false
}
```

Allowed create outcomes are `checkpoint_ready`, `checkpoint_appended`, and `blocked`. `checkpoint_ready` is the default dry-run result and writes nothing. `checkpoint_appended` appends one record to `runs/evidence_checkpoints.json` only. `blocked` means the existing chain is invalid and a new checkpoint was not appended.

With `--verify`, allowed outcomes are `verified` and `blocked`. `verified` means every checkpoint hash links to the previous checkpoint and current evidence matches the latest checkpoint. `blocked` means the chain or current evidence changed, with blockers such as `checkpoint_hash_mismatch:<id>`, `checkpoint_previous_hash_mismatch:<id>`, `checkpoint_ledger_empty`, or `current_evidence_differs_from_latest_checkpoint`.

## Evidence Governor

`skill-agent evidence-governor <candidate-id>` is a read-only advisory report for one candidate. It composes `skill-receipt`, `negative-evidence`, and `evidence-checkpoint --verify` surfaces into a deterministic recommendation. Allowed recommendations are `ask`, `test_more`, `deny`, and `defer`. The command never grants approval, authorizes install/copy, promotes candidates, widens permissions, changes routing, rewrites evidence, or enables active governor steering.

```json
{
  "candidate_id": "candidate_abc123def456",
  "skill_name": "argument-clustering",
  "recommendation": "ask",
  "recommendation_reason": "Human review or exact plan-digest approval is missing.",
  "allowed_recommendations": ["ask", "test_more", "deny", "defer"],
  "dry_run": true,
  "advisory_only": true,
  "approval_granted": false,
  "install_authorized": false,
  "promotion_authorized": false,
  "permission_widening_authorized": false,
  "route_steering_enabled": false,
  "signals": [
    {
      "name": "receipt:approval",
      "status": "missing",
      "summary": "Human review or exact plan-digest approval is still missing.",
      "evidence_refs": ["def456..."],
      "blockers": ["plan_digest_approval_missing"],
      "warnings": []
    }
  ],
  "skill_receipt": {},
  "negative_evidence": {},
  "evidence_checkpoint": {},
  "blockers": ["receipt:approval:plan_digest_approval_missing"],
  "warnings": [],
  "next_steps": [
    "Ask a human for the missing review or exact digest-bound approval."
  ],
  "run_logs_mutated": false,
  "candidate_ledger_mutated": false,
  "resolution_ledger_mutated": false,
  "checkpoint_ledger_mutated": false,
  "durable_skills_mutated": false,
  "registry_mutated": false,
  "governor_steering_enabled": false
}
```

Recommendation rules are deterministic and advisory. Reject or block evidence recommends `deny`. Missing or blocked utility proof, missing checkpoint proof, or other incomplete proof recommends `test_more`. Missing human review or exact digest-bound approval recommends `ask`. If the strongest available proof is present but write-mode activation or rollback execution remains absent, the recommendation is `defer`. The report is not an approval record and is not consulted by routing or durable admission commands.

## Shadow Activation Plan

`skill-agent shadow-activation-plan <candidate-id>` is a read-only plan for future managed-prefix activation. It composes `admit-candidate --dry-run` evidence with a content-addressed store path, profile generation, activation pointer, previous generation, rollback target, and shadow plan digest. It does not create the managed prefix, write a store object, switch an activation pointer, rewrite run logs, mutate candidate or resolution ledgers, copy or install durable skills, mutate the registry, widen permissions, or steer the governor.

```json
{
  "candidate_id": "candidate_abc123def456",
  "skill_name": "argument-clustering",
  "outcome": "ready_for_shadow_activation_preview",
  "ready_for_shadow_activation_preview": true,
  "dry_run": true,
  "mutation_supported": false,
  "managed_prefix": "runs/managed_shadow",
  "managed_prefix_exists": false,
  "store_dir": "runs/managed_shadow/store/sha256-abc123.../skills/argument-clustering",
  "store_skill_path": "runs/managed_shadow/store/sha256-abc123.../skills/argument-clustering/SKILL.md",
  "profile_name": "default",
  "profile_dir": "runs/managed_shadow/profiles/default",
  "activation_pointer": "runs/managed_shadow/profiles/default/current",
  "planned_generation": 1,
  "generation_dir": "runs/managed_shadow/profiles/default/generations/1",
  "generation_skill_path": "runs/managed_shadow/profiles/default/generations/1/skills/argument-clustering/SKILL.md",
  "previous_generation": null,
  "rollback_target": null,
  "source_sha256": "abc123...",
  "durable_plan_digest": "def456...",
  "shadow_plan_digest_algorithm": "sha256",
  "shadow_plan_digest": "789abc...",
  "collision_policy": "shadow_managed_prefix_only",
  "activation_policy": "profile_pointer_switch",
  "canary_scope": "manual",
  "durable_admission_preview": {},
  "blockers": [],
  "warnings": [],
  "next_steps": [
    "Use this as a dry-run activation plan only; shadow-managed-write owns managed-prefix mutation."
  ],
  "managed_prefix_mutated": false,
  "profile_mutated": false,
  "run_logs_mutated": false,
  "candidate_ledger_mutated": false,
  "resolution_ledger_mutated": false,
  "durable_skills_mutated": false,
  "registry_mutated": false,
  "governor_steering_enabled": false
}
```

Allowed outcomes are `ready_for_shadow_activation_preview` and `blocked`. A plan can become ready only when the nested durable admission preview is unblocked. Existing managed-prefix generations may be read to calculate `previous_generation`, `planned_generation`, and `rollback_target`, but no generation directories, store files, profile pointers, or durable `skills/` files are created.

## Shadow Rollback Plan

`skill-agent shadow-rollback-plan <candidate-id>` is a read-only verifier for future managed-prefix rollback. It composes `shadow-activation-plan` evidence with the current activation pointer and existing profile generations to prove whether a later write-mode activation could restore the previous generation. It does not create the managed prefix, write a store object, switch an activation pointer, rewrite run logs, mutate candidate or resolution ledgers, copy or install durable skills, mutate the registry, widen permissions, or steer the governor.

```json
{
  "candidate_id": "candidate_abc123def456",
  "skill_name": "argument-clustering",
  "outcome": "rollback_verifiable",
  "rollback_verifiable": true,
  "dry_run": true,
  "mutation_supported": false,
  "managed_prefix": "runs/managed_shadow",
  "profile_name": "default",
  "profile_dir": "runs/managed_shadow/profiles/default",
  "activation_pointer": "runs/managed_shadow/profiles/default/current",
  "activation_pointer_exists": true,
  "activation_pointer_target": "runs/managed_shadow/profiles/default/generations/3",
  "current_generation": 3,
  "planned_generation": 4,
  "rollback_generation": 3,
  "rollback_target": "runs/managed_shadow/profiles/default/generations/3",
  "rollback_target_exists": true,
  "shadow_plan_digest": "789abc...",
  "rollback_plan_digest_algorithm": "sha256",
  "rollback_plan_digest": "012def...",
  "shadow_activation_plan": {},
  "blockers": [],
  "warnings": [],
  "next_steps": [
    "Use this as rollback proof only; shadow-managed-write owns profile switching."
  ],
  "managed_prefix_mutated": false,
  "profile_mutated": false,
  "run_logs_mutated": false,
  "candidate_ledger_mutated": false,
  "resolution_ledger_mutated": false,
  "durable_skills_mutated": false,
  "registry_mutated": false,
  "governor_steering_enabled": false
}
```

Allowed outcomes are `rollback_verifiable` and `blocked`. A rollback plan can become verifiable only when the nested shadow activation plan is unblocked, an existing rollback generation directory is present, and the current activation pointer targets that rollback generation. If no previous generation exists, `rollback_generation_missing` blocks the plan. If the expected rollback target path is absent, `rollback_target_missing` blocks the plan. If the activation pointer is absent, `activation_pointer_missing` blocks the plan. If the pointer targets a different path, `activation_pointer_target_mismatch` blocks the plan. Existing activation pointers may be read as symlinks or text pointer files, but no pointer is created or changed.

## Shadow Activation Acceptance

`skill-agent shadow-activation-acceptance <candidate-id>` is a controlled acceptance harness for future managed-prefix write mode. It composes `shadow-activation-plan` evidence with a run-scoped acceptance prefix. By default it only reports the acceptance paths. With `--prepare-acceptance-evidence`, it may create or reuse matching files under `runs/shadow_activation_acceptance/` or another `--acceptance-prefix` inside `--runs-dir`, copy the source `SKILL.md` into an acceptance store and generation, simulate activation pointer switching, and restore the pointer to the rollback generation. It can recover an acceptance pointer that was already left on the planned generation, and it blocks rather than overwriting conflicting acceptance files or unexpected pointer targets. It refuses prefixes outside `--runs-dir`. It does not create or mutate the real managed prefix, rewrite run logs, mutate candidate or resolution ledgers, copy or install durable skills, mutate the registry, widen permissions, or steer the governor.

```json
{
  "candidate_id": "candidate_abc123def456",
  "skill_name": "argument-clustering",
  "outcome": "accepted",
  "acceptance_prepared": true,
  "activation_verified": true,
  "rollback_verified": true,
  "dry_run": true,
  "mutation_supported": true,
  "planned_managed_prefix": "runs/managed_shadow",
  "acceptance_prefix": "runs/shadow_activation_acceptance/candidate_abc123_789abc",
  "acceptance_prefix_exists": true,
  "profile_name": "default",
  "source_skill_path": "runs/artifacts/run_id/skills/argument-clustering/SKILL.md",
  "source_sha256": "abc123...",
  "acceptance_store_skill_path": "runs/shadow_activation_acceptance/candidate_abc123_789abc/store/sha256-abc123.../skills/argument-clustering/SKILL.md",
  "acceptance_generation_skill_path": "runs/shadow_activation_acceptance/candidate_abc123_789abc/profiles/default/generations/4/skills/argument-clustering/SKILL.md",
  "acceptance_activation_pointer": "runs/shadow_activation_acceptance/candidate_abc123_789abc/profiles/default/current",
  "previous_generation": 3,
  "planned_generation": 4,
  "acceptance_rollback_target": "runs/shadow_activation_acceptance/candidate_abc123_789abc/profiles/default/generations/3",
  "activation_pointer_before": null,
  "activation_pointer_after_activation": "runs/shadow_activation_acceptance/candidate_abc123_789abc/profiles/default/generations/4",
  "activation_pointer_after_rollback": "runs/shadow_activation_acceptance/candidate_abc123_789abc/profiles/default/generations/3",
  "interrupted_activation_recovered": false,
  "acceptance_conflict_detected": false,
  "shadow_plan_digest": "789abc...",
  "acceptance_plan_digest_algorithm": "sha256",
  "acceptance_plan_digest": "fedcba...",
  "shadow_activation_plan": {},
  "blockers": [],
  "warnings": [],
  "next_steps": [
    "Use this as controlled-prefix acceptance evidence only; durable skills remain untouched."
  ],
  "acceptance_prefix_mutated": true,
  "managed_prefix_mutated": false,
  "profile_mutated": false,
  "run_logs_mutated": false,
  "candidate_ledger_mutated": false,
  "resolution_ledger_mutated": false,
  "durable_skills_mutated": false,
  "registry_mutated": false,
  "governor_steering_enabled": false
}
```

Allowed outcomes are `planned`, `accepted`, and `blocked`. `planned` means the acceptance paths and digest are inspectable but no acceptance evidence was written. `accepted` means the run-scoped harness copied or reused the source in an acceptance store/generation, switched the acceptance pointer to the planned generation, restored it to the rollback generation, and verified both pointer states. `blocked` means the harness could not prepare evidence, for example because the acceptance prefix was outside `--runs-dir`, the source hash drifted, rollback generation evidence was missing, existing acceptance files conflicted with the expected source bytes, or the acceptance pointer started at an unexpected target. A pointer already targeting the planned generation is treated as an interrupted activation and must be restored to the rollback target before the report can be accepted.

## Shadow Write Gate

`skill-agent shadow-write-gate <candidate-id>` is a read-only verifier for the future human-approved managed-prefix write boundary. It composes `shadow-activation-plan`, `shadow-rollback-plan`, and `shadow-activation-acceptance` evidence, then verifies that the already prepared acceptance evidence still matches the expected source hash, content-addressed store copy, profile generation copy, rollback marker, restored acceptance pointer, and supplied exact `--acceptance-plan-digest`. Without that expected digest it remains an inspection-only blocked report. The command does not prepare acceptance evidence, create or mutate the real managed prefix, rewrite run logs, mutate candidate or resolution ledgers, copy or install durable skills, mutate the registry, widen permissions, or steer the governor.

```json
{
  "candidate_id": "candidate_abc123def456",
  "skill_name": "argument-clustering",
  "outcome": "ready_for_human_managed_prefix_write",
  "ready_for_human_managed_prefix_write": true,
  "dry_run": true,
  "mutation_supported": false,
  "managed_prefix": "runs/managed_shadow",
  "acceptance_prefix": "runs/shadow_activation_acceptance/candidate_abc123_789abc",
  "profile_name": "default",
  "source_skill_path": "runs/artifacts/run_id/skills/argument-clustering/SKILL.md",
  "source_sha256": "abc123...",
  "source_hash_verified": true,
  "acceptance_store_skill_path": "runs/shadow_activation_acceptance/candidate_abc123_789abc/store/sha256-abc123.../skills/argument-clustering/SKILL.md",
  "acceptance_store_verified": true,
  "acceptance_generation_skill_path": "runs/shadow_activation_acceptance/candidate_abc123_789abc/profiles/default/generations/4/skills/argument-clustering/SKILL.md",
  "acceptance_generation_verified": true,
  "acceptance_activation_pointer": "runs/shadow_activation_acceptance/candidate_abc123_789abc/profiles/default/current",
  "acceptance_pointer_restored": true,
  "acceptance_pointer_target": "runs/shadow_activation_acceptance/candidate_abc123_789abc/profiles/default/generations/3",
  "acceptance_rollback_target": "runs/shadow_activation_acceptance/candidate_abc123_789abc/profiles/default/generations/3",
  "acceptance_rollback_marker_verified": true,
  "durable_plan_digest": "def456...",
  "shadow_plan_digest": "789abc...",
  "rollback_plan_digest": "012def...",
  "acceptance_plan_digest_algorithm": "sha256",
  "acceptance_plan_digest": "fedcba...",
  "expected_acceptance_plan_digest": "fedcba...",
  "acceptance_plan_digest_verified": true,
  "shadow_activation_plan": {},
  "shadow_rollback_plan": {},
  "shadow_activation_acceptance": {},
  "blockers": [],
  "warnings": [],
  "next_steps": [
    "Use this report as a human approval gate only; no managed-prefix write is enabled."
  ],
  "acceptance_prefix_mutated": false,
  "managed_prefix_mutated": false,
  "profile_mutated": false,
  "run_logs_mutated": false,
  "candidate_ledger_mutated": false,
  "resolution_ledger_mutated": false,
  "durable_skills_mutated": false,
  "registry_mutated": false,
  "governor_steering_enabled": false
}
```

Allowed outcomes are `ready_for_human_managed_prefix_write` and `blocked`. `ready_for_human_managed_prefix_write` means the exact durable plan, shadow plan, rollback plan, supplied acceptance digest, and prepared acceptance evidence are all inspectable and hash-consistent, but `shadow-write-gate` itself has not mutated the managed prefix. `blocked` means at least one precondition is missing or stale, such as missing acceptance files, source hash drift, an unrestored acceptance pointer, missing rollback marker, missing rollback evidence in the real managed prefix, `acceptance_plan_digest_expected_missing`, or `acceptance_plan_digest_mismatch`.

## Shadow Managed Write

`skill-agent shadow-managed-write <candidate-id>` emits a `ShadowManagedWriteReport`. It is the first human-approved real write surface, but it is confined to the configured shadow managed prefix. Dry-run mode composes the skill receipt, evidence checkpoint verification, and shadow write gate, then emits a `managed_write_plan_digest`. Non-dry-run mode requires exact expected source/durable/shadow/rollback/acceptance/managed-write digests, latest checkpoint hash, and a separate non-expired `approve_review` resolution whose notes include the matching `managed_write_plan_digest=<digest>`. When all gates pass, it may create or reuse only the managed store `SKILL.md`, profile generation `SKILL.md`, activation pointer, and managed-prefix-local write receipt. It does not copy or install into durable `skills/`, mutate registry or ledgers, widen permissions, enable stable routing, or steer the governor.

```json
{
  "candidate_id": "candidate_abc123def456",
  "skill_name": "argument-clustering",
  "outcome": "managed_prefix_write_applied",
  "ready_for_managed_prefix_write": true,
  "dry_run": false,
  "mutation_supported": true,
  "managed_prefix": "runs/managed_shadow",
  "acceptance_prefix": "runs/shadow_activation_acceptance/candidate_abc123_789abc",
  "profile_name": "default",
  "source_skill_path": "runs/artifacts/run_id/skills/argument-clustering/SKILL.md",
  "source_sha256": "abc123...",
  "source_hash_verified": true,
  "store_skill_path": "runs/managed_shadow/store/sha256-abc123.../skills/argument-clustering/SKILL.md",
  "generation_skill_path": "runs/managed_shadow/profiles/default/generations/4/skills/argument-clustering/SKILL.md",
  "activation_pointer": "runs/managed_shadow/profiles/default/current",
  "rollback_target": "runs/managed_shadow/profiles/default/generations/3",
  "durable_plan_digest": "def456...",
  "shadow_plan_digest": "789abc...",
  "rollback_plan_digest": "012def...",
  "acceptance_plan_digest": "fedcba...",
  "managed_write_plan_digest_algorithm": "sha256",
  "managed_write_plan_digest": "456abc...",
  "expected_source_sha256": "abc123...",
  "expected_durable_plan_digest": "def456...",
  "expected_shadow_plan_digest": "789abc...",
  "expected_rollback_plan_digest": "012def...",
  "expected_acceptance_plan_digest": "fedcba...",
  "expected_managed_write_plan_digest": "456abc...",
  "expected_checkpoint_hash": "checkpoint123...",
  "expected_source_sha256_verified": true,
  "durable_plan_digest_verified": true,
  "shadow_plan_digest_verified": true,
  "rollback_plan_digest_verified": true,
  "acceptance_plan_digest_verified": true,
  "managed_write_plan_digest_verified": true,
  "checkpoint_verified": true,
  "checkpoint_hash_verified": true,
  "latest_checkpoint_hash": "checkpoint123...",
  "write_approval_id": "resolution_write_approval",
  "write_approval_digest": "456abc...",
  "write_approval_expires_at": "2026-06-05T00:00:00+00:00",
  "write_approval_present": true,
  "write_approval_verified": true,
  "exact_expected_values_verified": true,
  "receipt_acceptable": true,
  "receipt_reversibility_accepted": true,
  "shadow_write_gate_ready": true,
  "rollback_ready": true,
  "write_receipt_path": "runs/managed_shadow/profiles/default/write_receipts/456abc....json",
  "store_verified": true,
  "generation_verified": true,
  "activation_pointer_target": "runs/managed_shadow/profiles/default/generations/4",
  "activation_pointer_updated": true,
  "activation_pointer_verified": true,
  "rollback_target_verified": true,
  "already_applied": false,
  "interrupted_activation_recovered": false,
  "managed_prefix_write_policy": "managed_prefix_only_write",
  "profile_activation_policy": "profile_pointer_switch",
  "rollback_policy": "profile_pointer_rollback",
  "stable_routing_policy": "stable_routing_unchanged",
  "governor_policy": "governor_advisory_only",
  "skill_receipt": {},
  "evidence_checkpoint": {},
  "shadow_write_gate": {},
  "blockers": [],
  "warnings": [],
  "next_steps": ["Managed-prefix write applied; durable skills and stable routing remain unchanged."],
  "acceptance_prefix_mutated": false,
  "managed_prefix_mutated": true,
  "profile_mutated": true,
  "run_logs_mutated": false,
  "candidate_ledger_mutated": false,
  "resolution_ledger_mutated": false,
  "checkpoint_ledger_mutated": false,
  "durable_skills_mutated": false,
  "registry_mutated": false,
  "governor_steering_enabled": false
}
```

Allowed outcomes are `approval_required`, `blocked`, `ready_for_managed_prefix_write`, `managed_prefix_write_applied`, and `already_applied`. `approval_required` means the managed-write digest is available but the separate write approval is missing, expired, or mismatched. `ready_for_managed_prefix_write` means dry-run proof is complete and all supplied expected values match without mutation. `managed_prefix_write_applied` means the confined store/generation/pointer/receipt write succeeded. `already_applied` means a prior matching receipt, store, generation, and pointer state were verified. In every outcome, `durable_skills_mutated`, `registry_mutated`, `candidate_ledger_mutated`, `resolution_ledger_mutated`, `run_logs_mutated`, and `governor_steering_enabled` remain `false`; stable routing remains governed by `stable_routing_policy: "stable_routing_unchanged"`.

## Input Request

Input requests normalize human-decision boundaries across run logs, safety decisions, repair requests, candidate review queues, and admission dry runs. They are evidence and queue records only; they do not approve, promote, install, copy, route, or mutate durable skills.

```json
{
  "id": "inputreq_abc123def456",
  "kind": "promotion_approval",
  "status": "open",
  "title": "Review argument-clustering for candidate promotion",
  "reason": "Temporary evidence is ready for human promotion review.",
  "blocked_scope": "durable promotion only",
  "requested_decision": "Approve, repair, reject, or defer candidate promotion.",
  "options": ["approve_promotion", "repair_candidate", "reject_candidate", "defer"],
  "recommended_option": "approve_promotion",
  "evidence_refs": ["run_abc123"],
  "next_commands": [
    "skill-agent promote-candidate candidate_abc123 --reviewer <name> --notes <notes>"
  ],
  "related_run_id": null,
  "related_candidate_id": "candidate_abc123",
  "related_skill_request_id": null,
  "created_at": "2026-06-03T12:00:00"
}
```

Allowed kinds are `safety_approval`, `promotion_approval`, `durable_admission_review`, `repair_review`, `ambiguity_resolution`, and `missing_evidence`. Allowed statuses are `open`, `resolved`, and `blocked`. Requests synthesized from older run logs or candidate ledger entries use stable IDs and source evidence timestamps when available.

Input request queue items wrap a request with read-time source diagnostics:

```json
{
  "request": {
    "id": "inputreq_abc123def456",
    "kind": "promotion_approval",
    "status": "open",
    "title": "Review argument-clustering for candidate promotion",
    "reason": "Temporary evidence is ready for human promotion review.",
    "blocked_scope": "durable promotion only",
    "requested_decision": "Approve, repair, reject, or defer candidate promotion.",
    "options": ["approve_promotion", "repair_candidate", "reject_candidate", "defer"],
    "recommended_option": "approve_promotion",
    "evidence_refs": ["run_abc123"],
    "next_commands": [
      "skill-agent promote-candidate candidate_abc123 --reviewer <name> --notes <notes>"
    ],
    "related_run_id": null,
    "related_candidate_id": "candidate_abc123",
    "related_skill_request_id": null,
    "created_at": "2026-06-03T12:00:00"
  },
  "sources": [
    {
      "source_type": "candidate_ledger",
      "source_path": "runs/skill_candidate_ledger.json",
      "source_detail": "candidate_abc123"
    }
  ]
}
```

Allowed source types are `run_log`, `candidate_ledger`, and `resolution_ledger`.

## Input Request Resolution

Resolution classifies a proposed human decision for an input request. Dry-run mode does not write run logs, candidate ledgers, resolution ledgers, durable skills, or governor state. Non-dry-run mode appends one record to `runs/input_request_resolutions.json` and does not mutate the source run log or candidate ledger.

```json
{
  "dry_run": true,
  "input_request_id": "inputreq_abc123def456",
  "decision": "repair_candidate",
  "resolution_class": "repair",
  "proposed_status": "resolved",
  "reviewer": "Ada",
  "notes": "Reviewed evidence and requested repair.",
  "request": {
    "id": "inputreq_abc123def456",
    "kind": "repair_review",
    "status": "open",
    "title": "Review repairs for argument-clustering",
    "reason": "Candidate has validation failures or repair requirements.",
    "blocked_scope": "durable promotion and candidate admission",
    "requested_decision": "Repair, reject, or defer this candidate.",
    "options": ["repair_candidate", "reject_candidate", "defer"],
    "recommended_option": "repair_candidate",
    "evidence_refs": ["run_abc123"],
    "next_commands": ["Inspect candidate repair requirements and source evidence."],
    "related_run_id": null,
    "related_candidate_id": "candidate_abc123",
    "related_skill_request_id": null,
    "created_at": "2026-06-03T12:00:00"
  },
  "sources": [
    {
      "source_type": "candidate_ledger",
      "source_path": "runs/skill_candidate_ledger.json",
      "source_detail": "candidate_abc123"
    }
  ],
  "remaining_blocked_scope": "durable promotion and candidate admission",
  "next_steps": ["Repair the candidate evidence, then rerun the originating command."],
  "run_logs_mutated": false,
  "candidate_ledger_mutated": false,
  "resolution_ledger_mutated": true,
  "durable_skills_mutated": false,
  "governor_steering_enabled": false
}
```

The append-only resolution ledger stores historical decision evidence:

```json
{
  "schema_version": 1,
  "resolutions": [
    {
      "id": "resolution_abc123def456",
      "input_request_id": "inputreq_abc123def456",
      "decision": "repair_candidate",
      "resolution_class": "repair",
      "status": "resolved",
      "reviewer": "Ada",
      "notes": "Reviewed evidence and requested repair.",
      "source_request": {
        "id": "inputreq_abc123def456",
        "kind": "repair_review",
        "status": "open",
        "title": "Review repairs for argument-clustering",
        "reason": "Candidate has validation failures or repair requirements.",
        "blocked_scope": "durable promotion and candidate admission",
        "requested_decision": "Repair, reject, or defer this candidate.",
        "options": ["repair_candidate", "reject_candidate", "defer"],
        "recommended_option": "repair_candidate",
        "evidence_refs": ["run_abc123"],
        "next_commands": ["Inspect candidate repair requirements and source evidence."],
        "related_run_id": null,
        "related_candidate_id": "candidate_abc123",
        "related_skill_request_id": null,
        "created_at": "2026-06-03T12:00:00"
      },
      "sources": [
        {
          "source_type": "candidate_ledger",
          "source_path": "runs/skill_candidate_ledger.json",
          "source_detail": "candidate_abc123"
        }
      ],
      "remaining_blocked_scope": "durable promotion and candidate admission",
      "next_steps": ["Repair the candidate evidence, then rerun the originating command."],
      "created_at": "2026-06-03T12:00:00"
    }
  ]
}
```

Allowed resolution classes are `approve`, `revise`, `repair`, `reject`, `defer`, `block`, `recover`, `merge`, and `keep_separate`. Decisions must be one of the input request's declared `options`. `proposed_status` describes the input request state after the decision: `defer` remains `open`, while explicit decisions are `resolved`; `remaining_blocked_scope` describes any underlying work that still cannot proceed. `skill-agent input-requests` reads the latest ledger record per input request as an overlay, filters `resolved` requests from active output, and leaves deferred requests visible as `open`.

## Admission Plan

Admission plans are output-only dry-run reports. They inspect candidate ledger evidence, run logs, run-scoped temporary skill artifacts, and the durable registry, but they do not write the ledger, copy files, install skills, admit registry records, steer the governor, or promote anything to stable.

```json
{
  "candidate_id": "candidate_abc123def456",
  "outcome": "ready_for_durable_review",
  "ready_for_durable_review": true,
  "dry_run": true,
  "auto_promotion_enabled": false,
  "durable_skill_installed": false,
  "ledger_mutated": false,
  "registry_mutated": false,
  "governor_steering_enabled": false,
  "selected_source_artifact": "runs/artifacts/run_id/skills/argument-clustering/SKILL.md",
  "blockers": [],
  "warnings": [],
  "next_steps": ["Prepare human durable admission review."],
  "input_request": {
    "id": "inputreq_abc123def456",
    "kind": "durable_admission_review",
    "status": "open",
    "title": "Review durable admission for argument-clustering",
    "reason": "Candidate evidence is ready for human durable admission review.",
    "blocked_scope": "durable skill install/copy",
    "requested_decision": "Approve durable admission review, request repair, block, or defer.",
    "options": ["approve_review", "repair_candidate", "block", "defer"],
    "recommended_option": "approve_review",
    "evidence_refs": ["run_abc123"],
    "next_commands": ["Prepare human durable admission review."],
    "related_run_id": null,
    "related_candidate_id": "candidate_abc123",
    "related_skill_request_id": null,
    "created_at": "2026-06-03T12:00:00"
  }
}
```

Allowed outcomes are `ready_for_durable_review`, `needs_promotion_approval`, `evidence_incomplete`, and `blocked`. Missing candidates or unreadable ledgers are command errors; missing run logs, missing source paths, missing source files, source validation failures, permission widening, scripted candidates, and same-name durable collisions are report blockers.

Durable admission workflow design lives in `docs/plans/durable-admission-workflow-design-2026-06-03.md`. That workflow treats `ready_for_durable_review` and `approve_review` resolution evidence as review checkpoints only. They are not durable install/copy approval, registry admission, stable promotion, permission widening, or governor steering.

## Durable Admission Preview

`admit-candidate --dry-run` previews the future durable admission mutation contract. It requires the existing admission-plan proof and reports what would be needed before a future write-mode command could exist. By default it does not copy, install, admit, mutate ledgers, mutate the registry, promote to stable, widen permissions, create snapshots, stage destination files, or steer the governor. With `--prepare-write-evidence`, it may create or reuse matching run-scoped evidence only under `runs/admission_snapshots/` and `runs/admission_staging/`. `--no-dry-run` exits with an error because durable admission mutation is intentionally unavailable.

Dry-run options:

- `--collision-policy block_existing` is the default and blocks same-name durable skills.
- `--collision-policy allow_replace_with_approval` may preview `replace_existing_skill` only when append-only `approve_review` evidence exists for the same candidate.
- `--permission-approval-id <resolution-id>` optionally names separate resolved approval evidence for permission widening. Without that evidence, permission widening remains blocked. Older dry-run callers may still pass the source `input_request_id`, but new records include a stable `resolution_<id>` value.
- `--plan-approval-id <resolution-id>` optionally pins the resolved `approve_review` record that approved the exact dry-run plan digest.
- `--prepare-write-evidence` retains the source snapshot and stages the destination copy under `runs/` only when the dry-run write plan is otherwise unblocked.
- `--expected-source-sha256 <sha256>` optionally pins evidence preparation to a previously reviewed source fingerprint. A mismatch blocks snapshot retention and staging.

Plan-digest approval notes must include `plan_digest=<sha256>` and `expires_at=<timestamp>`. The approval record must be a resolved `approve_review` resolution for a `durable_admission_review` input request related to the same candidate. If `--plan-approval-id` is omitted, the preview searches append-only resolution evidence for a matching non-expired approval. A source hash change, destination change, collision-policy change, permission-approval change, or evidence-preparation option change produces a different digest and invalidates the old approval for the new plan.

The nested permission/dependency diff packet is evidence only. It classifies declared permission classes (`read_files`, `write_files`, `network`, `secrets`, `execute_code`), declared tools, dependency declaration keys, and dependency names from `dependencies`, `requirements`, `packages`, and direct dependency/package entries in `dependency_lock`. A dependency declaration can include exact realization evidence through `dependency_realization` entries with `name`, `version`, and `sha256`. Exact realization clears `dependency_realization_missing`, but dependency install remains blocked by `dependency_install_unsupported` because installation is intentionally unsupported in this no-write contract.

`write_plan.dependency_install_contract` is the no-write dependency evidence contract. It reports `policy: "no_write_dependency_evidence_only"`, schema/digest metadata, `dependency_plan_digest`, optional `expected_dependency_plan_digest` verification, optional run-scoped `evidence_manifest_path` and manifest hash/created/retained booleans, optional evidence-only dependency approval fields, normalized dependency items, blockers, warnings, and hard boundary flags: `install_supported: false`, `install_attempted: false`, and `dependencies_installed: false`. Normalized dependency items carry the dependency `name`, declaration keys/sources, declared spec or version text when available, exact realization version/hash when available, status such as `unresolved` or `exact_realized`, and item warnings.

The dependency plan digest is deterministic and distinct from the durable admission plan digest. It binds the candidate, selected source path and SHA-256, target skill path, normalized dependency items, manifest path, and no-write policy constants; it excludes volatile approval state, manifest creation booleans, and timestamps. The durable admission `plan_digest` includes the stable dependency contract inputs plus dependency-evidence option choices so source, dependency, policy, or evidence-option drift invalidates prior plan approval.

With `--prepare-dependency-evidence`, `admit-candidate --dry-run` may create or reuse a deterministic manifest only under `runs/admission_dependency_evidence/<candidate_id>/<source_sha256>/dependency_plan.json`. The manifest records schema version, candidate/source/target identity, no-write policy constants, normalized dependency items, recorded dependency blockers, and `dependency_plan_digest`. Existing matching manifests are reused. Existing conflicting manifests block with `dependency_evidence_manifest_hash_mismatch` and are not overwritten. `dependency_realization_missing` and `dependency_install_unsupported` are recorded in the manifest but do not by themselves prevent the no-write manifest from being prepared. Source/read failures, source hash mismatch, expected dependency digest mismatch, manifest byte conflicts, path-escape checks, and unsafe admission/source blockers such as outside-run sources, scripted candidates, permission widening, parse failures, validation failures, quarantined candidates, or missing promotion evidence do prevent evidence writes.

`--dependency-approval-id` is an evidence-only review hook. The referenced append-only resolution record must be resolved `approve_review` evidence for a `durable_admission_review` input request related to the same candidate, and its notes must include `dependency_plan_digest=<sha256>` plus a non-expired `expires_at=<timestamp>`. Valid dependency approval sets the contract approval fields, but it does not authorize installation, remove `dependency_realization_missing` or `dependency_install_unsupported`, mutate durable skills or ledgers, admit to the registry, promote to stable, enable routing, or steer the governor.

```json
{
  "candidate_id": "candidate_abc123def456",
  "outcome": "approval_required",
  "ready_for_mutation_preview": false,
  "dry_run": true,
  "mutation_supported": false,
  "durable_skill_installed": false,
  "ledger_mutated": false,
  "registry_mutated": false,
  "resolution_ledger_mutated": false,
  "governor_steering_enabled": false,
  "source_skill_path": "runs/artifacts/run_id/skills/argument-clustering/SKILL.md",
  "source_sha256": "abc123...",
  "target_skill_dir": "skills/argument-clustering",
  "target_skill_path": "skills/argument-clustering/SKILL.md",
  "write_plan": {
    "operation": "blocked",
    "plan_digest_algorithm": "sha256",
    "plan_digest": "def456...",
    "plan_approval_id": null,
    "plan_approval_digest": null,
    "plan_approval_expires_at": null,
    "plan_approval_verified": false,
    "source_skill_path": "runs/artifacts/run_id/skills/argument-clustering/SKILL.md",
    "source_sha256": "abc123...",
    "target_skill_dir": "skills/argument-clustering",
    "target_skill_path": "skills/argument-clustering/SKILL.md",
    "snapshot_dir": "runs/admission_snapshots/candidate_abc123def456/abc123...",
    "snapshot_skill_path": "runs/admission_snapshots/candidate_abc123def456/abc123.../SKILL.md",
    "snapshot_sha256": "abc123...",
    "prepare_write_evidence": false,
    "expected_source_sha256": null,
    "source_hash_verified": true,
    "source_snapshot_retained": false,
    "destination_stage_dir": "runs/admission_staging/candidate_abc123def456/abc123.../skills/argument-clustering",
    "destination_stage_skill_path": "runs/admission_staging/candidate_abc123def456/abc123.../skills/argument-clustering/SKILL.md",
    "destination_stage_sha256": null,
    "destination_stage_created": false,
    "collision_policy": "block_existing",
    "permission_policy": "block_widening_without_approval",
    "permission_approval_id": null,
    "permission_dependency_diff": {
      "permission_changes": [
        {
          "class_name": "network",
          "current_enabled": false,
          "requested_enabled": false,
          "change": "unchanged",
          "approval_required": false
        }
      ],
      "added_permission_classes": [],
      "removed_permission_classes": [],
      "added_tools": [],
      "removed_tools": [],
      "permission_approval_required": false,
      "dependency_diff": {
        "dependencies_declared": false,
        "declaration_keys": [],
        "exact_realization_available": true,
        "added": [],
        "removed": [],
        "realized": [],
        "unresolved": [],
        "blockers": [],
        "warnings": []
      },
      "blockers": [],
      "warnings": []
    },
    "replacement_approved": false,
    "permission_widening_approved": false,
    "durable_skill_installed": false,
    "ledger_mutated": false,
    "registry_mutated": false,
    "resolution_ledger_mutated": false,
    "source_snapshot_created": false,
    "governor_steering_enabled": false,
    "blockers": ["durable_review_resolution_missing"],
    "warnings": []
  },
  "required_human_records": [
    "promotion_approved_by",
    "promotion_approved_at",
    "durable_admission_review approve_review resolution",
    "plan digest approval resolution"
  ],
  "blockers": ["durable_review_resolution_missing"],
  "warnings": [],
  "next_steps": [
    "Resolve admission blockers and record required human review evidence.",
    "Rerun admit-candidate --dry-run before any future write-mode work."
  ],
  "admission_plan": {}
}
```

Allowed preview outcomes are `ready_for_mutation_preview`, `approval_required`, and `blocked`. Allowed write-plan operations are `copy_new_skill`, `replace_existing_skill`, and `blocked`. A preview can reach `ready_for_mutation_preview` only after `admission-plan` is ready or the only admission-plan blocker is a same-name collision explicitly handled by `allow_replace_with_approval`, the append-only input request resolution ledger contains resolved `approve_review` evidence for the same candidate, a non-expired approval record matches the exact plan digest, the permission/dependency diff has no blockers, and the write plan has no blockers. Dependency diff blockers include `dependency_realization_missing` when a dependency lacks hash-backed realization and `dependency_install_unsupported` when exact realization exists but install semantics are still intentionally absent.

Source snapshot retention and destination staging are opt-in dry-run evidence preparation steps. Without `--prepare-write-evidence`, `snapshot_dir`, `snapshot_skill_path`, `snapshot_sha256`, `destination_stage_dir`, and `destination_stage_skill_path` describe future evidence paths and all creation flags remain `false`. With `--prepare-write-evidence`, the command verifies the current source hash, verifies the exact plan-digest approval first, reuses matching existing evidence, creates missing run-scoped snapshot/staging files, and blocks rather than overwriting if an existing evidence file has a different hash.

Acceptance coverage for the future write mode lives in `tests/test_durable_admission_acceptance.py`. It proves source hash drift, snapshot path planning, run-scoped source retention, destination staging, collision approval, permission approval, exact plan-digest approval, and `--no-dry-run` rejection without copying into durable `skills/`, installing, or rewriting historical evidence.

## Capability Decision

```json
{
  "capability": "detect contradictions",
  "decision": "REQUEST_SKILL",
  "reason": "No existing skill met threshold for capability 'detect contradictions'.",
  "best_match": {"skill_name": "compare-claims", "score": 0.35, "coverage": "partial"},
  "ranked_candidates": [
    {
      "skill_name": "compare-claims",
      "score": 0.35,
      "coverage": "partial",
      "selected": false,
      "route_reason": {
        "matched_terms": ["claims"],
        "schema_overlap": ["claims"],
        "risk_result": "risk=low",
        "permission_result": "all permissions false",
        "status_result": "status=candidate; validation=manual",
        "compatibility_result": "declared",
        "score": 0.35,
        "threshold": 0.55
      }
    }
  ],
  "risk_level": "low",
  "requires_human_approval": false
}
```

Allowed decisions are `USE_SKILL`, `REQUEST_SKILL`, `ASK_HUMAN`, and `ABORT_UNSAFE`. Temporary drafting is recorded under `skill_requests[].temporary_skill`, not as a separate route decision.

## Skill Repair Request

Repair requests are emitted when a generated temporary skill fails validation. The repair acceptance demo uses an explicitly medium-risk local-code capability so risk is not used as a proxy for text-task difficulty.

```json
{
  "id": "repairreq_001",
  "task_id": "task_001",
  "skill_request_id": "skillreq_001",
  "skill_name": "local-python-analysis",
  "failed_capability": "run local python analysis",
  "failed_skill_path": "runs/artifacts/run_id/skills/local-python-analysis/SKILL.md",
  "failure_reasons": ["non-scripted skills must be low risk"],
  "repair_objective": "Revise the temporary Markdown skill so it satisfies the validator while preserving the requested capability contract.",
  "constraints": [
    "Keep the repair Markdown-only.",
    "Do not add scripts, dependencies, network access, secrets, or code execution.",
    "Do not auto-load the repaired skill without a fresh validation pass."
  ],
  "status": "requested"
}
```

## Run Log

```json
{
  "schema_version": 3,
  "run_id": "a1b2c3d4",
  "task_id": "task_001",
  "result_category": "success",
  "exit_code": 0,
  "trace": ["PLANNING", "CHECKING_SKILLS", "ROUTE_COMPLETE", "RUN_LOG_WRITTEN"],
  "trace_events": [
    {"sequence": 1, "stage": "PLANNING", "message": "", "details": {"run_id": "a1b2c3d4"}}
  ],
  "execution_summary": {
    "loaded_skills": ["extract-claims"],
    "temporary_skills": [],
    "requested_skills": [],
    "repair_requested_skills": [],
    "script_executions": [],
    "failed_scripts": [],
    "safety_decisions": [],
    "result_category": "success"
  },
  "capability_decisions": [],
  "skills_loaded": [],
  "skill_requests": [],
  "skill_repair_requests": [],
  "script_executions": []
}
```

`run_id` identifies one execution and appears in the filename. `task_id` remains deterministic for the task text. Temporary generated skills live under `runs/artifacts/<run_id>/skills/...` and are only loaded through that run's registry overlay.

Result categories use this precedence: `unsafe_aborted`, `awaiting_human_approval`, `repair_requested`, `route_load_failed`, `script_failed`, `blocked_missing_skill`, `success`.

## Script Execution Log

Scripted skills are opt-in restricted local subprocesses, not a true sandbox. Logs cap stdout/stderr, parse successful stdout as JSON, validate it against `output_schema`, and categorize failures.

```json
{
  "skill_name": "count-words",
  "command": ["python", ".../count_words.py"],
  "returncode": 0,
  "stdout": "{\"word_count\": 6}",
  "stderr": "",
  "timed_out": false,
  "parsed_stdout": {"word_count": 6},
  "output_validated": true,
  "failure_category": null
}
```

Failure categories: `timeout`, `nonzero_exit`, `invalid_json`, `output_schema_mismatch`, and `output_too_large`.

## JSON CLI Surfaces

- `skill-agent run --json` emits run result data: IDs, exit code, result category, run-log path, execution summary, decisions, requests, repairs, input requests, loaded skills, rejected skills, trace events, and script executions.
- `skill-agent registry --json` emits `{ "accepted": [...], "rejected": [...] }`.
- `skill-agent health --json` is additive and includes v2 metrics such as result categories, temporary outcomes, repair counts, safety stops, human approval waits, route/load failures, script failure categories, and input request counts.
- `skill-agent input-requests --json` emits `{ "runs_dir": "...", "input_request_count": 0, "input_request_kind_counts": {}, "warnings": [], "input_requests": [], "input_request_items": [] }`. `input_requests` is the flat compatibility list; `input_request_items` includes source diagnostics.
- `skill-agent resolve-input-request --json` emits the resolution report for one input request and proposed decision. With `--dry-run`, it does not mutate local evidence. With `--no-dry-run`, it appends to `runs/input_request_resolutions.json` only.
- `skill-agent admit-candidate --dry-run --json` emits the durable admission preview report with its nested write plan. `--no-dry-run` is intentionally rejected.
- `skill-agent skill-receipt --json` emits the read-only proof bundle for one candidate, including nested candidate usefulness and durable admission preview evidence.
- `skill-agent stable-readiness --json` emits the read-only advisory candidate-to-stable review report. It does not authorize stable promotion or enable stable routing.
- `skill-agent candidate-decision --json` emits the compact read-only operator decision report for one candidate, including `candidate_id`, `decision`, source-backed `why` items, nested stable-readiness evidence, and `next_command`.
- `skill-agent negative-evidence --json` emits read-only unfavorable/limiting evidence from candidate and resolution ledgers.
- `skill-agent evidence-checkpoint --json` emits the local evidence checkpoint create or verify report. `--no-dry-run` appends only to `runs/evidence_checkpoints.json`; `--verify` is read-only.
- `skill-agent evidence-governor --json` emits the read-only advisory recommendation report for one candidate. It never grants approval or steers execution.
- `skill-agent shadow-activation-plan --json` emits the read-only managed-prefix activation plan for one candidate.
- `skill-agent shadow-rollback-plan --json` emits the read-only managed-prefix rollback verifier for one candidate.
- `skill-agent shadow-activation-acceptance --json` emits the controlled acceptance harness report for one candidate. With `--prepare-acceptance-evidence`, it may write matching acceptance evidence under `runs/` only.
- `skill-agent shadow-write-gate --json` emits the read-only human write-gate verifier for prepared acceptance evidence. It never prepares evidence or mutates the real managed prefix.
- `skill-agent v1-local-use --json` emits the read-only v1 managed-prefix local-use checklist. It names `shadow-managed-write` as the primary command, reports `stable_routing_policy: "deferred_for_v1"`, lists required digest/checkpoint/write-approval inputs, and records unchanged authority for durable skills, registries, ledgers, run logs, stable routing, and governor steering.
- `skill-agent eval --json` emits the eval suite path, timestamp, per-task run-log paths, task pass/fail status, routing decisions, skill requests, input requests, request-quality scores, diagnostic dimensions, and aggregate counts.
- `skill-agent explain <run-log.json>` reads an existing run log and prints a human-readable trace summary. It does not mutate the run log.

## Eval Task

Eval suites are JSONL. Blank lines and comment lines are ignored.

```json
{
  "id": "missing_contradiction_001",
  "task": "Extract claims from these two sources and identify contradictions.",
  "expected": {
    "outcome": "missing_skill_request",
    "capability": "detect contradictions",
    "must_request_skill": true,
    "must_not_load_skill": "compare-claims",
    "min_request_quality": 4.0,
    "must_have_routing_decision": true,
    "trace_complete": true
  },
  "tags": ["missing_skill", "contradiction"],
  "temporary_skills": false,
  "scripted_skills": false
}
```

Eval tasks may optionally set `temporary_skills` or `scripted_skills` to override the suite-level execution mode for that row. Omitted values inherit the runner/CLI defaults. Tasks may also set `input_request_resolutions` as post-run eval fixture actions. Each action selects one task-scoped input request by `input_request_id` or by `kind`/`status`, calls the real non-dry-run resolver, appends to the resolution ledger, and then re-reads the queue before expectations are checked. Stable-readiness eval fixture preparation may promote a candidate inside the eval run directory only when `prepare_stable_readiness_candidate` is explicitly set; it may also set duplicate evidence with `stable_readiness_duplicate_of` / `stable_readiness_duplicate_evidence` or append eval-only negative resolution evidence with `stable_readiness_negative_resolution_decision`. That fixture support is not runtime auto-promotion and does not authorize stable routing.

Supported v0 expectations include:

- Core outcome/routing: `outcome`, `capability`, `must_request_skill`, `must_load_skill`, `must_not_load_skill`, `must_not_request_skill`, `min_request_quality`, `must_have_routing_decision`, `must_block_adversarial`, and `trace_complete`.
- Skill request control summaries: `must_have_request_control_summary`.
- Governor assertions: `governor_decision`, `governor_risk_level`, `governor_approval_required`, and `governor_dominant_signal`.
- Skill Candidate Ledger assertions: `candidate_id`, `candidate_skill_name`, `candidate_capability`, `must_have_candidate_entry`, `candidate_status`, `min_candidate_request_count`, `candidate_human_approval_required`, `must_have_candidate_evidence`, `must_not_auto_promote`, `candidate_validation_pass_count_min`, `candidate_validation_failure_count_min`, `candidate_duplicate_of_present`, `candidate_block_reason_contains`, `candidate_quarantine_reason_contains`, `candidate_repair_requirement_contains`, `candidate_promotion_requirement_contains`, and `candidate_review_queue`.
- Stable-readiness assertions and fixtures: `must_have_stable_readiness_report`, `stable_readiness_outcome`, `stable_readiness_ready_for_review`, `stable_review_authorized`, `stable_promotion_authorized`, `stable_routing_enabled`, `stable_readiness_blocker`, `prepare_stable_readiness_candidate`, `stable_readiness_successful_temporary_uses`, `stable_readiness_duplicate_of`, `stable_readiness_duplicate_evidence`, and `stable_readiness_negative_resolution_decision`.
- Input-focus assertions: `must_have_input_request`, `input_request_kind`, `input_request_status`, `input_request_active_count`, `input_request_resolution_count`, and `input_request_resolution_decisions`.

## Eval Report

```json
{
  "suite": "evals/capgap_smoke.jsonl",
  "timestamp": "2026-05-30T21:18:55",
  "passed": true,
  "aggregate": {
    "total": 4,
    "passed": 4,
    "failed": 0,
    "task_pass_rate": 1.0,
    "missing_skill_true_positives": 1,
    "missing_skill_false_positives": 0,
    "missing_skill_false_negatives": 0,
    "wrong_skill_loads": 0,
    "unsafe_allowed": 0,
    "safe_blocked": 0,
    "approval_required_detected": 1,
    "adversarial_attempted": 0,
    "adversarial_blocked": 0,
    "average_request_quality": 4.6,
    "trace_complete_count": 4,
    "trace_incomplete_count": 0,
    "trace_completeness": 1.0,
    "failure_categories": {},
    "diagnostic_dimensions": {
      "missing_skill": {
        "total": 1,
        "passed": 1,
        "failed": 0,
        "pass_rate": 1.0,
        "trace_completeness": 1.0,
        "average_request_quality": 4.6,
        "governor_decision_accuracy": 1.0,
        "lifecycle_evidence_accuracy": null,
        "failure_categories": {},
        "suggested_next_action": ""
      }
    },
    "weakest_diagnostic_dimensions": []
  },
  "tasks": []
}
```

Per-task records include `run_id`, `run_log_path`, `explain_command`, `result_category`, `loaded_skills`, `requested_skills`, `rejected_skills`, `skill_requests`, `input_requests`, `input_request_resolutions`, `stable_readiness_reports`, `request_quality`, `routing_decisions`, `trace`, `trace_complete`, `failure_categories`, `suggested_next_action`, and any assertion issues.

Per-task records also include `governor_decisions` and `governor_expectation_passed` when governor assertions are evaluated.

`diagnostic_dimensions` groups task results by non-generic tags, excluding bookkeeping tags such as `diagnostic`, `smoke`, `v0`, and `calibration`. `weakest_diagnostic_dimensions` lists up to three failing dimensions sorted by failed count, then pass rate, so local iteration can start with the largest visible failure bucket.

Failure categories are one or more of `wrong_route`, `missing_skill_not_detected`, `unnecessary_skill_request`, `unsafe_not_blocked`, `safe_task_overblocked`, `approval_not_requested`, `bad_skill_request_contract`, `trace_incomplete`, `report_incomplete`, `planner_misclassified_task`, `governor_decision_mismatch`, `governor_signal_mismatch`, `request_control_summary_missing`, `lifecycle_evidence_mismatch`, `stable_readiness_mismatch`, `input_request_missing`, `input_request_kind_mismatch`, `input_request_status_mismatch`, and `input_request_resolution_mismatch`.

## Request Quality

Request quality is deterministic and normalized to a 0-5 score:

```json
{
  "score": 4.6,
  "max_score": 5,
  "dimensions": {
    "specificity": 2,
    "input_contract": 1,
    "output_contract": 2,
    "success_criteria": 2,
    "failure_modes": 2,
    "risk_level_correctness": 2,
    "reuse_potential": 2
  },
  "notes": ["Weak input contract."]
}
```

Dimensions are scored 0-2: specificity, input contract, output contract, success criteria, failure modes, risk-level correctness, and reuse potential.
