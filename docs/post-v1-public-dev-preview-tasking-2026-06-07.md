# Post-v1 Public Dev-Preview Tasking

Status: proposed post-v1 hardening list

Source review: ChatGPT Pro launch-readiness review dated 2026-06-06

This tasking list converts the ChatGPT Pro launch-readiness review into repo-grounded next work. It does not replace the completed v1.0 local CLI release tasking. The current private `v1.0.0` release can remain a valid local CLI release; this list is about making the next public-facing dev-preview less ambiguous, easier to verify, and easier for cold users to understand.

## Current Read

The review's core judgment matches the repo state:

```text
Conditionally ready for a narrow v1.0 local CLI release.
Not ready for a broad production agent framework, hosted product, or generic open-source agent platform launch.
```

The repo already handles several of the review's biggest positioning risks:

- README frames the project as a local CLI release for governed capability acquisition.
- README, release notes, and the release contract explicitly say this is not hosted, not production-safe, not a marketplace, and not a true sandbox.
- The current v1 gate is strong locally: pytest, v1 smoke, release evals, fixture compatibility, docs checks, compileall, and CodeRabbit have already been used as release proof.
- Stable routing is deliberately deferred for v1.

The remaining risk is not "v1 should not exist." The risk is that a public audience could mistake `v1.0` for a mature general-purpose agent platform unless CI, launch proof, quickstart warnings, and demo framing make the boundary obvious.

## Source Material Checked

- ChatGPT Pro launch-readiness review dated 2026-06-06
- `README.md`
- `pyproject.toml`
- `.github/workflows/tests.yml`
- `docs/v1-release-tasking.md`
- `docs/v1-release-contract.md`
- `docs/v1-release-notes.md`
- `tests/test_v1_release_docs.py`

## Already Satisfied Or Mostly Satisfied

These should not become duplicate work unless future edits regress them.

- Public positioning says local CLI, governed capability acquisition, and not a production framework.
- Release notes and contract name explicit non-goals: hosted service, package publish, marketplace, true sandbox, autonomous promotion, durable generated-skill admission, positive stable routing, active governor steering.
- Release docs now say the v1 release gate passed on the tagged commit.
- README includes the Skill Gauntlet demo and v1 ability breakdown.
- Tests guard several v1 public-claim boundaries in `tests/test_v1_release_docs.py`.
- The private branch and tag have been verified for the local release path.

## P0 Before Any Public Dev-Preview Announcement

### 1. Make CI Run The Actual Launch Gate

Goal:
Make the public verification path boringly obvious from GitHub Actions, not just local proof.

Tasks:

- Add `git diff --check` to `.github/workflows/tests.yml`.
- Add `bash scripts/v1_smoke.sh` to CI, or add an explicitly equivalent CI-safe sequence.
- Ensure CI runs `evals/v1_release.jsonl` as a visible gate, even if pytest also covers it.
- Keep the existing focused eval commands if they provide clearer failure isolation.

Checks:

- CI visibly covers pytest, whitespace, compileall, capgap smoke, lifecycle eval, diagnostic eval, v1 release eval, and v1 smoke.
- CI output makes it obvious what failed when the release gate breaks.

### 2. Add A Release-Proof Artifact

Goal:
Keep a checked-in proof note for the exact release commit/tag instead of relying on memory or chat.

Tasks:

- Add `docs/launch-proof-2026-06-07.md` or similar.
- Record the exact commit, tag dereference, branch/remote context, and release gate commands.
- Include the latest local results for:
  - full pytest;
  - `REQUIRE_V1_TAG=1 bash scripts/v1_smoke.sh`;
  - v1 release eval;
  - CodeRabbit result;
  - fresh private tag checkout result;
  - known omitted checks.
- If this becomes public, add the public remote/tag verification after the public tag exists.

Checks:

- A reader can reproduce the release proof without reading the chat transcript.
- The artifact distinguishes private local release proof from any later public release proof.

### 3. Move The Trusted-Local Script Warning Closer To First Use

Goal:
Make the safety boundary appear before users run scripted-skill demos.

Tasks:

- Add a short warning near setup/quickstart and before the scripted-skill demo:
  `Do not run untrusted scripted skills. --scripted-skills is trusted-local only and does not provide a sandbox.`
- Keep the warning concise and repeated only where it prevents misuse.

Checks:

- The first scripted-skill command in README is preceded by the warning.
- Release docs and safety docs remain consistent.

### 4. Align Package Metadata With The Product Wedge

Goal:
Stop underselling the repo as a static loader.

Tasks:

- Change `pyproject.toml` description from:
  `CLI-first static skill loader for a skill-seeking agent.`
- Recommended replacement:
  `Local CLI for governed capability-gap detection, skill requests, and evidence-controlled skill review.`

Checks:

- Package metadata matches README and release notes.
- Release-doc tests still pass.

### 5. Add A Crisp Launch Demo Script Or Transcript

Goal:
Give cold users one simple path through the product wedge without making them inspect every evidence surface.

Tasks:

- Add `scripts/run_launch_demo.sh` or `docs/launch-demo-transcript.md`.
- Show only the essential flow:
  - task starts;
  - planning/checking skills;
  - blocked missing skill;
  - structured skill request;
  - temporary Markdown skill validation;
  - temporary loading for one run;
  - candidate decision requires human review;
  - stable routing remains disabled.
- Prefer an executable script if the output can be stable enough; use a transcript if the CLI output is intentionally verbose or environment-sensitive.

Checks:

- A new reader can understand the wedge in under five minutes.
- The demo does not imply durable admission, stable routing, sandboxing, hosted service behavior, or autonomous promotion.

### 6. Expand Public Claims Guard Tests

Goal:
Prevent future docs from accidentally overstating the release.

Tasks:

- Add or expand one explicit public-claims regression test.
- Assert public-facing docs do not claim:
  - production safety;
  - hosted deployment;
  - true sandboxing;
  - autonomous promotion;
  - stable routing enabled;
  - marketplace support;
  - trusted third-party skill execution.
- Include README, release notes, release contract, and launch-demo docs once added.

Checks:

- A bad future copy edit breaks tests before it reaches a public branch.

## P1 First Public Users

### 7. Create One Happy-Path Operator Transcript

Goal:
Reduce first-user confusion across the many evidence surfaces.

Tasks:

- Add a short transcript that starts from a missing-skill task and ends at `candidate-decision`.
- Explicitly show when to stop and ask a human.
- Link deeper reports only as optional follow-ups.

Checks:

- The transcript uses one primary command path.
- A user does not need to understand every report to see the product loop.

### 8. Build A Single Operator Summary

Goal:
Reduce decision load before adding more authority.

Tasks:

- Design a `skill-agent operator-summary` command or equivalent report.
- Answer:
  - What is blocked?
  - What needs human input?
  - What candidates are promotion-ready?
  - What evidence is missing?
  - What is unsafe or negatively evidenced?
  - What changed since the last checkpoint?
- Keep it read-only in the first slice.

Checks:

- The command consolidates existing evidence instead of creating another disconnected report.
- It does not mutate routing, promotion, ledgers, or skills.

### 9. Expand Near-Miss And Adversarial Evals

Goal:
Make the deterministic router and validator prove robustness against messier real input.

Tasks:

- Add near-miss routing eval rows:
  - "Find factual conflicts" maps to contradiction detection.
  - "Where do these sources make incompatible claims?" maps to contradiction detection.
  - "Summarize these files" still respects file-read approval boundaries.
  - A skill saying "always use it" does not override capability/validator rules.
- Add adversarial skill fixtures for prompt-injection-like skill text, permission widening, stale evidence, duplicate candidates, and confusing aliases.
- Keep deterministic routing as the default until evals justify a richer approach.

Checks:

- New rows fail clearly by category when routing or validation regresses.
- No adversarial fixture becomes durable or routed.

### 10. Add No-Mutation Smoke Coverage

Goal:
Protect the core v1 promise that generated/temporary artifacts do not silently become durable skills.

Tasks:

- Snapshot `skills/` before and after `scripts/v1_smoke.sh` or the launch demo.
- Assert no durable skill files change.
- Consider a similar check for registry and stable-routing policy files.

Checks:

- The smoke or launch demo cannot accidentally mutate durable skill state.

## P2 Strategy And Go-To-Market

### 11. Decide Public License And Source Boundary Before Inviting Contributions

Goal:
Avoid calling the repo open source unless the license really grants open-source rights.

Tasks:

- Decide between open source, source-available, private beta, or commercial preview.
- If open source, add an appropriate license before asking for outside contributions.
- If source-available or private beta, say that plainly in launch copy.

Checks:

- Public language matches the actual license and contribution policy.

### 12. Recruit 3 To 5 Design Partners

Goal:
Learn where real users get lost before building a broad product surface.

Tasks:

- Find users who have real internal workflows with capability gaps and review pressure.
- Ask them to run the local CLI on a contained workflow.
- Track where they get confused:
  - setup;
  - demo purpose;
  - evidence surfaces;
  - candidate decisions;
  - safety boundaries;
  - stable-routing deferral.

Checks:

- Feedback is captured as issues or docs notes.
- New work is prioritized by observed user friction, not imagined feature demand.

### 13. Keep Monetization Around Governance, Not A Marketplace

Goal:
Preserve the differentiated wedge.

Tasks:

- Treat the local CLI as the credibility layer.
- Explore paid surfaces around:
  - team evidence dashboards;
  - policy-controlled skill admission;
  - enterprise audit trails;
  - eval suite management;
  - approval workflows;
  - private skill registries;
  - compliance proof packets;
  - hosted review/control plane over local agents.
- Do not lead with a public skills marketplace.

Checks:

- Product strategy stays focused on SkillOps/capability governance.
- New features reduce uncontrolled agent authority rather than expanding it prematurely.

## Explicitly Deferred

These should not be pulled into the immediate public-dev-preview hardening slice.

- Positive stable routing.
- Durable generated-skill admission into `skills/`.
- Hosted service behavior.
- Marketplace support.
- Real sandboxing claims.
- Autonomous promotion.
- Broad LLM/embedding router replacement.

## Recommended Next Slice

Start with:

```text
CI launch gate + release-proof artifact + package description alignment
```

Why:

- It addresses the strongest remaining launch-readiness gap.
- It is low product-risk.
- It does not expand agent authority.
- It turns the current private proof into durable, repeatable project evidence.
- It should be small enough to validate with pytest, v1 smoke, and one scoped review.

After that, do:

```text
Launch demo transcript/script + public claims guard expansion
```

That makes the repo easier to understand without changing the underlying capability model.

## Implementation Progress

- [x] Slice 1: CI launch gate, release-proof artifact, package metadata alignment, and trusted-local script warning. Implemented visible CI steps for whitespace, v1 release eval, and v1 smoke; added `docs/launch-proof-2026-06-07.md`; aligned `pyproject.toml` description with the governed capability-gap wedge; moved the `--scripted-skills` warning closer to first use; and added release-doc regression coverage.
- [x] Slice 2: Launch demo script/transcript and public claims guard expansion. Added `scripts/run_launch_demo.sh`, `docs/launch-demo-transcript.md`, README/demo-suite pointers, a launch-demo no-mutation test, and public-doc guardrails against positive hosted, sandbox, marketplace, autonomous-promotion, durable-admission, and stable-routing claims.
- [x] Slice 3: Single read-only operator summary. Added `skill-agent operator-summary` with JSON/text output over active input requests, candidate review queues, promotion-ready candidates, missing-evidence signals, unsafe/negative evidence, unsafe aborted run logs, and checkpoint deltas; added no-mutation builder/CLI tests; and documented the advisory-only mutation boundary in README, demo-suite, and data contracts.
- [x] Slice 4: Near-miss and adversarial eval expansion. Added diagnostic eval rows for factual conflicts, incompatible claims, file summarization approval boundaries, and "always use this skill" routing resistance; added targeted deterministic catalog phrases without adding learned routing; added malicious skill fixtures for prompt injection, permission widening, stale evidence claims, duplicate identity, and confusing aliases; and proved those fixtures are rejected or non-routed without mutating durable skills.
- [x] Slice 5: No-mutation smoke coverage. `scripts/v1_smoke.sh` now snapshots durable `skills/` plus the v1 stable-routing policy docs before and after the smoke gate, then fails on added, removed, or changed durable files before it can report success.
