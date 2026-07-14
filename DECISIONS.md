# DECISIONS.md

**Project:** Loom Core
Architecture Decision Records (ADRs). Append-only. This file overrides chat history.
When resolving an Open Question (spec §11), record it here.

Template:
```
## DEC-NNN: <title>
- **Date:** YYYY-MM-DD
- **Status:** proposed | accepted | superseded
- **Context:** why the decision was needed
- **Decision:** what was decided
- **Consequences:** trade-offs / follow-ups
```

---

## DEC-001: git-ignore data/ contents but commit the directory scaffold
- **Date:** 2026-07-14
- **Status:** accepted
- **Context:** Spec §9 TASK-006 requires `.gitignore` that protects `data/` and
  secrets. `data/` holds runtime memory that may be sensitive and is
  machine-generated, but the empty directory structure must still exist on a
  fresh checkout.
- **Decision:** Ignore all `data/**` contents but preserve directories via
  committed `.gitkeep` files (negation patterns in `.gitignore`).
- **Consequences:** Memory entries created during development are NOT committed
  by default. If specific memory entries should be version-controlled later
  (e.g. TASK-017 dev-process entries), revisit with an explicit allowlist.

## DEC-002: Python packaging = hatchling + src layout, Python 3.11+
- **Date:** 2026-07-14
- **Status:** accepted
- **Context:** Spec §9 TASK-005 requires a basic Python project with src layout
  and a testing skeleton.
- **Decision:** Use hatchling build backend, `src/loom_core/` package layout,
  pytest for tests, ruff + mypy (strict) for quality. Runtime deps: pydantic v2,
  pyyaml, python-frontmatter, typer. `loom` console entry point.
- **Consequences:** Contributors run `pip install -e ".[dev]"`. Pydantic v2 is
  the basis for the memory models.

## DEC-003: File-path mapping for entry types not enumerated in §3.4
- **Date:** 2026-07-14
- **Status:** accepted
- **Context:** Spec §3.4 gives naming rules for core, episodic, skills,
  anti-patterns, entities and relations, but the schema (§3.3) also defines the
  types `preference`, `outcome` and `tool`.
- **Decision:** `preference` → `data/core/` (date-slug naming);
  `outcome` → `data/episodic/` (timestamp naming);
  `tool` → `data/procedural/tools/` (versioned `name-vN.md`, like skills).
- **Consequences:** All nine types have a deterministic home. Revisit if a
  dedicated preferences/outcomes layer is introduced later.

## DEC-004: Ownership + heartbeats are in-memory for now
- **Date:** 2026-07-14
- **Status:** superseded by DEC-006
- **Context:** Spec §6 makes the Orchestrator the sole arbiter of task
  ownership. A durable registry is not yet required for a single-process MVP.
- **Decision:** Track ownership and heartbeats in-memory inside the
  Orchestrator. Loops request ownership via the `OwnershipBroker` protocol.
- **Consequences:** Ownership did not survive process restarts. Superseded once
  Phase 3 added persistence.

## DEC-005: Context ranking weights (initial, tunable)
- **Date:** 2026-07-14
- **Status:** accepted
- **Context:** Spec §3.5 lists ranking signals in priority order but leaves the
  exact weights open (§11).
- **Decision:** Initial additive weights: tag match +10/tag, project match +8,
  core/preference +4 (+2 if active/promoted), skill/tool +5×success_rate
  (+1 if active/promoted), recency +3×(1/(1+age_days)), confidence +2×confidence.
  Token estimate ≈ len/4; budget filled greedily by descending score.
- **Consequences:** Simple, deterministic, testable. Weights are expected to be
  tuned once real usage data exists; this remains an open question in §11.

## DEC-006: Persist ownership + metrics as JSON under data/
- **Date:** 2026-07-14
- **Status:** accepted (supersedes DEC-004)
- **Context:** Spec §7 requires surviving partial crashes/restarts; §8 requires
  value metrics derived from real recorded data.
- **Decision:** `OwnershipRegistry` persists `data/ownership.json` (per-task
  owner + heartbeat) with atomic writes and reclaims a task once the owner's
  heartbeat exceeds a TTL (default 3600s). `MetricsStore` persists cumulative
  event counters in `data/metrics.json`; the rest of the §8 metrics are computed
  from memory on demand by `compute_metrics`.
- **Consequences:** Ownership and counters survive restarts. Both JSON files are
  git-ignored like the rest of `data/`. Still single-node (no locking); multi
  writer coordination remains future work.

## DEC-007: Tool execution gating + deferral of §11 open questions
- **Date:** 2026-07-14
- **Status:** accepted
- **Context:** Spec §4.4.6 warns tool creation is powerful/dangerous; §11 lists
  open questions intentionally left for later.
- **Decision:**
  - Executable tools (`tooling.ToolExecutor`) run only when `promoted`, or when
    a caller explicitly passes `allow_candidate` / `--allow-candidate`. Every run
    records an outcome entry and updates the tool's stats. Promotion is a manual
    action (`loom tools promote`) or a Meta evaluation with evidence.
  - Automatic (unattended) tool promotion stays **disabled** for now — the "how
    aggressive" question (§11) is deferred; humans/Meta-with-evidence promote.
  - **Deferred (not implemented this cycle):** vector index (keyword search is
    sufficient at current scale), multi-project isolation (single project per
    data dir for now), desktop app information architecture, and multi-writer
    locking. Revisit when there is real demand/scale.
- **Consequences:** Safe-by-default tool execution. The deferred items remain
  open questions in §11; no code assumes them.

## DEC-008: Retrieval stays keyword-based for now
- **Date:** 2026-07-14
- **Status:** accepted (resolves §11 "vector index")
- **Context:** §11 asks whether to add a vector index.
- **Decision:** Keep the deterministic keyword ranking in `ContextPacker` /
  `MemoryStore.search`. No embeddings/vector dependency yet.
- **Consequences:** Zero extra deps, fully local and testable. Revisit if recall
  degrades at larger scale; the packer's scoring is already pluggable.

## DEC-009: Tool promotion is manual / evidence-gated (no auto-promotion)
- **Date:** 2026-07-14
- **Status:** accepted (resolves §11 "auto-promotion aggressiveness")
- **Context:** §11 asks how aggressive automatic tool promotion should be.
- **Decision:** No unattended promotion. Tools are promoted only by an explicit
  human action (`loom tools promote`) or a Meta evaluation that supplies
  evidence + expected improvement + success metric (§4.4.4). Confirms DEC-007.
- **Consequences:** Powerful/dangerous capability stays behind an explicit gate.

## DEC-010: One data directory per project
- **Date:** 2026-07-14
- **Status:** accepted (resolves §11 "multi-project isolation")
- **Context:** §11 asks for a multi-project isolation strategy.
- **Decision:** Isolation is achieved by pointing Loom at a separate data dir per
  project via `LOOM_DATA_DIR` or `--data-dir`. No shared-store namespacing.
- **Consequences:** Simple, strong isolation with no cross-project leakage. A
  shared multi-tenant store can be layered later if needed.

## DEC-011: CLI + files are the interface; desktop GUI deferred
- **Date:** 2026-07-14
- **Status:** accepted (resolves §11 "desktop app IA")
- **Context:** §11 lists desktop app information architecture as open.
- **Decision:** The CLI and human-readable files are the interface. No GUI is
  built now; revisit only if a desktop app is actually pursued.
- **Consequences:** Focus stays on the memory-centric core.

## DEC-012: Advisory file locking for concurrent writers
- **Date:** 2026-07-14
- **Status:** accepted (resolves §11 "multi-writer coordination")
- **Context:** JSON state files (ownership, metrics, tool registry) are
  read-modify-written and could lose updates across processes.
- **Decision:** Add a dependency-free, cross-platform `FileLock` (atomic
  `O_CREAT|O_EXCL` lock file, polling, stale-lock breaking) and wrap the
  read-modify-write critical sections in `ownership`, `metrics`, and `registry`.
- **Consequences:** Concurrent single-node processes no longer clobber each
  other. Not a distributed lock; true multi-node coordination (DB/queue) remains
  out of scope.

---

## Resolved (formerly Open Questions from spec §11)

- Ranking weights for context packing — DEC-005 (initial, tunable)
- Vector index — DEC-008 (keep keyword)
- Automatic tool promotion aggressiveness — DEC-009 (manual/evidence-gated)
- Multi-project isolation — DEC-010 (one data dir per project)
- Desktop app information architecture — DEC-011 (deferred; CLI is the interface)
- Multi-writer coordination — DEC-012 (advisory file locking)