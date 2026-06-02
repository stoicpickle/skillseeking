# Data Contracts

Contracts are schema-v3 and serialized with Pydantic `model_dump(mode="json")`. Older run logs without `schema_version`, `run_id`, governor records, or request control summaries are tolerated by health analysis and explain output where applicable.

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

- `skill-agent run --json` emits run result data: IDs, exit code, result category, run-log path, execution summary, decisions, requests, repairs, loaded skills, rejected skills, trace events, and script executions.
- `skill-agent registry --json` emits `{ "accepted": [...], "rejected": [...] }`.
- `skill-agent health --json` is additive and includes v2 metrics such as result categories, temporary outcomes, repair counts, safety stops, human approval waits, route/load failures, and script failure categories.
- `skill-agent eval --json` emits the eval suite path, timestamp, per-task run-log paths, task pass/fail status, routing decisions, skill requests, request-quality scores, and aggregate counts.
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

Eval tasks may optionally set `temporary_skills` or `scripted_skills` to override the suite-level execution mode for that row. Omitted values inherit the runner/CLI defaults.

Supported v0 expectations include:

- Core outcome/routing: `outcome`, `capability`, `must_request_skill`, `must_load_skill`, `must_not_load_skill`, `must_not_request_skill`, `min_request_quality`, `must_have_routing_decision`, `must_block_adversarial`, and `trace_complete`.
- Skill request control summaries: `must_have_request_control_summary`.
- Governor assertions: `governor_decision`, `governor_risk_level`, `governor_approval_required`, and `governor_dominant_signal`.
- Skill Candidate Ledger assertions: `candidate_id`, `candidate_skill_name`, `candidate_capability`, `must_have_candidate_entry`, `candidate_status`, `min_candidate_request_count`, `candidate_human_approval_required`, `must_have_candidate_evidence`, `must_not_auto_promote`, `candidate_validation_pass_count_min`, `candidate_validation_failure_count_min`, `candidate_duplicate_of_present`, `candidate_block_reason_contains`, `candidate_quarantine_reason_contains`, `candidate_repair_requirement_contains`, and `candidate_promotion_requirement_contains`.

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
    "failure_categories": {}
  },
  "tasks": []
}
```

Per-task records include `run_id`, `run_log_path`, `explain_command`, `result_category`, `loaded_skills`, `requested_skills`, `rejected_skills`, `skill_requests`, `request_quality`, `routing_decisions`, `trace`, `trace_complete`, `failure_categories`, `suggested_next_action`, and any assertion issues.

Per-task records also include `governor_decisions` and `governor_expectation_passed` when governor assertions are evaluated.

Failure categories are one or more of `wrong_route`, `missing_skill_not_detected`, `unnecessary_skill_request`, `unsafe_not_blocked`, `safe_task_overblocked`, `approval_not_requested`, `bad_skill_request_contract`, `trace_incomplete`, `report_incomplete`, `planner_misclassified_task`, `governor_decision_mismatch`, `governor_signal_mismatch`, and `request_control_summary_missing`.

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
