# Product Brief

## Working Name

Skill-Seeking Agent.

Alternative names:

- SkillForge
- NeoSkill
- Capability Loader
- Skill Request Agent

## One-Line Description

An agent that notices when it lacks a capability, requests a specific validated skill, loads it only after approval or tests, and logs whether that skill actually helped.

## Problem

Most agents fail in one of three unhelpful ways:

- They hallucinate competence.
- They ask the user to debug an invisible capability gap.
- They accumulate too many tools and skills until selection becomes unreliable.

The missing product surface is not another tool drawer. It is a visible capability gap:

```text
I cannot complete this reliably with my current skills.
I need a skill that does X.
It should accept Y and return Z.
It should pass W before I use it.
```

## Product Thesis

An agent becomes more trustworthy when it can expose its limitations as structured requests instead of hiding them inside prose, failed tool calls, or low-confidence output.

The sharper wedge is not an agent marketplace. It is the control layer that turns repeated operational friction into validated, human-governed agent skills.

Every metaphor for smarter agents should become a concrete control primitive: a knob, ledger entry, test assertion, or state transition. See `docs/homeostatic-governor.md` for the planned governor addition.

## Go-To-Market Boundary

The first public motion is local CLI credibility plus reviewer learning, not a hosted product launch or marketplace. The repo is MIT-licensed open source for the local CLI dev-preview, while future commercial exploration should stay secondary to evidence dashboards, approval workflows, audit trails, policy-controlled skill admission, private registries, eval management, and compliance proof packets.

Do not lead with a public skill marketplace. Do not treat this strategy boundary as approval to add hosted service behavior, production-safety claims, true sandboxing claims, autonomous promotion, durable generated-skill admission, or positive stable routing.

## Core Loop

```text
Task arrives
-> agent attempts to plan
-> agent checks available skills
-> agent detects missing capability
-> agent writes a skill request
-> system retrieves, builds, or asks for the skill
-> skill is validated
-> agent loads the skill
-> task continues
-> outcome is logged
-> useful skills are kept, weak skills are repaired or retired
```

Durable promotion remains human-governed. The system can detect capability gaps, draft or request candidates, validate them, quarantine unsafe versions, and explain what evidence would justify promotion. It should not silently promote generated skills into the durable library.

## Five Product Powers

### 1. Notice Limitation

The agent must make a forced decision before execution:

```text
Can I complete this with current skills?

- yes, proceed
- yes, but with uncertainty
- no, missing skill
- no, missing data
- no, unsafe or permission needed
```

The valuable moment is not failure. It is specific failure.

### 2. Describe the Missing Skill

A skill request should be structured, inspectable, and testable:

```json
{
  "skill_name": "pdf-table-extraction",
  "need": "Extract structured tables from PDF pages",
  "reason_blocked": "The answer depends on tables embedded in the uploaded PDF",
  "input_schema": {
    "file_path": "string",
    "page_range": "optional string"
  },
  "output_schema": {
    "tables": "array of markdown tables",
    "page_numbers": "array of integers",
    "confidence": "number"
  },
  "success_tests": [
    "Extracts at least one table from sample PDF",
    "Preserves row and column labels",
    "Returns page numbers",
    "Fails cleanly on PDFs with no tables"
  ],
  "risk_level": "low",
  "requires_human_approval": false
}
```

### 3. Find an Existing Skill

The system searches a skill registry using:

- Skill name.
- Description.
- Tags.
- Input and output schema.
- Allowed tool permissions.
- Past success rate.
- Environment compatibility.
- Risk level.
- Freshness.

This must not be embedding-only retrieval. Skill metadata can influence selection, and malicious or sloppy metadata can distort routing.

### 4. Create a Temporary Skill If None Exists

If no skill exists, a separate Skillsmith drafts one. The main task agent should request the skill, not immediately create it for itself.

For the MVP, generated skills are Markdown-only. Scripted skills come later.

### 5. Keep, Repair, or Retire Skills

Every skill use should update the library:

```text
Skill: detect-contradictions
Used: 18 times
Success: 14
Partial: 3
Failed: 1
Average user correction rate: low
Last validated: 2026-05-29
Status: keep
```

The skill library is a software asset, not a junk drawer.

## First Domain

Start with research workflows because capability gaps are obvious and output quality is inspectable.

Initial skills:

1. `search-sources`
2. `extract-claims`
3. `score-source-quality`
4. `detect-contradictions`
5. `build-evidence-table`
6. `write-cited-summary`

## Best First Demo

Use this task:

```text
Analyze these three short articles and find where they agree, disagree, or make unsupported claims.
```

The UI should make this trace visible:

```text
Planning
Checking skills
Blocked
Requesting skill
Validating skill
Loading skill
Executing
Reviewing
Promoting or retiring skill
```

The shareable screenshot is:

```text
BLOCKED -> REQUESTED SKILL -> VALIDATED -> LOADED -> CONTINUED
```
