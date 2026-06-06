# V1 Release Candidate Documentation

Date: 2026-06-06

This plan implements Task 10 from [V1.0 Release Tasking](../v1-release-tasking.md).

Planning sources:

- RepoPrompt plan `untitled-chat-76F633` recommended a release-candidate documentation slice, not a version-stamp or tag slice.
- Context7 Python Semantic Release docs identify `pyproject.toml:project.version` as the version stamp and describe changelog/release notes as release artifacts.

## Goal

Move the repo from research-only framing to honest local v1 CLI release-candidate documentation without overstating safety or claiming a shipped `1.0.0`.

## Scope

Add and align:

- `CHANGELOG.md`;
- `docs/v1-release-notes.md`;
- README positioning;
- v1 contract and tasking status;
- release-doc smoke coverage;
- release-doc regression tests.

Out of scope:

- no `pyproject.toml` version bump;
- no `1.0.0` tag;
- no publish step;
- no durable `skills/` admission;
- no positive stable routing.

## Implementation Plan

1. Update `README.md` to describe Skill-Seeking Agent as a local v1 CLI release candidate for governed capability acquisition.
2. Add `CHANGELOG.md` with an Unreleased release-candidate section.
3. Add `docs/v1-release-notes.md` with current abilities, explicit limitations, verification commands, and remaining final-gate work.
4. Update `docs/v1-release-contract.md` and `docs/v1-release-tasking.md` so release docs are complete but the final `1.0.0` gate remains pending.
5. Add `tests/test_v1_release_docs.py` to guard against overclaiming release, hosted, marketplace, production-safe, sandbox, stable-routing, or version-tag status.
6. Update `scripts/v1_smoke.sh` to require the release docs and run the release-doc regression test.

## Validation

Run:

```bash
.venv/bin/python -m pytest -q tests/test_v1_release_docs.py
bash scripts/v1_smoke.sh
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
```

Before shipping, also run:

```bash
.venv/bin/skill-agent eval --suite evals/v1_release.jsonl --skills-dir skills --runs-dir /tmp/skill-agent-v1-release-check-task10
.venv/bin/skill-agent eval --suite evals/capgap_v0.jsonl --skills-dir skills --runs-dir /tmp/skill-agent-v1-capgap-v0-check-task10
```
