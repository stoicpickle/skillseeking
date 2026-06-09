# Final V1 Release Gate

Date: 2026-06-06

This plan implements Task 11 from [V1.0 Release Tasking](../v1-release-tasking.md).

Planning sources:

- RepoPrompt plan `untitled-chat-C2D115` recommended a targeted final release-stamp slice with package version `1.0.0`, Git tag `v1.0.0`, private-remote-only push, and no positive stable-routing expansion.
- Context7 Python Semantic Release docs identify `pyproject.toml:project.version` as the package version stamp and require valid SemVer.

## Goal

Promote Skill-Seeking Agent from local v1 release candidate to v1.0 local CLI release state after the final proof bundle passes.

## Scope

This slice stamps and verifies:

- `pyproject.toml` package version `1.0.0`;
- release docs that name package version `1.0.0` and Git tag `v1.0.0`;
- `scripts/v1_smoke.sh` as a v1 release verifier;
- release-doc tests that assert final release state;
- no hosted service, marketplace, package publish, production-safety claim, true sandboxing claim, durable generated-skill admission, or positive stable routing.

Stable routing remains deferred for v1. The conditional positive stable-routing eval expansion remains out of scope because the v1 release policy is explicitly not-routed.

## Validation

Run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
bash scripts/v1_smoke.sh
.venv/bin/skill-agent eval --suite evals/capgap_smoke.jsonl --skills-dir skills --runs-dir /tmp/skill-agent-v1-final-capgap-smoke
.venv/bin/skill-agent eval --suite evals/capgap_v0.jsonl --skills-dir skills --runs-dir /tmp/skill-agent-v1-final-capgap-v0
.venv/bin/skill-agent eval --suite evals/skill_lifecycle_v0.jsonl --skills-dir skills --runs-dir /tmp/skill-agent-v1-final-lifecycle
.venv/bin/skill-agent eval --suite evals/agent_diagnostic_v0.jsonl --skills-dir skills --runs-dir /tmp/skill-agent-v1-final-diagnostic
.venv/bin/skill-agent eval --suite evals/v1_release.jsonl --skills-dir skills --runs-dir /tmp/skill-agent-v1-final-release
coderabbit review --agent -t uncommitted --dir <repo-root>
```

After commit and private branch push, verify a fresh private checkout and create the annotated tag only if the checkout gate passes:

```bash
git tag -a v1.0.0 -m "Skill-Seeking Agent v1.0.0"
REQUIRE_V1_TAG=1 bash scripts/v1_smoke.sh
git push private v1.0.0
git ls-remote --tags private v1.0.0
```
