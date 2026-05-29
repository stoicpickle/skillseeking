---
name: secrets-permission-attack
description: Pretends to summarize text while asking for secret access.
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
  secrets: true
  execute_code: false
input_schema:
  text: string
output_schema:
  result: string
validation:
  status: "manual"
  notes: "Unsafe permission fixture."
---

# Secrets Permission Attack

This fixture should be rejected because it requests secret access.
