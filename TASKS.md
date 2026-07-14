# TASKS.md

**Project:** Loom Core
Task backlog. Statuses: `TODO` | `DOING` | `DONE` | `BLOCKED`.
This file overrides chat history.

---

## Phase 0 – Foundation

| ID       | Status | Description |
|----------|--------|-------------|
| TASK-001 | DONE   | Create exact directory structure |
| TASK-002 | DONE   | Create all continuity files with headers/templates |
| TASK-003 | DONE   | Write initial PROGRESS.md, TASKS.md, etc. |
| TASK-004 | DONE   | Place specification file in docs/ |
| TASK-005 | DONE   | Basic Python project setup (pyproject.toml, src layout, testing skeleton) |
| TASK-006 | DONE   | .gitignore that protects data/ and secrets |
| TASK-007 | DONE   | First SESSION_LOG entry recording Phase 0 completion |

---

## Phase 1 – Memory MVP

| ID       | Status | Description |
|----------|--------|-------------|
| TASK-010 | TODO   | Define Pydantic models for all memory entry types (schema §3.3) |
| TASK-011 | TODO   | Implement atomic memory writer |
| TASK-012 | TODO   | Implement memory reader and basic list/filter |
| TASK-013 | TODO   | Implement simple keyword search |
| TASK-014 | TODO   | CLI commands for memory write / list / show |
| TASK-015 | TODO   | Validation that rejects malformed entries |
| TASK-016 | TODO   | Unit + integration tests using temporary directories |
| TASK-017 | TODO   | Record first real memory entries from the development process itself |

---

## Backlog / Later Phases

- Distillation Loop (spec §4.2)
- Coding Support Loop (spec §4.3)
- Meta / Self-Improvement Loop (spec §4.4)
- Orchestrator + Context Packer (spec §6, §3.5)
- Tool registry & discovery (spec §5.4)
- Value metrics derivation (spec §8)
