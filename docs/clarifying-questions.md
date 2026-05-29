# Clarifying Questions

These are not blockers for the documentation. They are the questions that should shape the first implementation slice.

## Product Boundary

1. Should the first version be a local developer tool, a web demo, or both?
2. Is the first user a solo researcher, an AI builder, or someone evaluating agent behavior?
3. Should the product name stay generic for now, or should we pick a public-facing name early?

## Skill Scope

4. Should Phase 1 support only local skills, or should it also inspect external skill folders?
5. Should generated skills start as Markdown-only by policy, or should simple Python scripts be allowed behind approval?
6. Should skill promotion require human approval in every case?

## Interface

7. Is the "wow" demo a web UI with three panels, or should the first demo be a CLI trace that is easier to build?
8. Should the UI emphasize the blocked state, the skill inventory, or the final research artifact?
9. Should users be able to edit a skill request before Skillsmith drafts the skill?

## Memory and Metrics

10. Should the system remember only skill performance, or also user preferences about skill behavior?
11. How much run history should be preserved by default?
12. Should failed temporary skills be deleted, archived, or kept for repair?

## Safety

13. Should external skills be fully disallowed in the MVP?
14. Should network access be unavailable until Phase 4?
15. What operations should always require hard approval, even in local development?

