# Launch Proof: v1.0 Local CLI

Status: private/local v1.0 release proof

This artifact records the proof for the `v1.0.0` local CLI release state. It is not a hosted launch, public package publish, production-safety claim, marketplace claim, or true-sandbox claim.

## Scope

This proof applies to the private local CLI release path:

- Branch: `codex/capgap-eval-private`
- Remote: `private` (`<private release remote>`)
- Package version: `1.0.0`
- Git tag: `v1.0.0`
- Release commit: `e006ca815a5eba2e33b130386d5106fa5d7fb191`
- Tag object: `c13c61e2ec895ffebe3a5e015f46ab58fa5375ef`
- Tag dereference: `e006ca815a5eba2e33b130386d5106fa5d7fb191`

Public remote/tag proof is not included here. If this release is promoted from private local CLI release to public dev-preview, add the public remote, public tag, and public CI proof in a new launch-proof artifact.

## Remote Verification

Commands:

```bash
git rev-parse HEAD
git rev-parse v1.0.0
git rev-parse v1.0.0^{}
git ls-remote --heads --tags private 'codex/capgap-eval-private' 'v1.0.0*'
```

Observed private remote state:

```text
e006ca815a5eba2e33b130386d5106fa5d7fb191 refs/heads/codex/capgap-eval-private
c13c61e2ec895ffebe3a5e015f46ab58fa5375ef refs/tags/v1.0.0
e006ca815a5eba2e33b130386d5106fa5d7fb191 refs/tags/v1.0.0^{}
```

## Release Gate Results

Latest verified local release gate on the tagged commit:

```bash
.venv/bin/python -m pytest -q
REQUIRE_V1_TAG=1 bash scripts/v1_smoke.sh
.venv/bin/skill-agent eval --suite evals/v1_release.jsonl --skills-dir skills --runs-dir /tmp/skill-agent-v1-reviewfix-release
.venv/bin/python -m compileall -q app
git diff --check
```

Observed results:

- Full pytest: `279 passed`.
- Tag-required v1 smoke: passed.
- Capability-gap smoke eval inside v1 smoke: `4/4`.
- Lifecycle eval inside v1 smoke: `7/7`.
- Agent diagnostic eval inside v1 smoke: `16/16`.
- V1 release eval inside v1 smoke: `11/11`.
- Fixture compatibility checks inside v1 smoke: `6/6`.
- Release documentation checks inside v1 smoke: `6/6`.
- Direct v1 release eval: `11/11`.
- Compile app: passed.
- `git diff --check`: passed.
- CodeRabbit scoped review for the final v1 review-fix patch: `findings: 0`.
- Fresh private tag checkout, editable install, and `REQUIRE_V1_TAG=1 bash scripts/v1_smoke.sh`: passed on `e006ca815a5eba2e33b130386d5106fa5d7fb191`.

## Known Omissions

- No hosted service proof.
- No package publish proof.
- No public remote/tag proof.
- No marketplace proof.
- No true sandbox proof.
- No durable generated-skill admission proof.
- No positive stable-routing proof.
- No autonomous-promotion proof.

These omissions are intentional v1 boundaries, not hidden launch claims.
