# V1 Stable Routing Policy Deferred

Status: complete

## Source

This plan implements Task 5 from [V1.0 Release Tasking](../v1-release-tasking.md).

Planning inputs:

- RepoPrompt plan `untitled-chat-A7A402` recommended defining stable routing as explicitly deferred/disabled for v1 rather than adding positive routing.
- Context7 pytest guidance confirmed simple pathlib/plain-assert documentation contract tests are current.

## Decision

V1 does not enable positive stable routing.

The v1 policy is:

- stable-readiness is advisory only;
- stable review remains unauthorized;
- stable promotion remains unauthorized;
- stable routing remains disabled;
- managed-prefix-first local use through `shadow-managed-write` is the v1 local-use lane;
- positive stable routing is post-v1 work.

## Implementation

In scope:

- Add `docs/stable-routing-policy.md`.
- Add `stable_routing_policy: "deferred_for_v1"` to `skill-agent v1-local-use --json`.
- Add a named release eval row proving the policy when stable-readiness is otherwise ready.
- Tighten tests around stable-readiness next steps and v1 eval stable-routing fields.
- Update v1 contract, tasking, data contracts, evaluation plan, roadmap, README, smoke, and dev log.

Out of scope:

- stable route registry;
- stable promotion;
- durable `skills/` admission;
- automatic routing to generated skills;
- dependency installation;
- active governor steering.

## Validation

Planned local gates:

```bash
.venv/bin/python -m pytest -q tests/test_stable_readiness.py tests/test_v1_release_eval.py tests/test_v1_local_use.py tests/test_stable_routing_policy_docs.py
.venv/bin/skill-agent eval --suite evals/v1_release.jsonl --skills-dir skills --runs-dir /tmp/skill-agent-v1-release-check-task5
bash scripts/v1_smoke.sh
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app
git diff --check
```

Run one CodeRabbit pass before push:

```bash
coderabbit review --agent -t uncommitted --dir /Users/russ/Documents/Russ/skillseekingagent
```
