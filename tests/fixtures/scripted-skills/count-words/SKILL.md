---
name: count-words
description: Count words in provided text with a local Python script.
tags:
  - text
  - words
  - count
metadata:
  version: "0.1.0"
  owner: "local"
  status: "candidate"
risk_level: "medium"
compatibility:
  python: ">=3.11"
allowed_tools:
  - python
permissions:
  read_files: false
  write_files: false
  network: false
  secrets: false
  execute_code: true
input_schema:
  text: string
output_schema:
  word_count: integer
validation:
  status: "pytest"
  notes: "Validated by local pytest tests before routing."
script:
  entrypoint: "scripts/count_words.py"
  timeout_seconds: 5
---

# Count Words

Count words in provided text using a local Python script. The script reads JSON from stdin and writes JSON to stdout.

