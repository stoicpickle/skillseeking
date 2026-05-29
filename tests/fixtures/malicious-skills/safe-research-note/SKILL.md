---
name: safe-research-note
description: Safely extracts short research notes from plain text.
tags:
  - research
metadata:
  version: "0.1.0"
  owner: "local"
  status: "candidate"
risk_level: "low"
compatibility:
  python: ">=3.11"
allowed_tools: []
permissions:
  read_files: false
  write_files: false
  network: false
  secrets: false
  execute_code: false
input_schema:
  text: string
output_schema:
  notes: array
validation:
  status: "manual"
  notes: "Safe control fixture."
---

# Safe Research Note

Extract concise notes from user-provided text.
