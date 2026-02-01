# QMD Integration — Spec & Experiment Design

## Hypothesis
QMD (Tobi Lütke's local hybrid search engine) can replace our broken `memory_search` and become the foundation of Portal1's knowledge retrieval system.

**Current state:** `memory_search` fails (no OpenAI/Google key for embeddings). Knowledge retrieval is linear file reading — slow, context-heavy, doesn't scale.

**Target state:** Semantic + keyword search across all markdown, build logs, daily memory, specs, case studies. Any agent (main or sub-agent) can query knowledge in <1s.

## What QMD Brings
- BM25 full-text search (SQLite FTS5 — we already use this in catalog)
- Vector semantic search (GGUF embeddings, local)
- LLM reranking (optional, heavier)
- MCP server for agent integration
- CLI for direct use

## Known Risks

| Risk | Severity | Mitigation | How We'll Test |
|------|----------|------------|---------------|
| **arm64 compatibility** | 🔴 Blocker | sqlite-vec has no linux-arm64 prebuilt binary | Task 1: try install, capture exact error |
| **Bun on Pi 5** | 🟡 Medium | Bun supports linux-arm64 but may have quirks | Task 1: install + version check |
| **node-llama-cpp on arm64** | 🟡 Medium | GGUF inference on CPU — may be too slow | Task 3: benchmark embedding speed |
| **Memory pressure** | 🟡 Medium | Embedding model + Parakeet + camservice = competition for RAM | Task 3: measure RSS during embed |
| **Index size** | 🟢 Low | Our corpus is small (~50 markdown files) | Task 4: measure db size |

## Experiment Design

### Phase 1: Can it run? (Discovery)
**Goal:** Determine if QMD works on arm64. No code changes, just install and observe.
**Success criteria:** `qmd --help` runs, `qmd collection add` works, `qmd search` returns results.
**Failure criteria:** sqlite-vec won't compile, or Bun won't install. → Document blockers, evaluate alternatives.

### Phase 2: Does it work well? (Evaluation)
**Goal:** Measure search quality and speed on our actual knowledge base.
**Eval method:**
1. Create a set of 10 test queries with known correct answers (ground truth)
2. Run each query through `qmd search` (BM25), `qmd vsearch` (vector), `qmd query` (hybrid)
3. Score: Did the correct file appear in top 3 results? Top 1?
4. Measure: query latency, index time, memory usage

**Test queries (draft):**
| Query | Expected Top Result | Tests |
|-------|-------------------|-------|
| "how to start streaming" | TOOLS.md or memory/2026-01-31.md | Keyword + semantic |
| "what is the context cliff" | HEURISTICS.md | Semantic (concept) |
| "camera service port" | TOOLS.md | Keyword (exact) |
| "why did bulk builds fail" | CASE_STUDY.md | Semantic (reasoning) |
| "Hailo capabilities" | TOOLS.md or LEARN.md | Keyword + semantic |
| "Mudpaw's directives" | memory/2026-02-01.md | Semantic (who said what) |
| "scrubber bouncing fix" | memory/2026-02-01.md | Keyword (bug name) |
| "intercom mode plan" | MEMORY.md | Semantic (future plan) |
| "dependency principle" | HEURISTICS.md | Exact match |
| "how to write a task brief" | templates/BRIEF.md | Semantic (how-to) |

### Phase 3: Integration (Build)
**Goal:** Wire QMD into our workflow so it's the default search layer.
**Only proceed if Phase 2 passes with >70% top-3 accuracy.**

Integration points:
- Replace broken `memory_search` with `qmd search` via CLI
- Add to orchestrator: builders can query knowledge base before writing code
- Auto-reindex on git commit (hook or cron)
- MCP server for future multi-agent access

## Taskboard

### Task 1: Install & Smoke Test ⬜
**Scope:** System-level install only
**Depends on:** none
**Changes:**
- Install Bun if not present
- Clone/install QMD
- Run `qmd --help`
- Document any arm64 issues encountered
**Validate:**
```bash
bun --version
qmd --help 2>&1 | head -5
```
**Decision gate:** If this fails, STOP. Document the blocker. Don't try to fix it yet — evaluate alternatives first.

### Task 2: Index Our Knowledge Base ⬜
**Scope:** QMD collections only (no code changes to our files)
**Depends on:** Task 1
**Changes:**
- `qmd collection add /home/clawd --name portal1-kb`
- Add context descriptions
- Run initial index
- Test basic search: `qmd search "camera service"`
**Validate:**
```bash
qmd search "camera service" | head -10
qmd search "context cliff" | head -10
qmd status
```

### Task 3: Benchmark ⬜
**Scope:** Measurement only — no changes
**Depends on:** Task 2
**Changes:**
- Generate embeddings: `qmd embed` (measure time + memory)
- Run all 10 test queries through search/vsearch/query
- Record: latency per query, accuracy (top-1, top-3), RAM usage
- Document results in this file
**Validate:**
```bash
# Run eval script (we'll write a small one)
python3 systems/qmd/eval_search.py
```

### Task 4: Integration Decision ⬜
**Scope:** Documentation only
**Depends on:** Task 3
**Changes:**
- Review benchmark results
- Decision: proceed with integration, modify approach, or find alternative
- If proceeding: write integration taskboard
- Update CASE_STUDY.md with experiment results
- Update HEURISTICS.md with any new learnings
**Validate:** Decision documented with evidence.

## What We're Learning

This experiment tests several heuristics:
- **H1 (Scope Rule):** Task 1 is pure discovery — no code to specify. Is that ok? Or should we write exact commands?
- **H2 (Verification Gap):** Search quality is experiential — how do we eval it without human judgment on every query?
- **H5 (Dogfood):** We'll use QMD to search our own knowledge about QMD as soon as it's indexed.
- **H6 (Three Outputs):** Each phase produces: results + documentation + updated heuristics.

## Alternatives (if QMD fails on arm64)
1. **Port QMD's approach to Python** — Use our existing SQLite + FTS5 catalog pattern, add sentence-transformers for vectors
2. **Remote QMD** — Run on a different machine, query via MCP
3. **Simpler approach** — BM25-only search (no vectors), similar to our catalog.py. Fast, no model dependencies.
4. **Fix memory_search** — Configure an API key for the built-in Clawdbot embedding search

---

*This spec follows the scientific method: hypothesis → experiment design → controlled execution → measurement → decision. Every phase has explicit success/failure criteria and a decision gate.*
