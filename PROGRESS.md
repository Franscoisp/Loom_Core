# PROGRESS.md

**Project:** Loom Core
**Purpose:** Authoritative high-level record of what is done, in progress, and next.
This file overrides chat history. Update after every meaningful change.

---

## Current Phase

**Phase 0 – Foundation** ✅ COMPLETE
**Phase 1 – Memory MVP** ✅ COMPLETE
**Phase 2 – Loops & Orchestrator** ✅ COMPLETE
**Phase 3 – Value metrics, continuity enforcement, persistence** ⏳ NOT STARTED (next)

---

## Completed

### Phase 0 – Foundation (2026-07-14)
- [x] TASK-001: Exact directory structure created (`data/`, `src/`, `tests/`, `docs/`)
- [x] TASK-002: Continuity files created with headers/templates
- [x] TASK-003: Initial `PROGRESS.md`, `TASKS.md`, `CURRENT_FOCUS.md`, `DECISIONS.md`
- [x] TASK-004: Master specification placed at `docs/LOOM_CORE_MASTER_SPEC.md`
- [x] TASK-005: Python project setup (`pyproject.toml`, src layout, test skeleton)
- [x] TASK-006: `.gitignore` protecting `data/` contents and secrets
- [x] TASK-007: First `SESSION_LOG.md` entry recorded
- [x] git repository initialized with initial commit

### Phase 1 – Memory MVP (2026-07-14)
- [x] TASK-010: Pydantic v2 models for all entry types (`src/loom_core/models.py`)
- [x] TASK-011: Atomic memory writer + strict file naming (`store.py`, `paths.py`)
- [x] TASK-012: Reader + list/filter (`store.py`)
- [x] TASK-013: Keyword search (`store.py`)
- [x] TASK-014: CLI `loom memory write|list|show|search` (`cli.py`)
- [x] TASK-015: Strict validation (`extra="forbid"`, range/enum/type checks)
- [x] TASK-016: 22 unit/integration tests using temp dirs
- [x] TASK-017: First real memory entries recorded in `data/`

**Quality gates:** pytest (22 passed), ruff (clean), mypy --strict (clean).

### Phase 2 – Loops & Orchestrator (2026-07-14, in progress)
- [x] TASK-020: Loop interface + `Task` + `LoopResult` + `OwnershipBroker` (`loops/base.py`)
- [x] TASK-021: `Orchestrator` — ownership grant/revoke, dispatch, context assembly (`orchestrator.py`)
- [x] TASK-022: `ContextPacker` — ranking + strict token budget + savings metric (`context.py`)
- [x] TASK-023: `DistillationLoop` — candidates → memory, skill-stat updates, episode (`loops/distillation.py`)
- [x] TASK-024: CLI `loom pack`, `loom distill`
- [x] TASK-025: 13 new tests (orchestrator, context, distillation)
- [x] TASK-026: Coding Support Loop — context/surface_skills/record_outcome (`loops/coding_support.py`, §4.3)
- [x] TASK-027: Meta/Self-Improvement Loop — detect/propose/evaluate + lifecycle + audit (`loops/meta.py`, §4.4)
- [x] TASK-028: Tool registry & discovery (`registry.py`, §5.4); CLI `loom meta ...`, `loom tools list`
- [x] Refactor: shared skill-stat/versioning helpers moved to `MemoryStore`

**Quality gates (Phase 2):** pytest (46 passed), ruff (clean), mypy --strict (clean).

---

## In Progress

_None._

---

## Next Up

- Phase 3: value metrics derivation (§8), loop-driven continuity-file
  enforcement (§6 step 8, §7), and persisting ownership/heartbeats (DEC-004).

---

## Notes

- The Memory System, Distillation Loop, Meta/Self-Improvement Loop, and the
  Skill/Tool creation system are the differentiators. Implement with the care
  described in the spec. No shortcuts that lose outcome data or skip versioning.
