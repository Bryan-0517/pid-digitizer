# CLAUDE.md

Follow `AGENTS.md` and `/docs` as the repository constitution.

Work on exactly one TASKS.md task at a time.

When a request is ambiguous, prefer the smallest implementation that satisfies the current task and preserves the documented architecture.

Never shortcut by:
- storing engineering semantics only in React state;
- making model-specific response types the domain model;
- querying an LLM for topology that can be answered from EngineeringGraph;
- making pyDEXPI the source of truth;
- inventing missing benchmark coordinates or connections.
