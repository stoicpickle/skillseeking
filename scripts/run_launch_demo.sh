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

DEMO_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/skill-agent-launch-demo.XXXXXX")"
cleanup() {
  rm -rf "${DEMO_ROOT}"
}
trap cleanup EXIT

DEMO_SKILLS="${DEMO_ROOT}/skills"
DEMO_RUNS="${DEMO_ROOT}/runs"
cp -R "${REPO_ROOT}/skills" "${DEMO_SKILLS}"

step() {
  printf '\n==> %s\n' "$1"
}

printf 'LAUNCH DEMO\n'
printf 'Local CLI governed capability-gap loop\n'
printf 'Demo workspace: %s\n' "${DEMO_ROOT}"

step "1. Capability gap run"
"${SKILL_AGENT_BIN}" run \
  "Cluster arguments from these sources." \
  --skills-dir "${DEMO_SKILLS}" \
  --runs-dir "${DEMO_RUNS}"

step "2. Candidate decision"
CANDIDATE_ID="$("${PYTHON_BIN}" - "${DEMO_RUNS}" <<'PY'
import json
import sys
from pathlib import Path

ledger_path = Path(sys.argv[1]) / "skill_candidate_ledger.json"
if not ledger_path.exists():
    raise SystemExit(f"missing candidate ledger: {ledger_path}")
ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
entries = ledger.get("entries", [])
if not entries:
    raise SystemExit("candidate ledger has no entries")
print(entries[0]["candidate_id"])
PY
)"
printf 'Candidate ID: %s\n' "${CANDIDATE_ID}"
"${SKILL_AGENT_BIN}" candidate-decision "${CANDIDATE_ID}" \
  --skills-dir "${DEMO_SKILLS}" \
  --runs-dir "${DEMO_RUNS}"

step "3. Boundary check"
"${SKILL_AGENT_BIN}" candidate-decision "${CANDIDATE_ID}" \
  --skills-dir "${DEMO_SKILLS}" \
  --runs-dir "${DEMO_RUNS}" \
  --json >"${DEMO_ROOT}/candidate-decision.json"
"${PYTHON_BIN}" - "${DEMO_ROOT}/candidate-decision.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
durable_mutated = bool(data.get("durable_skills_mutated"))
stable_routing = bool(data.get("stable_routing_enabled"))
decision = data.get("decision", "unknown")
approval_granted = bool(data.get("approval_granted"))
install_authorized = bool(data.get("install_authorized"))
stable_review_required = bool(
    (data.get("stable_readiness") or {}).get("stable_review_approval_required")
)
human_review_required = decision == "ask_human" or stable_review_required
print(f"Candidate decision: {decision}")
print(f"Human review required: {'yes' if human_review_required else 'no'}")
print(f"Durable skills mutated: {'yes' if durable_mutated else 'no'}")
print(f"Stable routing enabled: {'yes' if stable_routing else 'no'}")
print("Hosted service used: no")
print("Sandbox provided: no")
if durable_mutated:
    raise SystemExit("launch demo must not mutate durable skills")
if stable_routing:
    raise SystemExit("launch demo must not enable stable routing")
if approval_granted:
    raise SystemExit("launch demo must not grant approval")
if install_authorized:
    raise SystemExit("launch demo must not authorize installation")
if not human_review_required:
    raise SystemExit("launch demo must stop at human review")
PY

printf '\nLaunch demo complete. Temporary evidence was removed with %s\n' "${DEMO_ROOT}"
