---
name: validate-skill-md
description: Validate local SKILL.md Markdown skill files for required metadata and safety constraints.
tags:
  - skill
  - validate
  - markdown
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
  skill_markdown: string
output_schema:
  validation_result: object
validation:
  status: "manual"
  notes: "Seed skill reviewed for M1."
---

# Validate SKILL.md

Check a Markdown skill for required metadata, safe permissions, and clear procedural boundaries.

