from __future__ import annotations

import json
import re
from pathlib import Path

from app.models import RunLog, new_default_run_id


def new_run_id() -> str:
    return new_default_run_id()


def write_run_log(run_log: RunLog, runs_dir: Path) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = run_log.created_at.strftime("%Y%m%d_%H%M%S")
    run_id = _filename_safe_run_id(run_log.run_id)
    path = runs_dir / f"run_{timestamp}_{run_id}.json"
    return rewrite_run_log(path, run_log)


def rewrite_run_log(path: Path, run_log: RunLog) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(run_log.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)
    return path


def _filename_safe_run_id(run_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "-", run_id).strip("-")
    return safe or new_run_id()

