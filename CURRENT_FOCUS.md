# CURRENT_FOCUS.md

**Project:** Loom Core
The single most important thing right now. This file overrides chat history.

---

## Focus

**Phase 2 is underway.** Distillation Loop, Orchestrator, and Context Packer are
done. Next: the **Coding Support Loop** (spec §4.3), then the
**Meta/Self-Improvement Loop** (spec §4.4) with the skill/tool lifecycle.

## What exists now

- Phase 1 memory core: `models`, `paths`, `store`, `cli` (memory subcommands).
- Phase 2 so far: `loops/base` (Loop/Task/LoopResult/OwnershipBroker),
  `orchestrator` (ownership + dispatch + context assembly), `context`
  (ranked packing within a token budget), `loops/distillation`.
- CLI: `loom memory ...`, `loom pack`, `loom distill`.
- Quality gates: `pytest` (35), `ruff check .`, `python -m mypy` — all green.

## Constraints to keep in mind

- Only the Orchestrator grants/revokes ownership; loops use the broker (§6).
- Never overwrite a promoted skill — new version for content changes; stat
  updates mutate counts in place (§3.3/§5.3).
- Context packs must respect the token budget and record why entries were
  included (§3.5). Ranking weights live in DEC-005 (tunable).

## Not now (deferred)

- Vector index, tool auto-promotion policy, multi-project isolation (§11).
- Persisting ownership/heartbeats across processes (DEC-004).
