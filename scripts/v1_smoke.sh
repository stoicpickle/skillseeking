#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

if [[ -x ".venv/bin/python" ]]; then
  PYTHON_BIN="${PYTHON_BIN:-.venv/bin/python}"
else
  PYTHON_BIN="${PYTHON_BIN:-python}"
fi

if [[ -x ".venv/bin/skill-agent" ]]; then
  SKILL_AGENT_BIN="${SKILL_AGENT_BIN:-.venv/bin/skill-agent}"
else
  SKILL_AGENT_BIN="${SKILL_AGENT_BIN:-skill-agent}"
fi

SMOKE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/skill-agent-v1-smoke.XXXXXX")"
cleanup() {
  rm -rf "${SMOKE_ROOT}"
}
trap cleanup EXIT

DURABLE_NO_MUTATION_TARGETS=(
  "skills"
  "docs/stable-routing-policy.md"
  "docs/plans/v1-stable-routing-policy-deferred-2026-06-06.md"
)

step() {
  printf '\n==> %s\n' "$1"
}

write_durable_snapshot() {
  local snapshot_path="$1"
  "${PYTHON_BIN}" - "${snapshot_path}" "${DURABLE_NO_MUTATION_TARGETS[@]}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

repo_root = Path.cwd().resolve()
snapshot_path = Path(sys.argv[1])
targets = list(sys.argv[2:])
files: dict[str, str] = {}
missing: list[str] = []

for target in targets:
    target_path = Path(target)
    if not target_path.exists():
        missing.append(target)
        continue
    if target_path.is_file():
        paths = [target_path]
    else:
        paths = sorted(path for path in target_path.rglob("*") if path.is_file())
    for path in paths:
        relative_path = path.resolve().relative_to(repo_root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files[relative_path] = f"sha256:{digest}"

if missing:
    raise SystemExit(f"missing durable no-mutation target(s): {', '.join(missing)}")

with snapshot_path.open("w", encoding="utf-8") as handle:
    json.dump({"targets": targets, "files": files}, handle, indent=2, sort_keys=True)
    handle.write("\n")

print(f"snapshot recorded {len(files)} durable file(s)")
PY
}

assert_durable_no_mutation() {
  local before_path="$1"
  local after_path="$2"
  "${PYTHON_BIN}" - "${before_path}" "${after_path}" <<'PY'
import json
import sys
from pathlib import Path

before = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["files"]
after = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))["files"]

before_paths = set(before)
after_paths = set(after)
added = sorted(after_paths - before_paths)
removed = sorted(before_paths - after_paths)
changed = sorted(path for path in before_paths & after_paths if before[path] != after[path])

if added or removed or changed:
    print("Durable mutation detected during v1 smoke:", file=sys.stderr)
    for label, paths in (("added", added), ("removed", removed), ("changed", changed)):
        if paths:
            print(f"  {label}:", file=sys.stderr)
            for path in paths:
                print(f"    {path}", file=sys.stderr)
    raise SystemExit(1)

print("durable skills and stable-routing policy unchanged")
PY
}

step "Repo root"
printf '%s\n' "${REPO_ROOT}"

step "Python version"
"${PYTHON_BIN}" --version

step "Durable no-mutation baseline"
write_durable_snapshot "${SMOKE_ROOT}/durable-before.json"

step "Required files"
for path in \
  "pyproject.toml" \
  "README.md" \
  "CHANGELOG.md" \
  "docs/v1-release-contract.md" \
  "docs/v1-release-notes.md" \
  "docs/v1-release-tasking.md" \
  "evals/v1_release.jsonl" \
  "scripts/run_gauntlet_demo.py"; do
  test -f "${path}" || {
    printf 'Missing required file: %s\n' "${path}" >&2
    exit 1
  }
  printf 'found %s\n' "${path}"
done

step "Version is stamped as 1.0.0"
"${PYTHON_BIN}" - <<'PY'
from pathlib import Path
import tomllib

data = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
version = data["project"]["version"]
if version != "1.0.0":
    raise SystemExit(f"pyproject.toml version must be 1.0.0 for v1 smoke, got {version}")
print("pyproject.toml is stamped 1.0.0")
PY

step "Release docs are stamped"
"${PYTHON_BIN}" - <<'PY'
from pathlib import Path

required = {
    "README.md": ["v1.0 local CLI release", "1.0.0", "v1.0.0"],
    "CHANGELOG.md": ["## [1.0.0] - 2026-06-06", "v1.0.0"],
    "docs/v1-release-notes.md": ["Status: v1.0 local CLI release", "Package version: `1.0.0`", "Git release tag: `v1.0.0`"],
    "docs/v1-release-contract.md": ["Status: v1.0 local CLI release", "set to `1.0.0`", "`v1.0.0`"],
}
for path, needles in required.items():
    text = Path(path).read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"{path} missing release marker: {needle}")
print("release docs are stamped")
PY

if [[ "${REQUIRE_V1_TAG:-0}" == "1" ]]; then
  step "V1 git tag exists"
  git rev-parse --verify refs/tags/v1.0.0 >/dev/null
  printf 'v1.0.0 tag exists\n'
fi

step "Package and CLI availability"
"${PYTHON_BIN}" - <<'PY'
import app.cli
import app.agent_loop

print("app imports ok")
PY
"${SKILL_AGENT_BIN}" --help >/dev/null
"${SKILL_AGENT_BIN}" v1-local-use --help >/dev/null
"${SKILL_AGENT_BIN}" candidate-decision --help >/dev/null
"${SKILL_AGENT_BIN}" v1-local-use --json >"${SMOKE_ROOT}/v1-local-use.json"
"${PYTHON_BIN}" - "${SMOKE_ROOT}/v1-local-use.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if data.get("primary_command") != "shadow-managed-write":
    raise SystemExit("v1-local-use does not point to shadow-managed-write")
if data.get("mutation_surface") != "managed prefix only":
    raise SystemExit("v1-local-use changed the managed-prefix mutation boundary")
if data.get("stable_routing_policy") != "deferred_for_v1":
    raise SystemExit("v1-local-use must defer stable routing for v1")
if "stable routing" not in data.get("unchanged_authority", []):
    raise SystemExit("v1-local-use must keep stable routing unchanged")
if "durable skills admission" not in data.get("excluded_authority", []):
    raise SystemExit("v1-local-use must exclude durable skills admission")
print("v1-local-use ok")
PY
printf 'skill-agent CLI ok\n'

step "Skill Gauntlet demo"
GAUNTLET_OUTPUT="${SMOKE_ROOT}/gauntlet.out"
"${PYTHON_BIN}" scripts/run_gauntlet_demo.py --runs-dir "${SMOKE_ROOT}/gauntlet-runs" >"${GAUNTLET_OUTPUT}"
grep -q "SKILL GAUNTLET" "${GAUNTLET_OUTPUT}"
grep -q "Result category:" "${GAUNTLET_OUTPUT}"
printf 'gauntlet ok\n'

step "Capability-gap smoke eval"
"${SKILL_AGENT_BIN}" eval \
  --suite evals/capgap_smoke.jsonl \
  --skills-dir skills \
  --runs-dir "${SMOKE_ROOT}/evals/capgap-smoke"

step "Lifecycle eval"
"${SKILL_AGENT_BIN}" eval \
  --suite evals/skill_lifecycle_v0.jsonl \
  --skills-dir skills \
  --runs-dir "${SMOKE_ROOT}/evals/lifecycle"

step "Agent diagnostic eval"
"${SKILL_AGENT_BIN}" eval \
  --suite evals/agent_diagnostic_v0.jsonl \
  --skills-dir skills \
  --runs-dir "${SMOKE_ROOT}/evals/diagnostic"

step "V1 release eval"
"${SKILL_AGENT_BIN}" eval \
  --suite evals/v1_release.jsonl \
  --skills-dir skills \
  --runs-dir "${SMOKE_ROOT}/evals/v1-release"

step "V1 fixture compatibility"
"${PYTHON_BIN}" -m pytest -q tests/test_v1_fixture_compatibility.py

step "V1 release documentation"
"${PYTHON_BIN}" -m pytest -q tests/test_v1_release_docs.py

step "Candidate decision isolated proof"
CANDIDATE_RUNS="${SMOKE_ROOT}/candidate-decision-runs"
"${SKILL_AGENT_BIN}" run \
  "Cluster arguments from these sources." \
  --skills-dir skills \
  --runs-dir "${CANDIDATE_RUNS}" >"${SMOKE_ROOT}/candidate-run.out"
CANDIDATE_ID="$("${PYTHON_BIN}" - "${CANDIDATE_RUNS}" <<'PY'
import json
import sys
from pathlib import Path

ledger_path = Path(sys.argv[1]) / "skill_candidate_ledger.json"
ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
entries = ledger.get("entries", [])
if not entries:
    raise SystemExit("candidate ledger has no entries")
print(entries[0]["candidate_id"])
PY
)"
"${SKILL_AGENT_BIN}" candidate-decision "${CANDIDATE_ID}" \
  --skills-dir skills \
  --runs-dir "${CANDIDATE_RUNS}" \
  --json >"${SMOKE_ROOT}/candidate-decision.json"
"${PYTHON_BIN}" - "${SMOKE_ROOT}/candidate-decision.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
required = {"candidate_id", "decision", "why", "next_command"}
missing = sorted(required - set(data))
if missing:
    raise SystemExit(f"candidate-decision output missing fields: {missing}")
if data.get("durable_skills_mutated") is not False:
    raise SystemExit("candidate-decision unexpectedly reports durable skill mutation")
if data.get("stable_routing_enabled") is not False:
    raise SystemExit("candidate-decision unexpectedly reports stable routing enabled")
print(f"candidate-decision ok: {data['decision']}")
PY

step "Compile app"
"${PYTHON_BIN}" -m compileall -q app

step "Durable no-mutation check"
write_durable_snapshot "${SMOKE_ROOT}/durable-after.json"
assert_durable_no_mutation \
  "${SMOKE_ROOT}/durable-before.json" \
  "${SMOKE_ROOT}/durable-after.json"

printf '\nV1 smoke passed. Evidence directory was temporary: %s\n' "${SMOKE_ROOT}"
