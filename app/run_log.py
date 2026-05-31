from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from app.models import RunLog


def write_run_log(run_log: RunLog, runs_dir: Path) -> Path:
    runs_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    shortid = uuid.uuid4().hex[:8]
    path = runs_dir / f"run_{timestamp}_{shortid}.json"
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(run_log.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp_path.replace(path)
    return path

