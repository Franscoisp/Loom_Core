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
  the basis for the memory models in TASK-010.

---

## Open Questions (from spec §11 — unresolved)

- Exact ranking algorithm weights for context packing
- Whether to introduce a vector index in Phase 2 or 3
- How aggressive automatic tool promotion should be
- Multi-project isolation strategy
- Desktop app information architecture
