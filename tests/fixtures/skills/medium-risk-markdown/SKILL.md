---
name: medium-risk-markdown
description: This non-scripted Markdown skill should be rejected because it is medium risk.
tags: []
metadata:
  version: "0.1.0"
  owner: "local"
  status: "candidate"
risk_level: "medium"
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

# Medium Risk Markdown

This fixture is medium risk and should be rejected because non-scripted skills must be low risk.
