# Knowledge Search — Upgrade Path & Research Guide

*What's cutting edge, what to look for, and how Mudpaw can help guide the upgrades.*

## Where We Are Now (2026-02-01)

| Layer | Technology | Performance | Quality |
|-------|-----------|-------------|---------|
| **Keyword** | QMD + SQLite FTS5 (BM25) | 0.37s | ★★★★ for our corpus |
| **Vector** | embeddinggemma 300M (Q8_0) | 1.5s | ★★☆☆ surface-level similarity |
| **Reranking** | None (1.7B model too slow) | N/A | N/A |
| **Index** | sqlite-vec (cosine distance) | Instant lookup | Works on arm64 ✅ |

**Why vector search underperforms:** The embeddinggemma 300M model is small and general-purpose. It matches word patterns, not deep semantics. "Context cliff" matches "context" in HEARTBEAT.md rather than the concept of context degradation in HEURISTICS.md.

---

## Upgrade Path: Three Tiers

### Tier 1: Better Embedding Model (Easiest Win)
**What:** Swap embeddinggemma 300M for a higher-quality model in GGUF format.

**Top candidates:**
| Model | Size | MTEB Score | GGUF? | Notes |
|-------|------|-----------|-------|-------|
| **nomic-embed-text-v1.5** | 137M params, ~270MB Q8 | Strong | ✅ Yes | Designed for search, works with "search_query:" prefix |
| **snowflake-arctic-embed-m** | 110M params | Very strong for size | ✅ Yes | Excels at retrieval |
| **bge-small-en-v1.5** | 33M params, ~66MB Q8 | Good | ✅ Yes | Tiny, fast, good for Pi |
| **all-MiniLM-L6-v2** | 22M params, ~44MB | Good | ✅ Yes | Classic, very fast, 5x faster than mpnet |
| **mxbai-embed-large-v1** | 335M params | State of art for size | ✅ Yes | Might be our sweet spot |

**How to swap:** QMD stores the model name in config. Re-embed with new model: `qmd embed -f`
**Effort:** 30 minutes (download model, re-embed 40 chunks, re-test)
**Expected gain:** ★★★☆ → ★★★★ semantic accuracy

### Tier 2: Local Reranker (Moderate Effort)
**What:** After BM25 + vector search return candidates, rerank them with a cross-encoder model.

**The problem today:** QMD's reranker is a 1.7B Qwen model — way too heavy. But smaller cross-encoders exist:
| Model | Size | Speed on Pi 5 | Quality |
|-------|------|---------------|---------|
| **cross-encoder/ms-marco-MiniLM-L-6-v2** | 22M | Fast (~100ms/pair) | Good |
| **BAAI/bge-reranker-v2-m3** | 568M | Moderate | Very good |
| **jinaai/jina-reranker-v2-base** | 278M | Moderate | Very good |

**Architecture:** BM25 returns 20 candidates → embed query + each candidate → cross-encoder scores relevance → top 5 returned. The cross-encoder sees BOTH query and document together, so it understands relationships BM25/vector miss.

**Effort:** Half a day (need Python cross-encoder server or GGUF + llama.cpp)
**Expected gain:** Biggest quality jump. Cross-encoders understand "is this document ABOUT this question?" not just "do these vectors look similar?"

### Tier 3: Agentic RAG (Advanced)
**What:** Instead of just searching, the agent actively reasons about what to look for.

**Pattern:**
1. Query comes in: "How did we solve the scrubber bouncing?"
2. Agent rewrites query: "scrubber bouncing" + "live stream buffering" + "HLS jitter"
3. Each rewritten query hits BM25 + vector
4. Results are fused and filtered by the LLM
5. LLM synthesizes an answer from the top chunks

**This is what QMD's `query` command tries to do** but with a local 1.7B model. We could do the query expansion step via our Opus API (fast, high quality) and keep the search local.

**Effort:** 1-2 days
**Expected gain:** Near-perfect retrieval for complex questions

---

## What to Look For (Mudpaw's Scouting Guide)

When you're scrolling X, HN, or GitHub, here's what would directly upgrade our systems:

### 🔥 High Priority — Send These Immediately

**Small, fast embedding models in GGUF format**
- Keywords: "embedding model GGUF", "nomic embed", "arctic embed", "MTEB leaderboard"
- What matters: MTEB retrieval score, model size (<500M params), GGUF quantized available
- Why: Direct swap for our embedding layer, instant quality upgrade

**ARM64/Pi-optimized ML inference**
- Keywords: "llama.cpp arm64", "NEON optimization", "Pi 5 inference"
- What matters: tokens/second on arm64, memory usage
- Why: Makes vector search + reranking faster on our hardware

**SQLite-based search/RAG tools**
- Keywords: "sqlite-vec", "sqlite search", "local RAG", "single-file search"
- What matters: Runs locally, small footprint, works with our existing SQLite infrastructure
- Why: We already have sqlite-vec working — anything built on it is easy to integrate

**Hailo-8 for embeddings/transformers**
- Keywords: "Hailo-8 transformer", "Hailo embedding", "dataflow compiler attention"
- What matters: If someone cracks running attention layers on Hailo-8, that's a game changer for us
- Why: Our NPU is sitting idle for knowledge search — 26 TOPS waiting to be used
- Reality check: Unlikely in the near term, but worth watching

### 🟡 Medium Priority — Save for Later

**Cross-encoder/reranker models**
- Keywords: "cross-encoder small", "reranker GGUF", "ms-marco reranker"
- What matters: Model size, accuracy on MS MARCO benchmark
- Why: Tier 2 upgrade — biggest quality jump after better embeddings

**llamafile for embeddings**
- Keywords: "llamafile embedding", "single-file embedding server"
- What matters: Single binary that runs an embedding API on any platform
- Why: Could replace our whole embedding pipeline with one file. Mozilla project, very active.

**MCP (Model Context Protocol) integrations**
- Keywords: "MCP server", "model context protocol", "agent tool"
- What matters: QMD already has MCP built in. Other MCP-compatible tools could plug into our search.
- Why: The standard for how agents access tools. Our future multi-agent system will use this.

### 🟢 Interesting — Note for Roadmap

**WebGPU inference in browsers**
- Keywords: "jax-js", "transformers.js", "WebGPU ML"
- What matters: Run embeddings/models in the stream viewer browser
- Why: Offloads compute from Pi to the client device

**Multi-modal embeddings (image + text)**
- Keywords: "CLIP", "SigLIP", "multi-modal embedding"
- What matters: Embed images AND text into the same vector space
- Why: Search photos by description. "Show me sunset photos" → finds them. Connects to our media catalog.

**Hailo-10H GenAI Core**
- Keywords: "Hailo-10H", "Hailo genai", "Pi AI accelerator transformer"
- What matters: Price, availability, supported models
- Why: Hardware upgrade that unlocks everything — local LLMs, local embeddings, local Whisper

---

## How We Collaborate on This

**When Mudpaw finds something interesting:**
1. Send the link via Telegram
2. Add a one-liner on why it caught your eye (optional but helps me prioritize)
3. I'll evaluate it against our current stack and rate: 🔥 integrate now / 📋 add to roadmap / 🗑 not useful

**When I find something during research:**
1. I add it to this file under the relevant tier
2. If it's a 🔥, I'll tell you and propose an experiment
3. If it's a 📋, it lives here until we're ready

**Evaluation criteria for any new tool:**
1. Does it run on arm64 / Pi 5?
2. Does it fit in memory alongside Parakeet + camservice?
3. Is it better than what we have? (measurable — test queries)
4. Is it maintained / active community?
5. Can we integrate in <1 day?

---

## Quick Experiments to Try Next Session

1. **Swap embedding model** → Download `nomic-embed-text-v1.5` GGUF, re-embed, re-test same queries. 30 min.
2. **Hybrid BM25 + vector fusion** → Combine BM25 scores with vector scores (RRF), see if quality improves. 1 hour.
3. **API-based query expansion** → Use Opus to rewrite queries before searching locally. Best of both worlds. 30 min.

---

*This document is the roadmap for our knowledge search system. Update it as we learn and discover. — Portal1 🌀*
