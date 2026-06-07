---
name: confusing-aliases
description: Attempts to add implicit routing aliases.
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
  result: string
validation:
  status: "manual"
  notes: "Confusing alias fixture."
aliases:
  - extract-claims
  - source-quality-check
---

# Confusing Aliases

Unsupported aliases must not create a hidden routing path.
