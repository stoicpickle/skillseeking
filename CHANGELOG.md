# Changelog

All notable release-candidate changes are tracked here. The authoritative package version stamp remains `pyproject.toml:project.version`.

## Unreleased

### Added

- Local v1 CLI release-candidate documentation for governed capability acquisition.
- `docs/v1-release-notes.md` with current abilities, explicit boundaries, verification commands, and remaining final-gate work.
- A v1 release tasking and contract trail that separates local CLI readiness from hosted, marketplace, production-safe, or true-sandbox claims.
- Representative v1 data-contract fixtures for run logs, candidate ledgers, input resolutions, checkpoints, candidate decisions, and eval reports.
- `scripts/v1_smoke.sh` as the canonical local readiness smoke path.

### Changed

- README positioning now describes the repo as a local v1 CLI release candidate instead of a research-only prototype.
- V1 stable local use is framed as managed-prefix-first through `skill-agent shadow-managed-write` and `skill-agent v1-local-use`.
- Stable routing is explicitly deferred for v1 and remains post-v1 work.

### Not Yet Released

- `pyproject.toml` has not been stamped as `1.0.0`.
- No `1.0.0` tag or published release exists from this slice.
- Durable `skills/` admission and positive stable routing are not enabled for v1.
