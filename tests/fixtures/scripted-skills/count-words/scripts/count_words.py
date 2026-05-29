from __future__ import annotations

import json
import re
import sys


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def main() -> None:
    payload = json.loads(sys.stdin.read() or "{}")
    text = str(payload.get("text", ""))
    print(json.dumps({"word_count": count_words(text)}))


if __name__ == "__main__":
    main()

