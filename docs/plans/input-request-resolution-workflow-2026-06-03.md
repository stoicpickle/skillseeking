# Input Request Resolution Workflow Design

Status: append-only resolution ledger implemented

This plan defines how input requests are resolved without changing the advisory nature of the queue. The current implementation can collect, display, dry-run classify, and append resolution evidence, but it does not mutate run logs, candidate ledgers, install skills, approve durable admission, or steer the governor.

## Goals

- Give every input request a concrete resolution path.
- Preserve the immutable run log as evidence.
- Keep durable promotion, install/copy, permission widening, and unsafe execution human-governed.
- Make resolution auditable before adding any mutation.

## Command Shape

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
- `--dry-run`: default non-mutating classification mode.

Dry-run resolution remains non-mutating. Non-dry-run resolution appends a record to `runs/input_request_resolutions.json`; historical run logs and candidate ledgers must never be rewritten by this command.

## Resolution Outcomes

| Input kind | Valid decisions | Resulting status | Follow-up |
| --- | --- | --- | --- |
| `safety_approval` | `approve_workflow`, `revise_task`, `defer` | `resolved`, or `open` for `defer` | Rerun with explicit approval or revised task. |
| `promotion_approval` | `approve_promotion`, `repair_candidate`, `reject_candidate`, `defer` | `resolved`, or `open` for `defer` | May call existing `promote-candidate`; does not install durable skills. |
| `durable_admission_review` | `approve_review`, `repair_candidate`, `block`, `defer` | `resolved`, or `open` for `defer` | May produce human review evidence; durable install remains future work. |
| `repair_review` | `repair_candidate`, `reject_candidate`, `defer` | `resolved`, or `open` for `defer` | Produce repair notes or leave candidate blocked. |
| `ambiguity_resolution` | `merge_candidate`, `keep_separate`, `reject_candidate`, `defer` | `resolved`, or `open` for `defer` | Produce merge decision evidence; do not mutate candidate identity yet. |
| `missing_evidence` | `repair_candidate`, `recover_evidence`, `block`, `defer` | `resolved`, or `open` for `defer` | Re-run evidence collection or admission plan. |

## Resolution Ledger Shape

```json
{
  "schema_version": 1,
  "resolutions": [
    {
      "input_request_id": "inputreq_abc123",
      "decision": "defer",
      "status": "open",
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

The ledger lives under `runs/input_request_resolutions.json` and is append-only until there is a separate compaction design. `skill-agent input-requests` reads the latest record for each input request as a status overlay: `resolved` requests leave the active queue, while `defer` keeps the request visible as `open`.

## Validation Plan

- CLI dry-run test for each input kind and every declared decision option. Status: complete.
- JSON contract test for source request snapshots. Status: complete.
- Regression test proving run logs and candidate ledgers are not rewritten. Status: complete.
- Input queue regression proving the latest resolution controls active status. Status: complete.

## Boundaries

- Do not auto-resolve requests.
- Do not treat `approve_review` as durable install approval.
- Do not write to `skills/`.
- Do not widen permissions.
- Do not let the governor steer execution from resolution state.
