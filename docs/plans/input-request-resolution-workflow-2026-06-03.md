# Input Request Resolution Workflow Design

Status: design-only

This plan defines how input requests should be resolved later without changing the current read-only queue. The current implementation remains advisory: it can collect, display, and test input-needed states, but it does not mutate run logs, approve candidates, install skills, or steer the governor.

## Goals

- Give every input request a concrete resolution path.
- Preserve the immutable run log as evidence.
- Keep durable promotion, install/copy, permission widening, and unsafe execution human-governed.
- Make resolution auditable before adding any mutation.

## Proposed Command Shape

```bash
skill-agent resolve-input-request <input-request-id> \
  --runs-dir runs \
  --decision approve_promotion \
  --reviewer "Ada" \
  --notes "Reviewed run evidence and candidate contract." \
  --dry-run
```

Required fields:

- `input-request-id`: the queue ID to resolve.
- `decision`: one of the request's declared `options`.
- `reviewer`: human reviewer name for approval-like decisions.
- `notes`: short reason tying the decision to evidence.
- `--dry-run`: default for the first implementation.

Future non-dry-run resolution should write a separate resolution ledger, not rewrite historical run logs.

## Resolution Outcomes

| Input kind | Valid decisions | Resulting status | Follow-up |
| --- | --- | --- | --- |
| `safety_approval` | `approve_workflow`, `revise_task`, `defer` | `resolved` or `blocked` | Rerun with explicit approval or revised task. |
| `promotion_approval` | `approve_promotion`, `repair_candidate`, `reject_candidate`, `defer` | `resolved` or `blocked` | May call existing `promote-candidate`; does not install durable skills. |
| `durable_admission_review` | `approve_review`, `repair_candidate`, `block`, `defer` | `resolved` or `blocked` | May produce human review evidence; durable install remains future work. |
| `repair_review` | `repair_candidate`, `reject_candidate`, `defer` | `resolved` or `blocked` | Produce repair notes or leave candidate blocked. |
| `ambiguity_resolution` | `merge_candidate`, `keep_separate`, `reject_candidate`, `defer` | `resolved` or `blocked` | Produce merge decision evidence; do not mutate candidate identity yet. |
| `missing_evidence` | `repair_candidate`, `recover_evidence`, `block`, `defer` | `resolved` or `blocked` | Re-run evidence collection or admission plan. |

## Resolution Ledger Shape

```json
{
  "schema_version": 1,
  "resolutions": [
    {
      "input_request_id": "inputreq_abc123",
      "decision": "defer",
      "status": "blocked",
      "reviewer": "Ada",
      "notes": "Waiting on missing source artifact.",
      "source_request": {
        "kind": "missing_evidence",
        "blocked_scope": "durable skill install/copy",
        "evidence_refs": ["run_abc123"]
      },
      "created_at": "2026-06-03T12:00:00"
    }
  ]
}
```

The ledger should live under `runs/input_request_resolutions.json` and should be append-only until there is a separate compaction design.

## Validation Plan

- CLI dry-run test for each input kind.
- JSON contract test for source request snapshots.
- Regression test proving run logs are not rewritten.
- Eval expectation for `input_request_status` once resolution state is read by `input-requests`.

## Boundaries

- Do not auto-resolve requests.
- Do not treat `approve_review` as durable install approval.
- Do not write to `skills/`.
- Do not widen permissions.
- Do not let the governor steer execution from resolution state.
