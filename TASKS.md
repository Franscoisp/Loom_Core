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
| TASK-010 | DONE   | Define Pydantic models for all memory entry types (schema §3.3) |
| TASK-011 | DONE   | Implement atomic memory writer |
| TASK-012 | DONE   | Implement memory reader and basic list/filter |
| TASK-013 | DONE   | Implement simple keyword search |
| TASK-014 | DONE   | CLI commands for memory write / list / show (+ search) |
| TASK-015 | DONE   | Validation that rejects malformed entries |
| TASK-016 | DONE   | Unit + integration tests using temporary directories |
| TASK-017 | DONE   | Record first real memory entries from the development process itself |

---

## Phase 2 – Loops & Orchestrator

| ID       | Status | Description |
|----------|--------|-------------|
| TASK-020 | DONE   | Loop interface, Task, LoopResult, OwnershipBroker (§4.1) |
| TASK-021 | DONE   | Orchestrator with task ownership grant/revoke + dispatch (§6) |
| TASK-022 | DONE   | Context Packer with ranking + strict token budget (§3.5) |
| TASK-023 | DONE   | Distillation Loop (§4.2) |
| TASK-024 | DONE   | CLI commands: `loom pack`, `loom distill` |
| TASK-025 | DONE   | Tests for loops / orchestrator / context / distillation |
| TASK-026 | DONE   | Coding Support Loop (§4.3) — context / surface_skills / record_outcome |
| TASK-027 | DONE   | Meta / Self-Improvement Loop (§4.4) — detect / propose / evaluate + lifecycle |
| TASK-028 | DONE   | Tool registry & discovery (§5.4); CLI `loom meta`, `loom tools` |

---

## Phase 3 – Metrics, Persistence & Continuity

| ID       | Status | Description |
|----------|--------|-------------|
| TASK-030 | DONE   | Value metrics derived from real data + persistent counters (§8) |
| TASK-031 | DONE   | Persistent ownership registry + stale-heartbeat reclamation (§7) |
| TASK-032 | DONE   | Orchestrator metric wiring (conflicts, distillation_runs, tokens_saved, recovery) |
| TASK-033 | DONE   | Continuity guard: sacred-file check + stub recovery (§7) |
| TASK-034 | DONE   | CLI `loom metrics`, `loom doctor [--fix]`, `loom session-start` |
| TASK-035 | DONE   | Tests for metrics / ownership / continuity |

---

## Phase 4 – Executable Tools & Enforcement

| ID       | Status | Description |
|----------|--------|-------------|
| TASK-040 | DONE   | Executable tool framework + built-in tools + candidate gating (§4.4.6) |
| TASK-041 | DONE   | Coding Support CLI (`loom support`) |
| TASK-042 | DONE   | Dispatch audit log in Orchestrator (§6 step 8) |
| TASK-043 | DONE   | CLI `loom tools run`, `loom tools promote` |
| TASK-044 | DONE   | Tests for tooling + dispatch log |

---

## Backlog / Later Phases (all §11 open questions — deferred, see DEC-007)

- Vector index for retrieval (keyword search sufficient at current scale)
- Automatic/unattended tool promotion policy
- Multi-project isolation strategy
- Desktop app information architecture
- Multi-writer / multi-process coordination (locking)
