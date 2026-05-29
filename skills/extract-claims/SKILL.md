---
name: extract-claims
description: Extract atomic factual claims from source text for research comparison.
tags:
  - research
  - claims
  - extraction
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
  source_id: string
output_schema:
  claims: array
validation:
  status: "manual"
  notes: "Seed skill reviewed for M1."
---

# Extract Claims

Turn source text into short, atomic factual claims. Preserve the source label and avoid merging unrelated facts into one claim.

