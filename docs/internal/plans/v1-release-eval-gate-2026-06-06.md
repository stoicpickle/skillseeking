# V1 Release Eval Gate

Status: complete

## Source

This plan implements Task 6A from [V1.0 Release Tasking](../v1-release-tasking.md) after the v1 contract and fresh-checkout smoke path.

Planning inputs:

- RepoPrompt plan `untitled-chat-C75C6D` recommended bootstrapping `evals/v1_release.jsonl` before Task 4 or Task 5, so later admission/routing work has a fixed release safety harness.
- Context7 pytest guidance confirmed the current lightweight test approach: pathlib reads plus plain `assert` statements for file/fixture validation.

## Goal

Create a named v1 release gate that runs through the repo's existing `skill-agent eval` harness and is included in the canonical smoke helper.

## Scope

In scope:

- Add `evals/v1_release.jsonl` using the existing `EvalTask` JSONL schema.
- Cover release-critical local CLI behaviors already supported by the current evaluator.
- Add focused pytest coverage for suite shape, pass result, no durable skill mutation, and disabled stable review/promotion/routing authority.
- Wire `scripts/v1_smoke.sh` to run the suite.
- Update release docs and tasking.

Out of scope:

- Positive stable routing.
- Durable `skills/` admission.
- Dependency installation.
- Marketplace, hosted, or true sandboxing claims.
- Version bump, changelog, release note, or tag.

## Implemented Coverage

The suite covers:

- existing skill happy path;
- missing capability request;
- unsafe stop;
- approval-required stop;
- adversarial routing resistance;
- temporary skill success that still requires review;
- repair-needed evidence;
- stable-readiness ready-for-review while not routed;
- duplicate-blocked stable review;
- negative-evidence-blocked stable review.

## Validation

Planned local gates:

```bash
.venv/bin/python -m pytest -q tests/test_v1_release_eval.py
.venv/bin/skill-agent eval --suite evals/v1_release.jsonl --skills-dir skills --runs-dir /tmp/skill-agent-v1-release-check
bash scripts/v1_smoke.sh
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
```

Run one CodeRabbit pass before push:

```bash
coderabbit review --agent -t uncommitted --dir <repo-root>
```
