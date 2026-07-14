# CURRENT_FOCUS.md

**Project:** Loom Core
The single most important thing right now. This file overrides chat history.

---

## Focus

**Phases 0–4 are complete.** Every binding spec section (§2–§10) is implemented
and tested. Loom Core has: the full memory system, all loop roles, the
Orchestrator (ownership + dispatch + audit log), context packing, the tool
registry with **executable, gated tools**, value metrics, persistent ownership,
and continuity enforcement.

There is no spec-required work outstanding. All remaining items are §11 open
questions, explicitly deferred in DEC-007. Pick any up only on real demand:
- Vector index / retrieval upgrade.
- Automatic tool promotion policy.
- Multi-project isolation; desktop app IA; multi-writer locking.

## Full module map

- `models`, `paths`, `store` — memory core (+ skill-stat/versioning helpers).
- `loops/base`, `loops/distillation` (§4.2), `loops/coding_support` (§4.3),
  `loops/meta` (§4.4).
- `orchestrator` (ownership + dispatch + metrics + audit log), `context`
  (ranked packing + `ContextProvider`), `registry` (§5.4),
  `tooling` (executable tools §4.4.6), `ownership` (persistent, §7),
  `metrics` (§8), `continuity` (§7).
- CLI: `memory ...`, `pack`, `distill`, `support`, `meta detect|run`,
  `tools list|run|promote`, `metrics`, `doctor [--fix]`, `session-start`,
  `version`.
- Quality gates: `pytest` (67), `ruff check .`, `python -m mypy` — all green.

## Constraints to keep in mind

- Only the Orchestrator grants/revokes ownership; loops use the broker (§6).
- Skill/tool content changes → new version; stat updates mutate in place
  (§3.3/§5.3). Promotion needs evidence (§4.4.4). Candidate tools are gated
  (§4.4.6).
- Metrics must be derived from real recorded data (§8).
