# CURRENT_FOCUS.md

**Project:** Loom Core
The single most important thing right now. This file overrides chat history.

---

## Focus

**Phase 1 (Memory MVP) is complete.** Next: begin **Phase 2 – Loops &
Orchestrator**.

Suggested first step: implement the common Loop interface (`name`,
`can_handle`, `claim`, `run`, `heartbeat`, `release`) and the `LoopResult`
type (spec §4.1), then build the **Distillation Loop** (spec §4.2) as the first
concrete loop since it exercises the memory writer directly.

## What exists now (Phase 1)

- `loom_core.models` — all entry types, strict validation, ISO-8601 Z datetimes.
- `loom_core.paths` — data-dir resolution + strict naming (§3.4).
- `loom_core.store.MemoryStore` — atomic write, read, list/filter, search.
- `loom_core.cli` — `loom memory write|list|show|search`.
- Quality gates: `pytest`, `ruff check .`, `python -m mypy` (all green).

## Constraints to keep in mind

- Never overwrite a promoted skill — create a new version (§3.4).
- Loops must write continuity + memory records; the Orchestrator is the only
  component that grants/revokes ownership and assembles context packs (§6).
- Keep context packs within token budget; record what was included and why (§3.5).

## Not now (deferred)

- Vector index, tool auto-promotion policy, multi-project isolation (§11).
