---
name: compare-claims
description: Compare factual claims for overlap, difference, similarity, or tension.
tags:
  - research
  - claims
  - compare
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
  claims: array
output_schema:
  comparisons: array
validation:
  status: "manual"
  notes: "Seed skill reviewed for M1."
---

# Compare Claims

Compare two or more atomic claims and describe whether they make the same point, differ in scope, or introduce tension.

