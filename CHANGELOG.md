# Changelog

All notable release changes are tracked here. The authoritative package version stamp remains `pyproject.toml:project.version`.

## Unreleased

### Added

- `skill-agent feedback-session-template` prints the canonical design-partner
  session block for manual feedback-log capture without appending to the log,
  updating rollups, or enabling new authority.
- `skill-agent feedback-session-append` previews or records one design-partner
  session in the selected feedback log, updating only objective rollup counters
  and no new authority.
- `skill-agent feedback-log-summary` reports design-partner feedback synthesis
  readiness without mutating the feedback log or enabling new authority.

## [1.0.0] - 2026-06-06

### Added

- Local v1 CLI release for governed capability acquisition.
- `docs/v1-release-notes.md` with current abilities, explicit boundaries, verification commands, and remaining final-gate work.
- A v1 release tasking and contract trail that separates local CLI readiness from hosted, marketplace, production-safe, or true-sandbox claims.
- Representative v1 data-contract fixtures for run logs, candidate ledgers, input resolutions, checkpoints, candidate decisions, and eval reports.
- `scripts/v1_smoke.sh` as the canonical local readiness smoke path.

### Changed

- README positioning now describes the repo as a v1.0 local CLI release instead of a research-only prototype.
- V1 stable local use is framed as managed-prefix-first through `skill-agent shadow-managed-write` and `skill-agent v1-local-use`.
- Stable routing is explicitly deferred for v1 and remains post-v1 work.

### Release State

- `pyproject.toml` is stamped as `1.0.0`.
- The matching Git release tag is `v1.0.0`.
- This is a local CLI release, not a hosted or package-published release.
- Durable `skills/` admission and positive stable routing are not enabled for v1.
