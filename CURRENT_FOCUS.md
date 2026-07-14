# CURRENT_FOCUS.md

**Project:** Loom Core
The single most important thing right now. This file overrides chat history.

---

## Focus

**Phase 2 is complete.** All four loop roles exist (Distillation, Coding
Support, Meta/Self-Improvement) plus the Orchestrator, Context Packer, and Tool
Registry. Next: **Phase 3** — value metrics (§8), loop-driven continuity-file
enforcement (§6 step 8, §7), and persisting ownership/heartbeats (DEC-004).

## What exists now

- Memory core: `models`, `paths`, `store` (write/read/list/search + skill-stat
  & versioning helpers), `cli` (`memory ...`).
- Loops: `loops/base`, `loops/distillation` (§4.2), `loops/coding_support`
  (§4.3), `loops/meta` (§4.4).
- `orchestrator` (ownership + dispatch + context assembly), `context`
  (ranked packing + `ContextProvider`), `registry` (tool registry §5.4).
- CLI: `loom memory ...`, `loom pack`, `loom distill`, `loom meta detect|run`,
  `loom tools list`.
- Quality gates: `pytest` (46), `ruff check .`, `python -m mypy` — all green.

## Constraints to keep in mind

- Only the Orchestrator grants/revokes ownership; loops use the broker (§6).
- Skill/tool content changes create a new version; stat updates mutate counts
  in place (§3.3/§5.3). Promotion requires evidence + expected improvement +
  success metric (§4.4.4).
- Context packs respect the token budget and record rationale (§3.5).

## Not now (deferred)

- Vector index, tool auto-promotion policy, multi-project isolation (§11).
- Executable implementations behind candidate tools (§4.4.6).
