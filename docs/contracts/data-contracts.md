# Data Contracts

## Skill Request

```json
{
  "id": "skillreq_001",
  "task_id": "task_001",
  "missing_capability": "detect contradictions between claims",
  "reason": "The agent can extract claims but lacks a repeatable contradiction procedure.",
  "desired_skill_name": "detect-contradictions",
  "input_schema": {
    "claims": "array"
  },
  "output_schema": {
    "contradictions": "array",
    "confidence": "number"
  },
  "success_criteria": [
    "Finds direct contradiction",
    "Distinguishes contradiction from nuance",
    "Preserves source IDs"
  ],
  "failure_modes": [
    "If claims are unrelated, return no contradiction",
    "If scope or timing differs, mark as nuance instead of contradiction"
  ],
  "risk_level": "medium",
  "approval_required": false,
  "status": "requested"
}
```

## Capability Decision

```json
{
  "capability": "detect contradictions between claims",
  "decision": "REQUEST_SKILL",
  "reason": "No existing skill meets schema and quality threshold.",
  "best_match": {
    "skill_name": "compare-claims",
    "score": 0.62,
    "coverage": "partial"
  },
  "risk_level": "medium",
  "requires_human_approval": false
}
```

Allowed decisions:

```text
USE_SKILL
REQUEST_SKILL
CREATE_TEMP_SKILL
ASK_HUMAN
ABORT_UNSAFE
```

## Skill Record

```json
{
  "name": "detect-contradictions",
  "version": "0.2.1",
  "description": "Detects contradictions between atomic claims.",
  "status": "candidate",
  "input_schema": {},
  "output_schema": {},
  "allowed_tools": ["read_file", "python"],
  "risk_level": "medium",
  "tests": {
    "total": 12,
    "passing": 11
  },
  "metrics": {
    "uses": 23,
    "success_rate": 0.82,
    "human_correction_rate": 0.18
  },
  "last_used": "2026-05-29T10:00:00-07:00",
  "last_tested": "2026-05-29T09:30:00-07:00"
}
```

## Run Log

```json
{
  "task_id": "task_001",
  "task": "Compare two sources and find disagreements.",
  "plan": ["extract claims", "compare claims", "write summary"],
  "capability_decisions": [
    {
      "capability": "extract claims",
      "decision": "USE_SKILL",
      "skill": "extract-claims"
    },
    {
      "capability": "detect contradictions",
      "decision": "CREATE_TEMP_SKILL",
      "skill_request": "skillreq_001"
    }
  ],
  "skills_loaded": [
    {
      "name": "extract-claims",
      "reason": "Needed source-level factual claims."
    },
    {
      "name": "detect-contradictions",
      "reason": "Needed claim conflict detection."
    }
  ],
  "script_executions": [
    {
      "skill_name": "count-words",
      "command": ["python", "skills/count-words/scripts/count_words.py"],
      "returncode": 0,
      "stdout": "{\"word_count\": 6}",
      "stderr": "",
      "timed_out": false
    }
  ],
  "skill_requests": [
    {
      "id": "skillreq_001",
      "desired_skill_name": "detect-contradictions",
      "status": "requested",
      "temporary_skill": {
        "skill_name": "detect-contradictions",
        "skill_path": "skills/detect-contradictions/SKILL.md",
        "validation_passed": true,
        "validation_reasons": [],
        "loaded": true
      }
    }
  ],
  "result_quality": {
    "score": 0.78,
    "notes": "Missed one indirect contradiction."
  }
}
```

## Minimal `SKILL.md`

````markdown
---
name: extract-claims
description: Extracts atomic factual claims from articles, PDFs, transcripts, or reports. Use when a task requires comparing, verifying, deduplicating, or contradicting source statements.
compatibility: Requires Python 3.11+
metadata:
  version: "0.1.0"
  owner: "local"
  risk: "low"
  status: "candidate"
---

## What This Skill Does

Turn messy text into short, checkable claims.

## Inputs

- `text`: source text
- `source_id`: source label
- `granularity`: `coarse` or `fine`

## Output

```json
[
  {
    "claim": "string",
    "source_id": "string",
    "evidence_quote": "string",
    "confidence": 0.0
  }
]
```

## Procedure

1. Split text into candidate factual statements.
2. Remove opinions unless they contain factual assertions.
3. Keep each claim atomic.
4. Preserve source references.
5. Return JSON only.

## Failure Cases

- If text is too short, return an empty list.
- If claims are ambiguous, mark confidence below 0.5.
````
