---
name: source-quality-check
description: Score source quality, credibility, reliability, and relevance for research tasks.
tags:
  - research
  - source
  - quality
  - credible
  - reliable
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
  source_text: string
  source_metadata: object
output_schema:
  source_quality: object
validation:
  status: "manual"
  notes: "Gauntlet safe fixture."
---

# Source Quality Check

Assess whether a source is credible, relevant, specific, and useful for the current research question.
