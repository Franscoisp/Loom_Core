# CURRENT_FOCUS.md

**Project:** Loom Core
The single most important thing right now. This file overrides chat history.

---

## Focus

**Transition from Phase 0 (Foundation) to Phase 1 (Memory MVP).**

Immediate next action: **TASK-010** — define Pydantic models for all memory
entry types per the Universal Memory Entry Schema (spec §3.3), including the
extra fields for skills/tools and episodes.

## Constraints to keep in mind

- Every memory file = YAML frontmatter (schema §3.3) + Markdown body.
- File naming rules are strict (spec §3.4). Never overwrite a promoted skill —
  create a new version.
- Validation must reject malformed entries (TASK-015).
- Tests use temporary directories, never the real `data/` (TASK-016).

## Not now (deferred)

- Loops, Orchestrator, context packing, vector index, tool auto-promotion.
