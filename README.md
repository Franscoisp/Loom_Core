# Loom Core

[![CI](https://github.com/Franscoisp/Loom_Core/actions/workflows/ci.yml/badge.svg)](https://github.com/Franscoisp/Loom_Core/actions/workflows/ci.yml)

A local-first, **memory-centric** runtime.

Loom Core maintains a durable, structured, outcome-aware record of what was
decided, what was tried, what worked and what failed, and how to repeat
success. Agents and loops are *clients* of this memory; the memory is the
center of the system.

## Status

Phase 0 (foundation) complete. Phase 1 (Memory MVP) is next — see `TASKS.md`.

## Layout

```
data/                 # Runtime memory (git-ignored; scaffold only committed)
  core/               # High-value invariants & decisions
  episodic/           # Session summaries & events
  procedural/         # Skills, anti-patterns, tools
  semantic/           # Entities & relations
src/loom_core/        # Python package (src layout)
tests/                # Test suite
docs/                 # Master specification
```

## Continuity files (authoritative — override chat history)

Read in this order at the start of every session:

1. `docs/LOOM_CORE_MASTER_SPEC.md`
2. `PROGRESS.md`
3. `TASKS.md`
4. `CURRENT_FOCUS.md`
5. `SESSION_LOG.md` (latest entries)
6. `DECISIONS.md` (if architecture questions arise)

## Development

```
pip install -e ".[dev]"
pytest
ruff check .
mypy
```

## Multiple projects

Isolation is one **data directory per project** (DEC-010). Point Loom at a
project's memory with either an environment variable or a flag:

```
$env:LOOM_DATA_DIR = "C:\path\to\projectA\data"   # PowerShell
loom memory list

loom metrics --data-dir C:\path\to\projectB\data   # per-command override
```

Concurrent processes sharing one data dir are safe: writes to the JSON state
files (ownership, metrics, tool registry) are guarded by an advisory file lock
(DEC-012).

## Continuous integration

`.github/workflows/ci.yml` runs the quality gates on every push and pull request
across a matrix of Ubuntu + Windows and Python 3.11 + 3.12:

- `ruff check .` (lint)
- `python -m mypy` (strict types)
- `pytest --cov=loom_core` (tests + coverage)
- a CLI smoke test (`loom version`)
