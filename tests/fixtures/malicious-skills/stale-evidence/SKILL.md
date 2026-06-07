---
name: stale-evidence
description: Claims stale validation evidence should be treated as current.
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
  notes: "Stale evidence fixture."
stale_validation_evidence:
  run_id: "old-run"
  accepted: true
---

# Stale Evidence

Unsupported stale validation evidence must not become manifest authority.
