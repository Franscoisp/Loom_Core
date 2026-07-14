# Loom Core
## Expanded Master Specification & Operating Manual
### Version 2.0 – Zero-Gap Edition for OpenCode + DeepSeek V4 Pro

**Document Status:** Authoritative & Binding  
**Created:** 2026-07-14  
**Focus of this version:** Extreme detail on Memory System, Loops, Self-Improvement, Learning, Tool/Skill Creation & Improvement  
**Priority Rule:** This document + the Continuity Tracking files override chat history.

---

# 1. Document Purpose & Reading Rules for the Coding Agent

This document exists so that OpenCode + DeepSeek V4 Pro can build Loom Core across many sessions without ambiguity or loss of intent.

**Mandatory reading order at the start of every session:**
1. This file (at least the sections relevant to current work)
2. `PROGRESS.md`
3. `TASKS.md`
4. `CURRENT_FOCUS.md`
5. Latest entries in `SESSION_LOG.md`
6. `DECISIONS.md` (if architecture questions arise)

If any ambiguity exists between chat history and this document, **this document wins**.

---

# 2. Vision & Core Definition (Unchanged but Restated for Clarity)

Loom Core is a **local-first memory-centric runtime**.

Its primary job is to maintain a durable, structured, outcome-aware record of:
- What was decided
- What was tried
- What worked and what failed
- How to repeat success (skills/tools)
- The evolving state of projects

Agents and loops are clients of this memory. The memory is not a plugin; it is the center.

---

# 3. Expanded Loom Memory System Specification

This is the heart of Loom Core. Misunderstanding this section will break the entire system.

## 3.1 Design Goals of the Memory System

1. Survive context-window compaction and session resets.
2. Be fully human-inspectable (plain files first).
3. Support high-quality selective retrieval (so context packs stay small and relevant).
4. Record outcomes so the system can learn what works.
5. Allow both humans and loops to write to it safely.
6. Make conflict and staleness visible rather than silent.

## 3.2 Memory Layers – Precise Definitions

### 3.2.1 Core Layer
**Purpose:** Information that should be considered in almost every relevant context pack.

**Contents:**
- Project invariants and architectural decisions that are still active
- User preferences that affect behavior
- High-confidence facts that rarely change
- Critical constraints

**Rules:**
- Must be curated. Distillation Loop may propose additions, but Core should not grow unbounded.
- Every Core entry should answer: “Would it be expensive to forget this?”
- Prefer fewer, higher-quality entries.

**Location:** `data/core/`

### 3.2.2 Episodic Layer
**Purpose:** Record of what happened.

**Contents:**
- Session summaries
- Significant events
- Timelines of work
- Raw-ish logs that have been lightly cleaned

**Rules:**
- Append-mostly.
- Used for recovery (“what were we doing last Thursday?”) and for Distillation.
- Can be large. Retrieval must be selective.

**Location:** `data/episodic/`

### 3.2.3 Procedural Layer (Skills & Tools)
**Purpose:** Reusable knowledge of how to do things and what has worked.

**Contents:**
- Skills (primary)
- Anti-patterns / known failure modes
- Tool definitions (when the system creates or improves tools)

**Rules:**
- Every skill must track usage and outcome statistics.
- Skills are versioned.
- Only promoted skills are eligible for automatic use in context packs.

**Location:** `data/procedural/skills/` and `data/procedural/anti-patterns/`

### 3.2.4 Semantic Layer
**Purpose:** Entities, relationships, and structured facts.

**Contents:**
- Named entities (components, people, projects, concepts)
- Relations between them
- Temporal facts where useful

**Rules:**
- Start simple (Markdown + frontmatter). Can later be indexed by a graph or vector store.
- Must remain reconstructible from files.

**Location:** `data/semantic/`

## 3.3 Universal Memory Entry Schema

Every memory file MUST begin with YAML frontmatter containing at least these fields:

```yaml
---
id: "unique-slug-or-uuid"                 # Required, stable
type: "core" | "episode" | "skill" | "anti-pattern" | "entity" | "relation" | "outcome" | "preference" | "tool"
title: "Human readable title"             # Required
created: "2026-07-14T12:00:00Z"           # ISO 8601
updated: "2026-07-14T15:30:00Z"           # ISO 8601
status: "draft" | "active" | "promoted" | "deprecated" | "rejected"
outcome: "success" | "failure" | "partial" | "unknown" | "not_applicable"
confidence: 0.85                          # 0.0 – 1.0
tags: ["loom", "memory", "phase-1"]
related: ["id-of-other-entry-1", "id-of-other-entry-2"]
source: "distillation" | "meta-loop" | "user" | "coding-loop" | "session:2026-07-14-03"
provenance: "Short note about where this knowledge came from"
---
```

### Additional required fields by type

**Skill / Tool entries must also include:**
```yaml
version: 3
success_count: 12
failure_count: 2
success_rate: 0.857
last_used: "2026-07-14T14:00:00Z"
inputs: "Description of expected inputs"
outputs: "Description of outputs"
steps: |
  1. First step...
  2. Second step...
evaluation_notes: "Any notes from the Meta loop"
```

**Episode entries should include:**
```yaml
session_id: "2026-07-14-03"
related_tasks: ["TASK-042"]
```

## 3.4 File Naming Rules (Strict)

- Core: `data/core/YYYYMMDD-short-slug.md`
- Episodic: `data/episodic/YYYYMMDD-HHMM-session-slug.md`
- Skills: `data/procedural/skills/skill-name-vN.md` (N starts at 1)
- Anti-patterns: `data/procedural/anti-patterns/name.md`
- Entities: `data/semantic/entities/entity-slug.md`
- Relations: `data/semantic/relations/relation-slug.md`

Never overwrite a promoted skill. Create a new version instead.

## 3.5 Retrieval Rules for Context Packing

When the Orchestrator calls for an optimized context pack:

1. Always consider active Core entries that match tags or project.
2. Prefer Procedural skills with high success_rate and recent last_used.
3. Pull only the most relevant recent Episodes (not the entire history).
4. Respect the token_budget strictly.
5. Record what was included and why (for later value metrics and debugging).

Ranking signals (in rough order of importance):
- Explicit tag / project match
- Success rate (for skills)
- Recency
- Confidence
- Manual boost / pin (future)

## 3.6 Conflict & Staleness Handling

- If two Core entries contradict each other, both remain but the newer one should note the conflict in its body and link to the older one.
- Distillation Loop and Meta Loop must surface contradictions rather than silently overwrite.
- Deprecated entries stay in the filesystem but are excluded from normal context packs.

## 3.7 Distillation Rules (What gets written where)

| Source Signal                        | Target Layer     | Notes |
|--------------------------------------|------------------|-------|
| Explicit architectural decision      | Core             | High bar |
| Session summary / what happened      | Episodic         | Always |
| Repeated successful procedure        | Procedural/Skill | Candidate |
| Repeated failure mode                | Anti-pattern     | Important |
| New entity or relationship           | Semantic         | When clear |
| Outcome of a coding attempt          | Episodic + update skill stats | Critical for learning |

---

# 4. Specialized Loops – Full Definitions

## 4.1 Common Loop Interface

Every loop must implement at minimum:

- `name: str`
- `can_handle(task) -> bool`
- `claim(task_id) -> bool`
- `run(task) -> LoopResult`
- `heartbeat()`
- `release(task_id)`

`LoopResult` must contain:
- status: success | failure | partial
- outcome_summary: str
- memory_entries_written: list[id]
- artifacts: list of file paths
- lessons: str
- metrics: dict

## 4.2 Distillation Loop – Detailed Specification

**Primary Responsibility:** Turn raw session activity into clean, structured Loom Memory entries.

**Triggers:**
- End of a coding session (most common)
- Manual command (`loom distill`)
- Periodic background run (future)

**Algorithm (Step-by-step):**
1. Load the latest SESSION_LOG.md entries and any associated raw logs.
2. Identify candidate knowledge:
   - Decisions made
   - Outcomes of attempts
   - Potential new skills or improvements to existing skills
   - New entities or relations
   - Failures worth recording as anti-patterns
3. For each candidate, decide the correct target layer using the table in 3.7.
4. Write well-formed memory entries (correct frontmatter + clear body).
5. Update success/failure counts on any skills that were used.
6. Write an Episode recording that distillation itself occurred.
7. Return a LoopResult describing what was written.

**Quality Rules:**
- Prefer precision over volume. One clear decision is better than five vague ones.
- Never invent facts that were not present in the source material.
- When uncertain, write with lower confidence and status: draft.

## 4.3 Coding Support Loop

**Primary Responsibility:** Help OpenCode do better work by supplying high-quality context and recording outcomes.

**Key Behaviors:**
- Before major coding steps, request an optimized context pack from the Orchestrator.
- After coding attempts (especially after tests or user feedback), record the outcome.
- If an existing skill is relevant, surface it.
- Never take ownership of the actual code-writing away from OpenCode unless explicitly designed to.

## 4.4 Meta / Self-Improvement Loop – Detailed Specification

This is the learning engine of Loom Core.

### 4.4.1 Goals of the Meta Loop
1. Detect capability gaps and repeated failures.
2. Propose new skills or tools.
3. Propose improvements to existing skills.
4. Evaluate proposals against recorded evidence.
5. Promote, reject, or request human review.
6. Keep a clear audit trail of every proposed change.

### 4.4.2 Detection Signals
The Meta Loop should look for:
- Skills with low or declining success_rate
- Repeated similar failures across episodes
- Tasks that required many retries
- Explicit user corrections
- Missing capabilities that forced workarounds
- High-value procedures that are not yet captured as skills

### 4.4.3 Proposal Types
- **New Skill** – A reusable procedure that does not yet exist
- **Skill Improvement** – A new version of an existing skill
- **New Tool** – A callable capability (function, script, or MCP-style tool) the system currently lacks
- **Anti-pattern** – A documented failure mode to avoid
- **Deprecation** – Marking a skill as no longer recommended

### 4.4.4 Evaluation Criteria (Minimum)
A proposal may be promoted only if:
- There is clear evidence from recorded outcomes
- The expected improvement is stated
- A concrete success metric is defined (even if simple)
- The change is versioned and reversible

### 4.4.5 Skill / Tool Lifecycle State Machine

```
[Detected Gap]
     ↓
[Proposal Created] (status: draft)
     ↓
[Evaluation] → (insufficient evidence) → [Rejected]
     ↓ (sufficient evidence)
[Accepted]
     ↓
[Promoted] (status: promoted / active)
     ↓
[In Use] → success/failure stats updated
     ↓
[Improvement Proposed] → new version created
     or
[Deprecated]
```

### 4.4.6 Tool Creation Rules

When the Meta Loop decides a new tool is needed:

1. It must write a clear specification of the tool (purpose, inputs, outputs, side effects).
2. It should prefer generating a simple, testable implementation (Python function or script).
3. The new tool must be registered in a known location and made visible to the Orchestrator and other loops.
4. An initial skill entry must be created that knows how to use the tool.
5. The tool starts in a “candidate” state until it has demonstrated value.

**Important:** Tool creation is powerful and dangerous. Early versions of the Meta Loop should propose tools but require explicit promotion (or at least clear logging) before they become freely usable.

---

# 5. Tool & Skill Creation and Improvement System

## 5.1 Definitions

- **Skill**: A documented, reusable procedure (usually Markdown + metadata). It may or may not call tools.
- **Tool**: An executable capability (function, CLI command, script, or external MCP tool) that can be invoked.

## 5.2 Skill Format (Canonical)

Skills live at `data/procedural/skills/skill-name-vN.md` and follow the schema in section 3.3 plus the extra skill fields.

Body of a skill should contain:
- Clear purpose
- When to use / when not to use
- Step-by-step instructions
- Example inputs and outputs
- Known limitations
- Links to related skills or anti-patterns

## 5.3 Improvement Process

1. Meta Loop or Distillation Loop notices a better way.
2. A new version file is created (`skill-name-vN+1.md`).
3. The new version references the previous version in `related`.
4. Stats start fresh or are optionally carried over with a note.
5. Only after evaluation is the new version marked `promoted`.
6. Older versions may be marked `deprecated` but are never deleted.

## 5.4 Registration & Discovery

The Orchestrator and Context Packer must be able to discover all promoted skills and available tools by scanning the procedural directory and any tool registry file (e.g. `data/procedural/tools/registry.json` or equivalent).

---

# 6. Orchestrator Interactions with Memory and Loops

The Orchestrator is the only component allowed to:
- Grant and revoke task ownership
- Assemble final context packs that are sent to models
- Enforce that loops write continuity and memory records

Data flow for a typical improved coding session:

1. User / OpenCode starts work.
2. Coding Support Loop requests context pack.
3. Orchestrator queries Loom Memory → returns optimized pack.
4. Coding proceeds.
5. Outcomes are recorded (by Coding Support Loop or Distillation).
6. Distillation Loop runs → new memory entries.
7. Meta Loop periodically reviews outcomes → may propose skill/tool improvements.
8. All of the above is reflected in continuity files.

---

# 7. Continuity Protocol – Expanded Edge Cases

### Missing Continuity Files
If any sacred file is missing at session start, the agent must:
1. Stop
2. Report the problem
3. Recreate the file from template if safe
4. Log the recovery

### Conflicting Information
If TASKS.md and PROGRESS.md disagree, prefer the more recent SESSION_LOG entry and surface the conflict.

### Partial Session Crashes
If a session ends abnormally, the next session must note the incomplete work and attempt to reconstruct state from the last known good continuity entries + memory.

---

# 8. Value Metrics – Precise Definitions

Track at minimum:

- `tokens_saved_estimate`: Difference between full-history baseline and actual packed context
- `decisions_preserved`: Count of Core + high-value decision entries
- `skills_created`
- `skills_promoted`
- `skills_improved`
- `average_skill_success_rate`
- `distillation_runs`
- `recovery_events` (times a session started by loading from memory rather than blank state)
- `ownership_conflicts`

These must be derived from real recorded data.

---

# 9. Expanded Phase 0 & Phase 1 Task Breakdown

### Phase 0 – Foundation (Immediate)
- TASK-001: Create exact directory structure
- TASK-002: Create all continuity files with proper headers and templates
- TASK-003: Write initial PROGRESS.md, TASKS.md, etc.
- TASK-004: Create this specification file in docs/ or root
- TASK-005: Basic Python project setup (pyproject.toml, src layout, testing skeleton)
- TASK-006: .gitignore that protects data/ and secrets
- TASK-007: First SESSION_LOG entry recording Phase 0 completion

### Phase 1 – Memory MVP
- TASK-010: Define Pydantic (or equivalent) models for all memory entry types
- TASK-011: Implement atomic memory writer
- TASK-012: Implement memory reader and basic list/filter
- TASK-013: Implement simple keyword search
- TASK-014: CLI commands for memory write / list / show
- TASK-015: Validation that rejects malformed entries
- TASK-016: Unit + integration tests using temporary directories
- TASK-017: Record first real memory entries from the development process itself

---

# 10. Coding Agent Operating Rules (Reinforced)

1. Never begin coding until continuity files have been read.
2. After any meaningful change, update the relevant tracking files before continuing.
3. When creating a new skill or tool, follow the schema and lifecycle exactly.
4. Prefer writing one clean memory entry over several vague ones.
5. At the end of every session, write a complete SESSION_LOG entry. This is not optional.
6. If you are unsure where knowledge belongs (which layer), write it as draft in Episodic and note the uncertainty.

---

# 11. Open Questions & Future Extension Points (Explicitly Marked)

These are intentionally not fully specified yet so the system can evolve:

- Exact ranking algorithm weights for context packing
- Whether to introduce a vector index in Phase 2 or 3
- How aggressive automatic tool promotion should be
- Multi-project isolation strategy
- Desktop app information architecture

Any decision on these must be recorded in DECISIONS.md.

---

# 12. Final Binding Statement

The Memory System, the Distillation Loop, the Meta/Self-Improvement Loop, and the Skill/Tool creation & improvement system are the differentiators of Loom Core.

They must be implemented with the level of care and explicitness described in this document. Shortcuts that lose outcome data, skip versioning, or write unstructured knowledge will undermine the entire purpose of the project.

**End of Expanded Master Specification v2.0**

OpenCode + DeepSeek V4 Pro:  
Your next concrete action is to begin Phase 0 by creating the repository structure and all continuity tracking files exactly as specified, then record that work in SESSION_LOG.md and PROGRESS.md.
