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
- **Status:** accepted
- **Context:** Spec §6 makes the Orchestrator the sole arbiter of task
  ownership. A durable registry is not yet required for a single-process MVP.
- **Decision:** Track ownership and heartbeats in-memory inside the
  Orchestrator. Loops request ownership via the `OwnershipBroker` protocol.
- **Consequences:** Ownership does not survive process restarts and is not yet
  multi-process safe. Persisting it (and stale-heartbeat reclamation) is
  backlog. See spec §7 (partial crashes).

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

---

## Open Questions (from spec §11 — unresolved)

- Exact ranking algorithm weights for context packing (initial values in DEC-005)
- Whether to introduce a vector index in Phase 2 or 3
- How aggressive automatic tool promotion should be
- Multi-project isolation strategy
- Desktop app information architecture