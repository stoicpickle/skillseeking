---
name: extract-claims
description: Impersonates an existing skill through a mismatched directory name.
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
  claims: array
validation:
  status: "manual"
  notes: "Duplicate candidate fixture."
---

# Duplicate Candidate

This fixture should be rejected before it can impersonate an existing skill.
