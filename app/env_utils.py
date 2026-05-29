from __future__ import annotations

import os


def safe_env(include_home: bool = False) -> dict[str, str]:
    allowed = {
        "PATH",
        "PYTHONPATH",
        "PYTHONHOME",
        "VIRTUAL_ENV",
        "TMPDIR",
        "TEMP",
        "TMP",
        "LC_ALL",
        "LANG",
    }
    if include_home:
        allowed.add("HOME")
    return {key: value for key, value in os.environ.items() if key in allowed}

