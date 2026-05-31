---
name: write-structured-answer
description: Write a structured summary or answer from prepared research notes.
tags:
  - research
  - write
  - answer
  - summary
  - structured
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
  notes: array
  task: string
output_schema:
  answer: string
validation:
  status: "manual"
  notes: "Gauntlet safe fixture."
---

# Write Structured Answer

Turn prepared notes into a concise structured answer. Preserve uncertainty and avoid adding unsupported claims.
