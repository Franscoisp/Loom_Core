# SESSION_LOG.md

**Project:** Loom Core
Chronological log of work sessions. Newest entries at the top.
A complete entry at the end of every session is mandatory (spec §10.5).
This file overrides chat history.

Session ID format: `YYYY-MM-DD-NN`.

---

## Session 2026-07-14-08 — CI + BOM fix

- **Session ID:** 2026-07-14-08
- **Date:** 2026-07-14
- **Focus:** Wire up GitHub Actions CI; fix a JSON-BOM robustness bug.

### What happened
- Live terminal walkthrough of the full system (memory → pack → distill →
  meta/tool lifecycle → metrics → doctor). It surfaced a bug: PowerShell's
  `Set-Content -Encoding utf8` writes a UTF-8 BOM that `json.loads` rejected.
- Fixed: added `cli._load_json` (reads `utf-8-sig`, validates object shape) and
  routed `distill`, `meta run`, `support`, and `tools run` payload reads through
  it (commit ab12021).
- Added `.github/workflows/ci.yml` (TASK-055, DEC-013): ruff + mypy + pytest
  (coverage) + CLI smoke test, matrix Ubuntu/Windows × Python 3.11/3.12, on push
  and PR. Validated the YAML and confirmed coverage locally (~87%).
- README: added CI badge placeholder + a "Continuous integration" section.

### Outcome
- **Status:** success. Quality gates: pytest 72 passed, ruff clean, mypy strict
  clean; local coverage ~87%.

### Notes
- README badge needs the real `OWNER/REPO` once a git remote is created.

### Next session
- Optional: push to a remote and confirm the CI run goes green; add venv
  quickstart if desired.

---

## Session 2026-07-14-07 — Phase 5: resolve §11 open questions

- **Session ID:** 2026-07-14-07
- **Date:** 2026-07-14
- **Focus:** Walk through and resolve all §11 open questions.

### What happened
- Reviewed the five §11 open questions with the user and recorded decisions:
  - DEC-008: keep keyword retrieval (no vector index).
  - DEC-009: tool promotion manual / evidence-gated (no auto-promotion).
  - DEC-010: one data directory per project (documented in README).
  - DEC-011: CLI + files are the interface; desktop GUI deferred.
  - DEC-012: add advisory file locking for concurrent writers.
- Implemented DEC-012: `locking.py` with a dependency-free, cross-platform
  `FileLock` (atomic `O_CREAT|O_EXCL` lock file, polling, stale-lock breaking).
  Wired it into the read-modify-write critical sections of `ownership.py`,
  `metrics.py`, and `registry.py`.
- Fixed `FileLock.acquire` to create the lock file's parent dir first.
- README: documented per-project data dirs and concurrency safety.
- `tests/`: +6 tests (`test_locking.py`) including a 5-thread × 20 concurrent
  increment test that asserts no lost updates (final count == 100). 72 total.

### Outcome
- **Status:** success — all §11 open questions resolved.
- Quality gates: pytest 72 passed, ruff clean, mypy --strict clean.

### Lessons / notes
- Locking must ensure the parent directory exists before creating the lock file
  (the JSON stores may not have been written yet).

### Project state
- Loom Core is feature-complete against the Expanded Master Specification v2.0.
  Spec §2–§10 implemented and tested; §11 open questions all resolved.

### Next session
- None outstanding. New work would be net-new features beyond the spec.

---

## Session 2026-07-14-06 — Phase 4: Executable tools & enforcement

- **Session ID:** 2026-07-14-06
- **Date:** 2026-07-14
- **Focus:** Executable tools (§4.4.6), Coding Support CLI, dispatch audit log,
  and recording §11 deferrals. Closes out all spec-required work.

### What happened
- `tooling.py` (TASK-040): `ToolExecutor` binds Python callables to registered
  tools, gates execution by lifecycle status (candidate tools require
  `allow_candidate`; only `promoted` run freely — spec §4.4.6), records an
  outcome entry and updates tool stats on every run. Built-ins:
  `frontmatter-linter`, `memory-summary`.
- `cli.py` (TASK-041, TASK-043): `loom support` (Coding Support Loop),
  `loom tools run`, `loom tools promote`.
- `orchestrator.py` (TASK-042): appends every dispatch to
  `data/dispatch_log.jsonl` (loop, task, status, whether memory was written) so
  gaps are auditable rather than silent (spec §6 step 8, §7).
- `tests/`: +10 tests (tooling, dispatch log); 67 total (TASK-044).
- Verified via CLI: candidate tool blocked → allowed with flag → promoted →
  runs freely.

### Decisions
- DEC-007: safe-by-default tool execution gating; explicitly **deferred** the
  §11 open questions (vector index, auto-promotion aggressiveness, multi-project
  isolation, desktop app IA, multi-writer locking).

### Outcome
- **Status:** success — Phase 4 COMPLETE. All binding spec sections (§2–§10)
  implemented and tested.
- Quality gates: pytest 67 passed, ruff clean, mypy --strict clean.

### Lessons / notes
- Gating tool execution at the executor (not just the registry) keeps the
  dangerous capability (spec §4.4.6) behind an explicit switch.
- The dispatch log gives cheap, durable auditability without a background loop.

### Project state
- Loom Core is feature-complete against the Expanded Master Specification v2.0.
  Remaining work is §11 open questions only (deferred, DEC-007).

### Next session
- None required. Revisit §11 items on real demand.

---

## Session 2026-07-14-05 — Phase 3: Metrics, persistence, continuity

- **Session ID:** 2026-07-14-05
- **Date:** 2026-07-14
- **Focus:** Value metrics (§8), persistent ownership (§7), continuity guard (§7).

### What happened
- `metrics.py` (TASK-030): `compute_metrics` derives the §8 metrics from memory
  (decisions preserved, skills created/promoted/improved, average success rate)
  and merges persistent cumulative counters (`MetricsStore` → `data/metrics.json`:
  distillation_runs, recovery_events, ownership_conflicts, tokens_saved).
- `ownership.py` (TASK-031): `OwnershipRegistry` persists `data/ownership.json`
  with atomic writes; reclaims a task once the owner's heartbeat exceeds a TTL
  (default 3600s) — handles partial crashes (§7). Supersedes DEC-004 via DEC-006.
- `orchestrator.py` (TASK-032): now uses the persistent registry and updates
  metrics as a side effect of dispatch (ownership_conflicts on denied grants,
  distillation_runs, tokens_saved_cumulative), plus `record_recovery` and
  `metrics_snapshot`.
- `continuity.py` (TASK-033): `ContinuityGuard` checks the sacred files exist and
  can recreate missing ones from a clearly-marked stub (§7).
- `cli.py` (TASK-034): `loom metrics`, `loom doctor [--fix]`, `loom session-start`.
- `tests/`: +11 tests (metrics, ownership, continuity); 57 total (TASK-035).
- Verified via CLI: doctor OK, session-start recorded a recovery event, metrics
  reflected real data.

### Decisions
- DEC-006 (persist ownership + metrics as JSON under data/); DEC-004 superseded.

### Outcome
- **Status:** success — Phase 3 COMPLETE (TASK-030 → TASK-035).
- Quality gates: pytest 57 passed, ruff clean, mypy --strict clean.

### Lessons / notes
- Metrics split cleanly into memory-derived (recomputed) vs event counters
  (persisted), matching the §8 requirement to derive from real data.
- Heartbeat TTL reclamation keeps ownership honest without a background process.

### Next session
- Backlog only: executable tools behind candidates (§4.4.6), retrieval upgrade
  (§11), loop-driven continuity auto-writes (§6 step 8).

---

## Session 2026-07-14-04 — Phase 2: Coding Support + Meta loops (complete)

- **Session ID:** 2026-07-14-04
- **Date:** 2026-07-14
- **Focus:** Finish Phase 2 — Coding Support Loop, Meta Loop, tool registry.

### What happened
- Refactored shared skill/tool logic into `MemoryStore`: `versions`,
  `latest_version`, `next_version_number`, `update_stats` (stat updates mutate
  in place; only content changes create a new version). Distillation now uses it.
- `loops/coding_support.py` (§4.3, TASK-026): actions `context` (requests a pack
  via the Orchestrator through the new `ContextProvider` protocol — never
  assembles packs itself), `surface_skills` (search skills/tools), and
  `record_outcome` (write an outcome entry + update skill stats). Never owns
  code-writing.
- `loops/meta.py` (§4.4, TASK-027): `detect` (underperforming skills + failure
  clusters → proposals), `propose` (new_skill / skill_improvement /
  new_tool / anti_pattern as drafts; new_tool also registers a candidate and a
  companion usage skill per §4.4.6), `evaluate` (promote/reject/deprecate;
  promotion blocked unless evidence + expected_improvement + success_metric are
  supplied per §4.4.4). Every transition writes an audit episode.
- `registry.py` (§5.4, TASK-028): JSON `ToolRegistry` with atomic writes.
- `cli.py`: `loom meta detect`, `loom meta run <json>`, `loom tools list`.
- `tests/`: +11 tests (coding support, meta); 46 total.
- Verified end-to-end via CLI: proposed a candidate tool (registered) + skill.

### Outcome
- **Status:** success — Phase 2 COMPLETE (TASK-020 → TASK-028).
- Quality gates: pytest 46 passed, ruff clean, mypy --strict clean.

### Lessons / notes
- The `ContextProvider` protocol lets loops depend on the Orchestrator's context
  assembly without a circular import.
- Meta promotion gating (evidence/expected_improvement/success_metric) keeps the
  learning engine honest and reversible (spec §4.4.4).

### Next session
- Phase 3: value metrics (§8), loop-driven continuity enforcement (§6/§7), and
  persisting ownership/heartbeats (DEC-004).

---

## Session 2026-07-14-03 — Phase 2: Loops & Orchestrator (partial)

- **Session ID:** 2026-07-14-03
- **Date:** 2026-07-14
- **Focus:** Loop framework, Orchestrator, Context Packer, Distillation Loop.

### What happened
- `loops/base.py`: `Task`, `LoopResult` (validated status), `OwnershipBroker`
  protocol, and the abstract `Loop` (name/can_handle/run/claim/release/
  heartbeat) per spec §4.1 (TASK-020).
- `orchestrator.py`: `Orchestrator` — sole arbiter of ownership (grant/revoke),
  loop registration/binding, `dispatch` (claim→heartbeat→run→release), and
  `context_pack` delegation (spec §6) (TASK-021).
- `context.py`: `ContextPacker` — additive ranking (tag/project/layer/success_
  rate/recency/confidence), strict token budget, `tokens_saved_estimate`, and
  per-item rationale (spec §3.5) (TASK-022). Weights recorded as DEC-005.
- `loops/distillation.py`: `DistillationLoop` — writes validated candidate
  entries, updates skill/tool success/failure stats on the latest version,
  records a distillation episode (spec §4.2) (TASK-023).
- `cli.py`: added `loom pack` and `loom distill` (TASK-024).
- `tests/`: +13 tests (orchestrator, context, distillation); 35 total (TASK-025).
- Verified end-to-end via CLI: distilled a Phase 2 session and packed context.

### Decisions
- DEC-003 (paths for preference/outcome/tool), DEC-004 (in-memory ownership),
  DEC-005 (initial context ranking weights).

### Outcome
- **Status:** success (Phase 2 partial)
- TASK-020 → TASK-025 complete. Coding Support (§4.3) and Meta (§4.4) loops remain.
- Quality gates: pytest 35 passed, ruff clean, mypy --strict clean.

### Lessons / notes
- `LoopResult.status` is validated in `__post_init__` to catch typos early.
- Skill stat updates mutate counts in place (not a new version); only content
  changes create a new version (spec §3.3/§5.3). `store.write` re-validates,
  keeping `success_rate` consistent.

### Next session
- Implement the Coding Support Loop (§4.3), then the Meta/Self-Improvement Loop
  (§4.4) with the skill/tool lifecycle state machine.

---

## Session 2026-07-14-02 — Phase 1: Memory MVP

- **Session ID:** 2026-07-14-02
- **Date:** 2026-07-14
- **Focus:** Implement the Memory MVP (TASK-010 → TASK-017).

### What happened
- `src/loom_core/models.py`: Pydantic v2 models for every entry type (core,
  preference, outcome, anti-pattern, entity, relation, episode, skill, tool).
  Strict (`extra="forbid"`), timezone-aware datetimes serialized to ISO-8601 Z,
  filename-safe id validation, `success_rate` auto-recomputed from counts,
  `parse_entry()` discriminated validation (TASK-010, TASK-015).
- `src/loom_core/paths.py`: data-dir resolution (arg > `LOOM_DATA_DIR` > `./data`)
  and strict per-type file naming (spec §3.4).
- `src/loom_core/store.py`: `MemoryStore` with atomic write (temp file +
  `os.replace` + fsync), reader, list/filter, ranked keyword search
  (TASK-011/012/013).
- `src/loom_core/cli.py`: `loom memory write|list|show|search` using Typer
  `Annotated` options (TASK-014).
- `tests/`: 22 tests (models, store, CLI) all using temp dirs (TASK-016).
- Added `types-PyYAML` dev dep for mypy.
- Recorded first real memory entries in `data/` via the CLI (TASK-017):
  `memory-is-the-center` (core), `run-quality-gates` (skill),
  `phase-1-memory-mvp` (episode).
- Swapped skill/tool mixin inheritance so `id`/`title` lead the frontmatter.

### Outcome
- **Status:** success
- Phase 1 tasks TASK-010 through TASK-017 complete.
- Quality gates: pytest 22 passed, ruff clean, mypy --strict clean.

### Lessons / notes
- Typer options need `Annotated[...]` to avoid ruff B008.
- With `use_enum_values=True`, `entry.type` becomes a plain string after
  validation; path logic handles both enum and string forms.
- Pydantic field order follows reverse MRO; `(_StatsMixin, BaseEntry)` puts base
  fields first for human-readable frontmatter.

### Next session
- Begin Phase 2: common Loop interface + `LoopResult` (§4.1), then the
  Distillation Loop (§4.2).

---

## Session 2026-07-14-01 — Phase 0: Foundation

- **Session ID:** 2026-07-14-01
- **Date:** 2026-07-14
- **Focus:** Bootstrap the repository and continuity system (Phase 0).

### What happened
- Reviewed the Expanded Master Specification v2.0.
- Confirmed empty working directory; chose "Phase 0 + git init".
- Created the exact directory structure: `data/{core,episodic,procedural/{skills,anti-patterns,tools},semantic/{entities,relations}}`, `src/loom_core/`, `tests/`, `docs/`.
- Added `.gitkeep` files to preserve empty `data/` subdirectories.
- Wrote `.gitignore` protecting `data/` contents and secrets (see DEC-001).
- Set up Python project: `pyproject.toml` (hatchling, src layout, pytest, ruff, mypy), `src/loom_core/__init__.py`, `src/loom_core/cli.py` skeleton with `loom` entry point, `tests/test_smoke.py` (see DEC-002).
- Placed the spec at `docs/LOOM_CORE_MASTER_SPEC.md`.
- Created continuity files: `PROGRESS.md`, `TASKS.md`, `CURRENT_FOCUS.md`, `DECISIONS.md`, this `SESSION_LOG.md`, and `README.md`.
- Recorded DEC-001 (data/ ignore strategy) and DEC-002 (packaging choices).
- Initialized git repository and made the initial commit.

### Outcome
- **Status:** success
- Phase 0 tasks TASK-001 through TASK-007 complete.

### Lessons / notes
- `data/` runtime memory is git-ignored by default; revisit if dev-process
  memory entries (TASK-017) should be committed.

### Next session
- Begin Phase 1 (Memory MVP), starting with TASK-010: Pydantic models for all
  memory entry types (schema §3.3).
