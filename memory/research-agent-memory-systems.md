# Research Report: Agent Memory & Coordination Systems

*Research conducted 2026-01-30 by Portal1 subagent*

---

## Table of Contents
1. [Toby Lütke's QMD — Key Ideas](#1-qmd)
2. [Letta (formerly MemGPT) — Stateful Agent Memory](#2-letta)
3. [Agent Skills Standard — Progressive Disclosure](#3-agent-skills)
4. [CrewAI Memory — Multi-Agent Shared Memory](#4-crewai)
5. [AutoGen Teams — Multi-Agent Coordination](#5-autogen)
6. [Patterns & Principles Synthesis](#6-synthesis)
7. [Recommendations for Our Setup](#7-recommendations)
8. [Token Efficiency Strategies](#8-token-efficiency)
9. [What to Change in Our Current System](#9-changes)

---

## 1. QMD — Toby Lütke's Local Search Engine for Agent Memory {#1-qmd}

**Repo:** [github.com/tobi/qmd](https://github.com/tobi/qmd) (4.5k stars)
**What it is:** A local CLI search engine for markdown notes, meeting transcripts, documentation, and knowledge bases. Designed to be the memory retrieval layer for agentic workflows.

### Architecture

QMD combines three search strategies into a hybrid pipeline:

1. **BM25 full-text search** (SQLite FTS5) — fast keyword matching
2. **Vector semantic search** (embeddinggemma-300M) — meaning-based similarity
3. **LLM re-ranking** (qwen3-reranker-0.6b) — quality assessment via logprobs

All models run locally via `node-llama-cpp` with GGUF quantized models (~2GB total).

### Key Design Decisions

| Decision | Why It Matters |
|----------|---------------|
| **Hybrid search (BM25 + vector + rerank)** | No single search method works for all queries. BM25 is fast for exact terms, vectors catch semantic meaning, reranking adds judgment. |
| **Reciprocal Rank Fusion (RRF)** | Merges results from multiple search backends without needing to normalize scores to the same scale. |
| **Position-aware blending** | Top-3 results trust retrieval 75%, bottom results trust reranker 60%. Prevents the reranker from displacing exact matches. |
| **Query expansion** (fine-tuned 1.7B model) | Generates alternative phrasings to catch documents the original query might miss. |
| **Collections with context** | Each document collection gets human-written descriptions that help search understand what the collection is about. |
| **MCP server built-in** | Agents can query QMD via Model Context Protocol — standardized tool interface. |
| **Everything local** | No cloud dependencies. Privacy-first. Works offline. |

### Agent Integration Patterns

QMD was explicitly designed for agent workflows:
- `--json` and `--files` output formats for LLM consumption
- `--min-score` threshold to filter noise
- `--full` flag to get complete documents (not just snippets)
- `qmd get` retrieves specific documents by path or short hash ID
- `qmd multi-get` with glob patterns for bulk retrieval

### What We Can Learn

**The core insight:** Agents need a search layer between "read entire file" and "don't know it exists." QMD fills this gap — it's the agent's ability to *remember what's relevant* without loading everything into context.

**For our setup:** We currently load LEARN.md and MEMORY.md wholesale every session. QMD's approach suggests we should be able to *search* our knowledge base and load only relevant sections. However, our knowledge base is still small enough (<15KB combined) that full loading is fine. The QMD pattern becomes essential when we scale to multiple agents with large shared knowledge.

---

## 2. Letta (formerly MemGPT) — Stateful Agent Memory {#2-letta}

**Repo:** [github.com/letta-ai/letta](https://github.com/letta-ai/letta) (originally cpacker/MemGPT)
**What it is:** Platform for building stateful agents with advanced memory that persists across sessions and self-improves over time.

### Core Architecture

Letta's memory model uses **named memory blocks** — labeled sections of the context window:

```
┌─────────────────────────────────────┐
│ System Prompt                        │
├─────────────────────────────────────┤
│ Memory Block: "human"               │  ← Who the user is
│ Memory Block: "persona"             │  ← Who the agent is
│ Memory Block: "project"             │  ← Current project context
│ Memory Block: "project-conventions" │  ← Coding patterns
│ Memory Block: "project-gotchas"     │  ← Footguns to avoid
├─────────────────────────────────────┤
│ Conversation History                 │
├─────────────────────────────────────┤
│ Available Tools                      │
└─────────────────────────────────────┘
```

Each block has:
- A **label** (human, persona, project, etc.)
- A **description** (what it contains)
- **Content** (the actual text)
- A **character limit** (prevents unbounded growth)
- **Read/write access** by the agent itself

### Sleep-time Agents (Async Memory Management)

This is Letta's most innovative pattern. A **sleep-time agent** runs in the background alongside the primary agent:

- **Shares memory blocks** with the primary agent
- **Triggered every N steps** (default: 5) of the primary agent's conversation
- **Reflects on conversation history** to update memory blocks
- **Works asynchronously** — doesn't block the primary agent

Think of it as a background process that watches conversations and distills important information into permanent memory. This is essentially an automated version of what our AGENTS.md tells us to do manually ("review daily files and update MEMORY.md with what's worth keeping").

### Subagent Architecture

Letta Code supports 5 built-in subagent types:

| Type | Purpose | Model | Can Edit? |
|------|---------|-------|-----------|
| **explore** | Fast codebase search | Haiku (cheap) | Read-only |
| **general-purpose** | Full implementation | Sonnet (balanced) | Yes |
| **memory** | Clean up & reorganize memory blocks | Opus (smart) | Memory files |
| **plan** | Break down complex tasks | Opus | Read-only |
| **recall** | Search conversation history | Opus | Read-only |

Key properties:
- **Stateless** — each invocation is independent
- **Autonomous** — can't ask questions mid-execution
- **Context-aware** — see full conversation history
- **Parallel** — can run concurrently

### `/init` — Onboarding Pattern

When starting with a new project, Letta's `/init` command:
1. Asks the user questions (research depth, identity, workflow preferences)
2. Reads README, configs, git history
3. Explores key directories
4. Creates/updates memory blocks incrementally

Two modes:
- **Standard:** Quick (~5-20 tool calls) — essentials only
- **Deep:** Comprehensive (~100+ tool calls) — full architecture analysis, contributor patterns, conventions

### What We Can Learn

1. **Named memory blocks with character limits** prevent unbounded memory growth — our MEMORY.md has no size constraint
2. **Sleep-time agents** automate memory maintenance that we currently do manually in heartbeats
3. **Dedicated memory subagent** (uses Opus-level reasoning) for reorganizing and defragmenting memory
4. **Memory blocks are shared between agents** — this is the coordination primitive
5. **`/init` command** for deliberate project onboarding is more structured than our ad-hoc boot sequence

---

## 3. Agent Skills Standard — Progressive Disclosure {#3-agent-skills}

**Spec:** [agentskills.io](https://agentskills.io) | [github.com/agentskills/agentskills](https://github.com/agentskills/agentskills)
**Origin:** Created by Anthropic, released as open standard (Dec 2025)
**Adoption:** Claude Code, Cursor, VS Code/Copilot, Letta Code, OpenAI Codex, and more

### The Progressive Disclosure Pattern

This is the most important architectural pattern from the research. Skills implement a **3-level progressive disclosure system**:

```
Level 0: Name + description only (always in system prompt)
         → Agent knows skill exists, when to use it
         → Cost: ~50 tokens per skill

Level 1: Full SKILL.md content (loaded on demand)
         → Core instructions, workflows, conventions
         → Cost: varies, loaded only when relevant

Level 2: Bundled reference files (loaded as needed)
         → API docs, schemas, scripts, examples
         → Cost: potentially large, loaded only for specific subtasks
```

**Key insight from Anthropic's blog post:** "Agents with a filesystem and code execution tools don't need to read the entirety of a skill into their context window. This means the amount of context that can be bundled into a skill is effectively unbounded."

### Skill Directory Structure

```
.skills/
├── testing/
│   └── SKILL.md                    ← Always discoverable
├── api-client/
│   ├── SKILL.md                    ← Loaded when relevant
│   └── references/
│       ├── endpoints.md            ← Loaded when doing API work
│       └── error-codes.md          ← Loaded when debugging
└── deployment/
    ├── SKILL.md
    └── scripts/
        └── deploy.sh               ← Executed, not loaded into context
```

### Resolution Priority

Skills are discovered from multiple locations with priority ordering:
1. **Project** (`.skills/`) — project-specific
2. **Agent** (`~/.letta/agents/{id}/skills/`) — agent-specific
3. **Global** (`~/.letta/skills/`) — shared across all agents
4. **Bundled** — built-in defaults

### Skill Learning

The `/skill` command in Letta Code triggers the agent to:
1. Reflect on recent successful approaches
2. Review pitfalls encountered
3. Extract reusable patterns
4. Write a new skill capturing that knowledge

This is **automated learning** — the agent itself creates skills from experience.

### What We Can Learn

1. **Our current system is flat** — LEARN.md, MEMORY.md, TOOLS.md are all loaded wholesale. There's no progressive disclosure.
2. **We should adopt the skill format** — SKILL.md with name/description frontmatter for each capability
3. **Scripts bundled with skills > instructions in markdown** — deterministic, don't consume context tokens
4. **Cross-platform portability** — skills written for our agent could work in Claude Code, Cursor, etc.

---

## 4. CrewAI Memory — Multi-Agent Shared Memory {#4-crewai}

**Docs:** [docs.crewai.com/concepts/memory](https://docs.crewai.com/en/concepts/memory)

### Memory Components

CrewAI provides four memory types:

| Type | Storage | Purpose | Persistence |
|------|---------|---------|-------------|
| **Short-term** | ChromaDB (RAG) | Recent interactions, current context | Current execution |
| **Long-term** | SQLite | Task results, insights from past runs | Cross-session |
| **Entity** | ChromaDB (RAG) | People, places, concepts encountered | Cross-session |
| **Contextual** | Combined | Merges all above for coherent responses | Runtime |

### Key Pattern: Entity Memory

CrewAI automatically extracts and tracks entities (people, organizations, concepts) across conversations. When an agent encounters "Daniel mentioned the Pi 5 project," it updates entries for both "Daniel" and "Pi 5 project" with the new context.

This is interesting for our multi-agent setup — shared entity memory means all agents automatically know about the same people, projects, and concepts without explicit coordination.

### What We Can Learn

1. **Entity extraction as a memory primitive** — automatically track people, projects, tools mentioned
2. **Separate storage for different memory types** — don't mix ephemeral context with long-term knowledge
3. **RAG for short-term memory** — search recent interactions instead of replaying full conversation

---

## 5. AutoGen Teams — Multi-Agent Coordination {#5-autogen}

**Docs:** [microsoft.github.io/autogen](https://microsoft.github.io/autogen/stable/)

### Team Topologies

AutoGen provides 4 coordination patterns:

| Pattern | How It Works | Best For |
|---------|-------------|----------|
| **RoundRobin** | Agents take turns, share full context | Reflection, review cycles |
| **SelectorGroup** | LLM picks next speaker after each message | Dynamic task routing |
| **MagenticOne** | Orchestrator + specialist agents | Complex multi-domain tasks |
| **Swarm** | Handoff messages signal transitions | Workflow pipelines |

### The Swarm Pattern

Most relevant for our setup. Agents communicate via **handoff messages** — explicit signals that pass control and context:

```
Agent A: "I've finished the data analysis. Handing off to visualization agent."
         → HandoffMessage(target="viz_agent", context={...})
         
Agent B (viz_agent): Receives context, continues work
```

This is essentially what our Convex chat infrastructure could implement.

### What We Can Learn

1. **Start with single agents, move to teams only when needed** — AutoGen explicitly warns against premature multi-agent architectures
2. **Handoff messages** are a clean coordination primitive
3. **Shared context** (all agents see all messages) is simplest but most expensive
4. **Termination conditions** prevent runaway conversations

---

## 6. Patterns & Principles Synthesis {#6-synthesis}

### Universal Patterns Across All Systems

| Pattern | Used By | Description |
|---------|---------|-------------|
| **Progressive disclosure** | Agent Skills, Letta, QMD | Load context in layers, not all at once |
| **Named memory blocks** | Letta, CrewAI | Labeled, bounded sections of persistent memory |
| **Async memory maintenance** | Letta (sleep-time) | Background process that curates memory |
| **Search over memory** | QMD, CrewAI (RAG) | Query-based retrieval vs. wholesale loading |
| **Skill/capability packaging** | Agent Skills, Letta Skills | Self-contained instructions with metadata |
| **Subagent delegation** | Letta, AutoGen, Clawdbot | Spawn focused workers for specific tasks |
| **Entity tracking** | CrewAI | Automatically extract and maintain entity knowledge |
| **Shared memory blocks** | Letta, CrewAI | Multiple agents read/write the same memory |
| **Model tiering** | Letta subagents | Cheap models for search, expensive for reasoning |

### The Maturity Model

```
Level 1: File-based memory (MEMORY.md, daily logs)     ← We are here
Level 2: Structured blocks with progressive disclosure   ← Next step
Level 3: Search-based retrieval (QMD/RAG)               ← When knowledge grows
Level 4: Async memory maintenance (sleep-time agents)    ← When we have multiple agents
Level 5: Shared memory with entity tracking              ← Full multi-agent coordination
```

---

## 7. Recommendations for Our Setup {#7-recommendations}

### Immediate (Low Effort, High Impact)

#### 7.1 Adopt Progressive Disclosure in Our File System

**Current:** AGENTS.md says "read MEMORY.md, LEARN.md, daily logs" — agent loads everything.

**Proposed:** Structure files so agents load only what's needed:

```
/home/clawd/
├── AGENTS.md          ← Boot instructions (auto-injected, keep small)
├── SOUL.md            ← Personality (auto-injected, keep small)
├── USER.md            ← Human profile (auto-injected, keep small)
├── TOOLS.md           ← Hardware/software ref (auto-injected, keep small)
├── MEMORY.md          ← Operational state only (~1KB max)
├── LEARN.md           ← Index/TOC only — points to deeper docs
├── knowledge/         ← Deeper knowledge loaded on demand
│   ├── hardware.md    ← Detailed hardware reference
│   ├── techniques.md  ← Patterns and lessons learned
│   ├── vision.md      ← Long-term roadmap
│   └── agents.md      ← Agent registry and coordination details
├── skills/            ← Existing skills (already use SKILL.md pattern!)
└── memory/            ← Daily logs (unchanged)
```

**Key change:** LEARN.md becomes a **table of contents** (~500 tokens) instead of a full document (~3000 tokens). Agents load deeper docs only when working on relevant tasks.

#### 7.2 Add Character Limits to Memory Files

Borrow from Letta: each memory file has a **size budget**:

| File | Max Size | Purpose |
|------|----------|---------|
| MEMORY.md | 2KB | Operational state, active projects, key lessons |
| LEARN.md (index) | 1KB | TOC with descriptions, links to knowledge/ |
| Daily logs | 5KB each | Raw session notes, trimmed after 7 days |

This prevents the "ever-growing MEMORY.md" problem.

#### 7.3 Skill Format for Our Existing Skills

We already have `skills/` with SKILL.md files! Make sure they follow the Agent Skills standard format with frontmatter:

```yaml
---
name: parakeet-stt
description: Local speech-to-text using Parakeet TDT. Use when transcribing audio files or setting up voice pipeline.
---
```

This makes skills discoverable by name/description without loading full instructions.

### Medium-Term (Multi-Agent Foundation)

#### 7.4 Shared Knowledge Base via Convex

When agents coordinate via Convex chat, they need shared memory:

- **Entity registry** in Convex — agents post entity updates (people, projects, tools)
- **Learning channel** — agents post discoveries, other agents subscribe
- **Task handoff protocol** — structured messages with context for delegation

#### 7.5 Agent Boot Sequence Standardization

Borrow from Letta's `/init`:

```
1. Read auto-injected files (AGENTS.md, SOUL.md, USER.md, TOOLS.md)
2. Read MEMORY.md (operational state)
3. Read LEARN.md index (discover what knowledge exists)
4. Read today's daily log (recent context)
5. Load relevant skills/knowledge based on current task
```

Step 5 is the key addition — currently we don't do task-based knowledge loading.

#### 7.6 Memory Maintenance as a Subagent

Instead of doing memory maintenance during heartbeats (which conflicts with checking email, calendar, etc.), spawn a dedicated memory subagent periodically:

```
Cron: Every 6 hours
Task: Review recent daily logs, update MEMORY.md, trim stale info, 
      update LEARN.md index if new knowledge was captured
Model: Use cheaper model (Sonnet) — this is maintenance, not creative work
```

### Long-Term (Multi-Agent Ecosystem)

#### 7.7 QMD-Style Search Layer

When knowledge base exceeds ~50KB, deploy a search index:

- Index all markdown files in workspace
- Agents query before loading full documents
- Could run QMD on Pi 5 (Bun + SQLite + small GGUF models — needs testing on arm64)
- Alternative: Simple BM25 search via SQLite FTS5 (no ML models needed, very lightweight)

#### 7.8 Sleeptime Agent Pattern

When we have multiple agents active:
- Designate one agent (or subagent) as the "memory curator"
- It watches all agent conversations (via Convex)
- Periodically distills important information into shared knowledge
- Updates entity registry, project status, lessons learned

---

## 8. Token Efficiency Strategies {#8-token-efficiency}

### Current Token Budget (Estimated)

| Component | Tokens | When Loaded |
|-----------|--------|-------------|
| AGENTS.md | ~2,500 | Auto-injected every session |
| SOUL.md | ~500 | Auto-injected every session |
| USER.md | ~200 | Auto-injected every session |
| TOOLS.md | ~2,000 | Auto-injected every session |
| MEMORY.md | ~1,500 | Read at boot |
| LEARN.md | ~3,000 | Read at boot |
| Daily log | ~1,000 | Read at boot |
| **Total boot cost** | **~10,700** | **Every session** |

### Reduction Strategies

1. **Compress AGENTS.md** — Remove examples and verbose explanations. Agent already knows how to be an agent. Target: 1,500 tokens (save ~1,000).

2. **Split LEARN.md into index + files** — Index-only LEARN.md at ~500 tokens. Load knowledge/ files only when relevant. Save ~2,500 tokens per session when topic isn't relevant.

3. **TOOLS.md tiering** — Core info (hostname, key commands) stays injected. Detailed service configs, Python envs, gotchas move to `knowledge/hardware.md`. Target: 1,200 tokens injected (save ~800).

4. **Daily log pruning** — Only load today's log. Yesterday's log loaded only if referenced. Older logs: search, don't load.

5. **Skip MEMORY.md in subagent sessions** — Subagents don't need operational state. They get task-specific context from the spawning agent.

### Projected Savings

| Component | Current | After Optimization | Savings |
|-----------|---------|-------------------|---------|
| AGENTS.md | 2,500 | 1,500 | 1,000 |
| TOOLS.md | 2,000 | 1,200 | 800 |
| LEARN.md | 3,000 | 500 (index) | 2,500 |
| Daily log | 1,000 | 500 (today only) | 500 |
| **Total** | **10,700** | **5,900** | **4,800 (45%)** |

---

## 9. What to Change in Our Current System {#9-changes}

### AGENTS.md Changes

1. **Add LEARN.md to the mandatory boot reads** (step 3 of "Every Session")
2. **Add "Load relevant knowledge on demand"** as step 5
3. **Compress the file** — Many sections repeat what the LLM already knows (how to use memory, how to be safe). Keep only our-specific conventions.
4. **Add subagent context protocol** — When spawning subagents, what context to pass vs. omit

### MEMORY.md Changes

1. **Add a size budget header:** `<!-- Max: 2KB. Prune aggressively. -->`
2. **Separate "operational state" from "lessons learned"** — State changes frequently, lessons are permanent
3. **Add timestamps to entries** — Know when something was last verified
4. **Remove file map** — It's static info that belongs in AGENTS.md

### LEARN.md Changes (Biggest Impact)

1. **Transform into an index/TOC** — Each section becomes a 1-line summary + link
2. **Move content to knowledge/ directory:**
   - `knowledge/infrastructure.md` — Hardware, services, platforms
   - `knowledge/techniques.md` — STT pipeline, camera, Hailo patterns  
   - `knowledge/agents.md` — Registry, communication channels, coordination
   - `knowledge/vision.md` — Roadmap, phases, evolution model
   - `knowledge/tasks.md` — Active task lists
3. **Keep design principles in LEARN.md** — They're small and should be in every agent's boot context

### TOOLS.md Changes

1. **Tier the content** — Essential commands in TOOLS.md, detailed configs in knowledge/
2. **Add "Quick Reference" section at top** — The 5 most-used commands
3. **Remove "What's NOT Available"** — Agents don't need to know what's absent every session

### New Files to Create

1. **`knowledge/` directory** — Progressive disclosure knowledge base
2. **`HEARTBEAT.md` with actual content** — Currently empty, should have a minimal checklist
3. **`.skills/` directory** — Adopt Agent Skills standard for project-level skills (in addition to existing `skills/`)

### New Patterns to Adopt

1. **Memory maintenance subagent** — Cron job every 6 hours, cheaper model
2. **Task-based knowledge loading** — Agent checks LEARN.md index before loading knowledge files
3. **Entity tracking** — Simple JSON file tracking people, projects, tools mentioned across sessions
4. **Skill learning** — After completing novel tasks, agent writes a skill capturing what worked

---

## Sources

1. **QMD** — github.com/tobi/qmd — Toby Lütke's local search engine for agent memory
2. **Letta/MemGPT** — github.com/letta-ai/letta — Stateful agent platform with memory blocks
3. **Letta Code Skills** — docs.letta.com/letta-code/skills — On-demand skill loading
4. **Letta Code Subagents** — docs.letta.com/letta-code/subagents — Delegation patterns
5. **Letta Code Memory** — docs.letta.com/letta-code/memory — Memory blocks and maintenance
6. **Letta Sleep-time Agents** — docs.letta.com/guides/agents/architectures/sleeptime — Async memory
7. **Agent Skills Standard** — agentskills.io — Open skill format by Anthropic
8. **Anthropic Skills Blog** — claude.com/blog/equipping-agents-for-the-real-world-with-agent-skills
9. **Anthropic Skills Repo** — github.com/anthropics/skills — Example skills
10. **CrewAI Memory** — docs.crewai.com/en/concepts/memory — Multi-agent memory components
11. **AutoGen Teams** — microsoft.github.io/autogen — Multi-agent coordination patterns
12. **Clawdbot Docs** — docs.clawd.bot (returning 404 as of research date)

---

*This research was conducted to inform the design of our multi-agent memory and coordination system. The recommendations are ordered by effort and impact — start with the immediate changes and progress as the system grows.*
