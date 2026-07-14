# COMPLETED.md

**Project:** Loom Core
Append-only log of completed work. One entry per finished task/batch.
Part of the continuity protocol (spec §5).

---

## 2026-07-14 — v2.0 specification

### Phase 0: Foundation
- Repository initialized with directory structure, `.gitignore`, Python project
  skeleton, continuity files (PROGRESS, TASKS, CURRENT_FOCUS, SESSION_LOG,
  DECISIONS), master spec. Git history: commit `263c006`.

### Phase 1: Memory MVP
- Pydantic v2 models for all memory entry types, strict validation, ISO-8601 Z
  datetimes.
- Atomic writer, reader, list/filter, keyword search.
- CLI: `loom memory write|list|show|search`.
- 22 tests. Commit: `0b959a7`.

### Phase 2: Loops & Orchestrator
- Loop interface (`Task`, `LoopResult`, `OwnershipBroker`), Orchestrator
  (ownership, dispatch, context), ContextPacker, Distillation Loop, Coding
  Support Loop, Meta/Self-Improvement Loop (detect/propose/evaluate + lifecycle
  + audit), Tool registry, shared skill-stat/versioning helpers.
- CLI: `loom pack`, `loom distill`, `loom meta detect|run`, `loom tools list`.
- 35 + 11 tests (46 total). Commits: `3b8ef88`, `47e9ad6`.

### Phase 3: Metrics, persistence, continuity
- Value metrics derived from real data, persistent counters, persistent
  ownership registry with TTL reclamation, continuity guard.
- CLI: `loom metrics`, `loom doctor [--fix]`, `loom session-start`.
- 57 tests. Commit: `e6c8f24`.

### Phase 4: Executable tools & enforcement
- `ToolExecutor` with candidate gating, built-in tools (frontmatter-linter,
  memory-summary), CLI `loom tools run|promote`, Coding Support CLI
  (`loom support`), dispatch audit log.
- 67 tests. Commit: `aa75032`.

### Phase 5: §11 open questions resolved
- Advisory file locking for concurrent writers, decisions for all §11 questions
  (DEC-008 through DEC-012). 72 tests. Commit: `8d301b3`.

### CI
- GitHub Actions workflow (ruff + mypy + pytest/coverage + CLI smoke) across
  Ubuntu/Windows × Python 3.11/3.12. Badge + branch protection on `main`.
  Commit: `b24ddfd`.

## 2026-07-14 — v3.0 harmonization

### Batch 1: New sacred file + CLI aliases + skills dir
- Created `COMPLETED.md` (new §5 sacred file).
- Added `skills/` directory at repo root (§16).
- Added `loom value` and `loom stats` CLI aliases (§15).

### Batch 3: TUI with Textual (§11)
- `src/loom_core/tui/app.py`: `LoomApp` (Textual framework), status bar
  (phase/model/claims/value), toggleable sidebar, 6 views: Chat, Memory
  (browse by layer), Skills (success rates), Progress (continuity files),
  Value (metrics), Loops (loop status). Slash commands: `/help`, `/quit`,
  `/refresh`.
- CLI: `loom tui`. `textual>=0.80` as `[tui]` extra.
- Quality gates: pytest 72, ruff clean, mypy strict clean.
