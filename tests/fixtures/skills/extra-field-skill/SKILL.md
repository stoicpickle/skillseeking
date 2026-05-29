---
name: extra-field-skill
description: This fixture includes an unexpected manifest field.
tags: []
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
  notes: "Fixture."
unexpected_manifest_field: "should not be accepted"
---

# Extra Field Skill

This fixture should be rejected because the manifest contains an unexpected field.

