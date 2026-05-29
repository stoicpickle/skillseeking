---
name: invalid_name
description: This fixture has an invalid name.
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
---

# Invalid Name

This fixture has an underscore in its name.

