# CURRENT_FOCUS.md

**Project:** Loom Core
The single most important thing right now. This file overrides chat history.

---

## Focus

**Loom Core is feature-complete.** Every binding spec section (§2–§10) is
implemented and tested, and all §11 open questions are now resolved
(DEC-005, DEC-008..012). There is no outstanding work.

If new work arrives it would be net-new feature requests beyond the current
spec (e.g., a GUI, embeddings-based retrieval, distributed coordination) — each
should get its own DECISIONS.md entry first.

## Full module map

- `models`, `paths`, `store` — memory core (+ skill-stat/versioning helpers).
- `loops/base`, `loops/distillation` (§4.2), `loops/coding_support` (§4.3),
  `loops/meta` (§4.4).
- `orchestrator` (ownership + dispatch + metrics + audit log), `context`
  (ranked packing + `ContextProvider`), `registry` (§5.4),
  `tooling` (executable tools §4.4.6), `ownership` (persistent, §7),
  `metrics` (§8), `continuity` (§7), `locking` (advisory FileLock, DEC-012).
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
