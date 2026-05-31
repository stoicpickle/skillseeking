# Critique: Agent Improvement Implementation Plan

## Context/Scope
Compared `docs/plans/agent-improvement-implementation-2026-05-29.md` against the original context-builder export at `prompt-exports/oracle-plan-2026-05-29-083651-agent-plan-29379d-daf8.md`. Scope is limited to plan quality and implementation-order risks.

## Findings

### 1) Top 3 under-specified seams
1. **Temporary registry/loading seam.** The plan says containment should shift to each `SkillRecord` having `source_root`/lifecycle (`docs/plans/agent-improvement-implementation-2026-05-29.md:134`) and Item 4 names `registry.py`, `skill_validator.py`, and `loader.py` (`:250-265`), but it does not specify whether `SkillRegistry.load()` accepts multiple roots, overlays temporary records, or creates a per-run registry instance. The export was more explicit: durable + optional temp roots, `SkillRecord.source_root`, and loader containment against that source root (`prompt-exports/oracle-plan-2026-05-29-083651-agent-plan-29379d-daf8.md:422-428`).
2. **Safety taxonomy/catalog cutoff.** The plan lists example actions for secrets, file reads, APIs, installs, and mutation (`docs/plans/...:138-147`) but leaves the classification vocabulary and matching precedence fuzzy. Implementers must guess whether safety applies to task text, planned capability, skill manifest permissions, or all three.
3. **Run/result category precedence.** The plan defines the result-category precedence list and Item 7 asserts that every run has exactly one `result_category`. Items 6–7 could cross-reference that list more prominently so implementers do not miss the ordering when safety stops, repair requests, route/load failures, and script failures overlap.

### 2) Specificity balance
- **Over-specified:** The recommended artifact path `runs/artifacts/<run_id>/skills` (`docs/plans/...:116-134`, `:254`) is a tactical storage choice. The implementation agent should own exact path/API shape as long as run-scoped, inspectable, and non-durable invariants hold.
- **Dropped useful framing:** The export emphasized docs may describe a richer future system and the plan should separate immediate MVP hardening from medium-term investments (`prompt-exports/...:63-68`). The plan mostly folds everything into 13 sequential items, making catalog, router explanations, JSON CLI, health v2, docs, and CI all appear equally necessary before completion.
- **Dropped useful specificity:** Export lines `422-426` gave concrete registry/load containment behavior; the plan reduces this to a single sentence at `docs/plans/...:134`, increasing implementation ambiguity.

### 3) Contradictions or missing dependencies
- **JSON/health mismatch:** The export notes JSON output for run/registry/health “as appropriate” (`prompt-exports/...:60`) and later notes health already has JSON output (`:99-100`). The plan’s Item 9 only covers run/registry (`docs/plans/...:329-340`), while Item 11 touches health metrics but not whether health JSON schema changes are required.
- **Capability catalog before safety may be too strict.** Item 6 depends on Item 5 (`docs/plans/...:278-293`), but a minimal safety classifier could land before full planner/requester catalog consolidation. This dependency may delay the P0 safety outcome.
- **Open questions are not actually none.** `docs/plans/...:422-423` says none blocking, but registry overlay strategy, safety classification source/precedence, and result-category precedence can change implementation order.

### 4) Risk of over-planning
Cut or defer detailed sequencing for Items 8–11 until P0 invariants pass: router ranked candidates, JSON CLI surfaces beyond needed result fields, script hardening breadth, and library health v2. Keep them as follow-up milestones unless they are directly required by run-scoped temps, explicit safety stops, or category logging.

### 5) Questions that would change implementation order
1. Should explicit safety decisions ship before the full capability catalog, using a small classifier, to unblock P0 sooner?
2. Should registry support multiple roots globally, or should `agent_loop` create a per-run overlay/temporary record list only for generated skills?
3. What is the result-category precedence order when safety, repair, route/load, and script failures overlap?
4. Is health JSON schema stabilization in scope for this pass, or only text/metric additions?
