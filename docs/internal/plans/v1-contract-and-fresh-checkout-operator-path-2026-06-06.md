# V1 Contract And Fresh-Checkout Operator Path

Status: complete

## Source

This plan implements the first slice from [V1.0 Release Tasking](../v1-release-tasking.md): define the v1 contract and prove the first-run operator path. Context7 check: current Python Semantic Release docs treat `pyproject.toml:project.version` as the primary version stamp and support changelog/release-note generation, so the v1 contract should treat version, changelog, release notes, and tags as release artifacts rather than afterthoughts.

Current branch context:

- Branch: `codex/capgap-eval-private` tracking `release branch`.
- Baseline: `candidate-decision` is committed and pushed as `2397dae feat: add candidate decision summary`.
- At the time of this slice, `pyproject.toml` declared `version = "0.1.0"`. The final release gate later stamped `version = "1.0.0"`.

## Product Question

Can a new local operator understand the v1 promise and run the canonical first proof path from a fresh checkout without needing private repo lore?

## Goal

Create the v1 release contract and a fresh-checkout smoke path that prove the local CLI operator experience while preserving current safety boundaries.

## Scope

### Docs

- Add `docs/v1-release-contract.md`.
- Link `docs/internal/v1-release-tasking.md` and the new contract from `docs/operating-roadmap.md`.
- Update README only enough to point to the v1 tasking/contract work, not to claim v1 is shipped.

### Smoke Helper

- Add a canonical smoke helper, likely `scripts/v1_smoke.sh`.
- The helper should run from repo root and fail loudly.
- It should use `.venv/bin/python` and `.venv/bin/skill-agent` when present, matching current repo validation style.
- It should keep proof under a run-scoped or temporary smoke directory, not mutate durable skills.
- It should cover:
  - package import/CLI availability;
  - gauntlet or core demo smoke;
  - capgap smoke eval;
  - lifecycle eval or a narrow candidate-decision fixture path;
  - `candidate-decision --help` or one candidate-decision JSON inspection when a candidate fixture is created.

### Validation Docs

- Document the smoke helper in `docs/v1-release-contract.md`.
- Add the helper to the v1 tasking checks if needed.
- Update dev log after implementation.

## Boundaries

- Do not change `pyproject.toml` to `1.0.0` in this slice; that is reserved for the later final release gate.
- Do not introduce durable `skills/` admission.
- Do not enable stable routing.
- Do not add active governor steering.
- Do not claim true sandboxing.
- Do not add marketplace, hosted, or UI scope.
- Start from the committed `candidate-decision` baseline; do not redo or broaden that slice.

## Tasks

### 1. Confirm Current Baseline

Before editing behavior, confirm the current branch starts from the pushed `candidate-decision` baseline.

Checks:

- `git status --short --branch` is inspected.
- `git log --oneline -1` shows the current slice starts after `2397dae` or a descendant.
- No unrelated dirty files are reverted.

### 2. Draft V1 Release Contract

Create `docs/v1-release-contract.md` with:

- v1 promise;
- stable CLI commands;
- stable JSON/report contracts;
- lifecycle and promotion boundaries;
- safety and mutation boundaries;
- eval/release gates;
- explicit non-goals;
- version/changelog/tag expectations.

Checks:

- Contract does not claim production safety.
- Contract distinguishes local v1 stability from true sandboxing and hosted deployment.
- Contract names `pyproject.toml`, changelog, release notes, and tag as final release artifacts.

### 3. Build Fresh-Checkout Smoke Helper

Add `scripts/v1_smoke.sh` or the smallest repo-native equivalent.

Checks:

- Script starts with strict shell behavior.
- Script can run from any cwd by resolving repo root.
- Script does not require existing `runs/` state.
- Script does not mutate durable skills or registries.
- Script prints each major check before running it.

### 4. Wire Docs

Add discoverability:

- README pointer to v1 tasking/contract planning.
- Operating roadmap pointer to `docs/internal/v1-release-tasking.md`.
- Dev log entry for the slice.

Checks:

- README still says v1 is planned, not shipped.
- Roadmap still says current product proof is CLI-first prototype.

### 5. Validate

Docs/helper slice validation:

```bash
.venv/bin/python -m pytest -q tests/test_candidate_decision.py
.venv/bin/python -m compileall -q app
git diff --check
bash scripts/v1_smoke.sh
```

If helper touches broader eval behavior, also run:

```bash
.venv/bin/python -m pytest -q
.venv/bin/skill-agent eval --suite evals/capgap_smoke.jsonl --skills-dir skills --runs-dir runs/evals
.venv/bin/skill-agent eval --suite evals/skill_lifecycle_v0.jsonl --skills-dir skills --runs-dir runs/evals
```

## Expected Output

After this slice, the repo should have:

- a durable v1 tasking doc;
- a v1 release contract draft;
- a fresh-checkout smoke command;
- docs that make the path discoverable;
- proof that the smoke path runs without claiming v1 is already shipped.

## Not Yet

- `1.0.0` version bump.
- changelog initialization beyond planning unless needed for the contract.
- durable skill admission implementation.
- stable routing implementation.
- public release/tag.
