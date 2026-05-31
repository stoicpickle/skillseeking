from __future__ import annotations

import argparse
import tempfile
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from app.agent_loop import run_task
from app.registry import SkillRegistry


GAUNTLET_TASK = (
    "Extract claims from these messy research notes, cluster arguments, "
    "run local Python analysis, score source quality, and write a structured summary."
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Skill Gauntlet demo.")
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=REPO_ROOT / "tests" / "fixtures" / "gauntlet-skills",
        help="Skill library to use for the gauntlet.",
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=None,
        help="Run-log directory. Defaults to a temporary directory.",
    )
    args = parser.parse_args()

    runs_dir = args.runs_dir or Path(tempfile.mkdtemp(prefix="skill-gauntlet-runs-"))
    registry = SkillRegistry.load(args.skills_dir)
    result = run_task(GAUNTLET_TASK, skills_dir=args.skills_dir, runs_dir=runs_dir)

    accepted = [record.name for record in registry.list_records()]
    rejected = registry.rejections()
    summary = result.run_log.execution_summary
    safe_loaded = [skill.name for skill in result.run_log.skills_loaded if not skill.temporary]
    temp_loaded = [skill.name for skill in result.run_log.skills_loaded if skill.temporary]

    print("SKILL GAUNTLET")
    print("")
    print("TASK")
    print(GAUNTLET_TASK)
    print("")
    print("REGISTRY")
    print(f"Accepted skills: {len(accepted)}")
    for name in accepted:
        print(f"  - {name}")
    print(f"Rejected skills: {len(rejected)}")
    for rejection in rejected:
        reason = "; ".join(rejection.reasons)
        print(f"  - {rejection.name or rejection.path.parent.name}: {reason}")
    print("")
    print("TRACE")
    for event in result.run_log.trace_events:
        label = event.stage
        if "skill_name" in event.details:
            label = f"{label} {event.details['skill_name']}"
        elif "capability" in event.details:
            label = f"{label} {event.details['capability']}"
        print(label)
    print("")
    print("RESULT")
    print(f"Safe skills loaded: {_format(safe_loaded)}")
    print(f"Temporary skills loaded: {_format(temp_loaded)}")
    print(f"Requested skills: {_format(summary.requested_skills)}")
    print(f"Rejected skills: {_format(summary.rejected_skills)}")
    print(f"Repair requests: {_format(summary.repair_requested_skills)}")
    print(f"Result category: {result.run_log.result_category}")
    print(f"Exit code: {result.exit_code}")
    print(f"Run log: {result.run_log_path}")


def _format(values: list[str]) -> str:
    return ", ".join(values) if values else "-"


if __name__ == "__main__":
    main()
