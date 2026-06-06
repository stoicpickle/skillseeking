# V1 Data Contract Freeze

Date: 2026-06-06

This plan implements Task 9 from [V1.0 Release Tasking](../v1-release-tasking.md).

Planning sources:

- RepoPrompt plan `untitled-chat-420972` recommended a targeted docs-and-tests contract freeze instead of broad JSON Schema generation.
- Context7 Pydantic docs confirmed `model_validate`, `model_dump(mode="json")`, and `model_json_schema()` as current Pydantic v2 APIs for model validation, JSON-compatible serialization, and schema inspection.

## Goal

Freeze the representative v1 JSON and ledger compatibility surfaces that operators and future slices now rely on.

## Scope

The v1 fixture freeze covers representative payloads for:

- run logs;
- skill candidate ledgers;
- input request resolution ledgers;
- evidence checkpoint ledgers;
- candidate decision reports;
- eval reports.

This is not an exhaustive schema generator. It is a compatibility sentinel for top-level versions, stable identity fields, required nested objects, and JSON-serializable model output.

## Implementation

1. Add deterministic fixture payloads under `tests/fixtures/v1_contracts/`.
2. Add `tests/test_v1_fixture_compatibility.py`.
3. Validate model-backed fixtures with Pydantic v2 `model_validate`.
4. Serialize model-backed fixtures with `model_dump(mode="json")` and re-validate the serialized payload.
5. Validate the eval report fixture with explicit key/type checks because eval reports are currently plain dicts.
6. Update `docs/contracts/data-contracts.md` with the v1 freeze policy, schema/version notes, and volatility caveat.
7. Mark Task 9 complete in `docs/v1-release-tasking.md` and keep the remaining release blockers accurate.
8. Wire the focused compatibility test into `scripts/v1_smoke.sh`.

## Validation

Run:

```bash
.venv/bin/python -m pytest -q tests/test_v1_fixture_compatibility.py
bash scripts/v1_smoke.sh
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
```

Also run the v1 release and capgap v0 eval gates directly before shipping:

```bash
.venv/bin/skill-agent eval --suite evals/v1_release.jsonl --skills-dir skills --runs-dir /tmp/skill-agent-v1-release-check-task9
.venv/bin/skill-agent eval --suite evals/capgap_v0.jsonl --skills-dir skills --runs-dir /tmp/skill-agent-v1-capgap-v0-check-task9
```
