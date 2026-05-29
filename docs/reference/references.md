# References

These references informed the concept brief. Verify specific implementation details against the current source documentation before coding against an API.

## Agent Skills

- Agent Skills overview: https://agentskills.io/home
- Agent Skills specification: https://agentskills.io/specification
- Anthropic engineering writeup on Agent Skills: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills

Relevant design takeaways:

- Skills can be represented as portable folders.
- Compact metadata can be loaded before full instructions.
- Full skill instructions, scripts, references, and assets should be loaded only when needed.

## Tool and Agent Frameworks

- Model Context Protocol tool specification: https://modelcontextprotocol.io/specification/2025-06-18/server/tools
- OpenAI Agents SDK tools documentation: https://openai.github.io/openai-agents-python/tools/

Relevant design takeaways:

- Tools should be exposed with clear controls.
- Approval and filtering matter for safety-sensitive capabilities.
- Agents SDK primitives can support function tools, agent-as-tool patterns, handoffs, guardrails, tracing, and dynamic tool filtering.

## Research

- Toolformer: https://arxiv.org/abs/2302.04761
- Voyager: https://arxiv.org/abs/2305.16291
- SkillFoundry: https://arxiv.org/html/2604.03964v1
- SkillOps: https://arxiv.org/html/2605.13716v1
- SKILL.md supply-chain attack paper: https://arxiv.org/abs/2605.11418

Relevant design takeaways:

- Tool use can be learned and selected conditionally.
- Reusable executable skill libraries can improve task performance.
- Skill libraries require validation, repair, merge, and retirement workflows.
- Skill metadata and prose can influence discovery and selection, so skills need package-like safety treatment.

## Current Docs Check

Context7 was used during this documentation pass to check current OpenAI Agents SDK concepts relevant to:

- Tools.
- Agent-as-tool patterns.
- Handoffs.
- Dynamic tool filtering.
- Guardrails.
- Tracing and sessions.

