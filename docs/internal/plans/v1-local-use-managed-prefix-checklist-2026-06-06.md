# V1 Local-Use Managed-Prefix Checklist

Status: complete

## Source

This plan implements Task 4 from [V1.0 Release Tasking](../v1-release-tasking.md) after the v1 release eval gate.

Planning inputs:

- RepoPrompt plan `untitled-chat-9F0D78` recommended adding a compact read-only `v1-local-use` command instead of creating a second mutation path.
- Context7 Typer guidance confirmed the repo's current `Annotated[..., typer.Option(...)]` command style and `CliRunner` test style are current.

## Goal

Make the existing human-governed managed-prefix write path visible as the v1 local-use path.

## Current Evidence

The backend path already exists:

- `shadow-managed-write --no-dry-run` can perform the confined managed-prefix write.
- `build_shadow_managed_write_report` requires receipt evidence, shadow write-gate evidence, exact source/durable/shadow/rollback/acceptance/managed-write digests, latest checkpoint hash, and separate non-expired write approval.
- Existing tests cover happy path, idempotency, mismatch blockers, conflict blockers, symlink escape blocking, rollback/interruption recovery, and no durable skills/registry/ledger/governor mutation.

## Implementation

Add `skill-agent v1-local-use` as a read-only operator checklist.

In scope:

- Human and `--json` checklist output.
- Required command inputs for `shadow-managed-write`.
- Explicit unchanged authority and excluded authority.
- Smoke validation that the checklist still points to `shadow-managed-write` and managed-prefix-only mutation.
- Tasking/docs updates marking Task 4 complete through managed-prefix-first local use.

Out of scope:

- Durable `skills/` admission.
- Positive stable routing.
- A wrapper that executes `shadow-managed-write`.
- Registry, ledger, permission, dependency, governor, hosted, marketplace, or sandbox expansion.

## Validation

Planned local gates:

```bash
.venv/bin/python -m pytest -q tests/test_v1_local_use.py tests/test_shadow_activation.py
bash scripts/v1_smoke.sh
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
```

Run one CodeRabbit pass before push:

```bash
coderabbit review --agent -t uncommitted --dir <repo-root>
```
