from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_count_words_script_contract():
    skill_dir = Path(__file__).resolve().parents[1]
    script = skill_dir / "scripts" / "count_words.py"

    result = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps({"text": "one two two"}),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout) == {"word_count": 3}

