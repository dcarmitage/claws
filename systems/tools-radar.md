# Tools Radar

*Tools we've discovered, evaluated, or plan to evaluate. Living document.*

## Active / In Use
| Tool | Purpose | Status | Notes |
|------|---------|--------|-------|
| Clawdbot | Agent runtime | ✅ Running | Gateway on port 18789 |
| Parakeet STT | Speech-to-text | ✅ Running | Port 5092, 10-20x realtime |
| CamService | Camera + streaming | ✅ Running | Port 5080, HLS + audio |
| SQLite + FTS5 | Media catalog | ✅ Running | catalog.py |

## Evaluating
| Tool | Purpose | Status | Notes |
|------|---------|--------|-------|
| QMD | Knowledge base search | 🔬 Phase 1 | Tobi Lütke. BM25 + vector + rerank, all local. Risk: arm64 sqlite-vec. |

## Radar (Future Interest)
| Tool | Purpose | Why Interesting | When |
|------|---------|----------------|------|
| jax-js | Browser-side ML | JAX in JS via WebGPU/Wasm. Could run vision models in stream viewer client-side, offloading Pi. | When we need client-side inference |
| Hailo-10H | Local LLM/transformer | GenAI Core — runs transformers unlike Hailo-8. Would enable on-device embeddings, Whisper, VLMs. | Hardware upgrade |
