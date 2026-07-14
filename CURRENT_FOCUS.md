# CURRENT_FOCUS.md

**Project:** Loom Core
The single most important thing right now. This file overrides chat history.

---

## Focus

**Phases 0–3 are complete.** Loom Core now has the full memory system, all four
loop roles, the Orchestrator, context packing, tool registry, value metrics,
persistent ownership, and continuity enforcement.

Suggested next work (all backlog, none blocking):
- Executable implementations behind candidate tools (§4.4.6).
- A retrieval upgrade / optional vector index (§11 open question).
- Loop-driven auto-write of continuity records on every dispatch (§6 step 8).

## What exists now

- Memory core: `models`, `paths`, `store` (+ skill-stat/versioning helpers), CLI.
- Loops: `loops/base`, `distillation` (§4.2), `coding_support` (§4.3),
  `meta` (§4.4).
- `orchestrator` (ownership + dispatch + context + metric wiring), `context`
  (ranked packing + `ContextProvider`), `registry` (tools §5.4),
  `ownership` (persistent, TTL reclamation §7), `metrics` (§8),
  `continuity` (§7 guard).
- CLI: `loom memory ...`, `pack`, `distill`, `meta detect|run`, `tools list`,
  `metrics`, `doctor [--fix]`, `session-start`.
- Quality gates: `pytest` (57), `ruff check .`, `python -m mypy` — all green.

## Constraints to keep in mind

- Only the Orchestrator grants/revokes ownership; loops use the broker (§6).
- Skill/tool content changes → new version; stat updates mutate in place
  (§3.3/§5.3). Promotion needs evidence + expected improvement + success metric
  (§4.4.4).
- Metrics must be derived from real recorded data (§8).

## Not now (deferred)

- Vector index, tool auto-promotion policy, multi-project isolation, desktop
  app IA (§11); multi-writer coordination.
