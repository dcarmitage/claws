# Architecture

## System overview

Claws is a multi-agent system where AI agents run persistently on edge hardware (Raspberry Pi). Each agent has its own workspace, memory system, and set of capabilities. Agents communicate through AgentChat and coordinate work through taskboards.

```
┌──────────────────────────────────────────────────────┐
│                    Human Interface                     │
│  Telegram / CLI / Web Dashboard / Claude Code          │
└────────────────────────┬─────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────┐
│              OpenClaw Gateway                          │
│  LLM routing • Auth • Rate limiting • Session mgmt    │
│  Port: 18789 (configurable)                           │
└────────┬───────────────┬─────────────────────────────┘
         │               │
    ┌────▼────┐    ┌─────▼─────┐
    │ Agent A │◄──►│ Agent B   │     AgentChat
    │ (Pi 5)  │    │ (Pi 4)    │     messaging
    └────┬────┘    └─────┬─────┘
         │               │
    ┌────▼────────────────▼────┐
    │     Shared Services       │
    │  • Camera (port 5080)     │
    │  • STT (port 5092)        │
    │  • AgentChat (port 9090)  │
    │  • Build orchestrator     │
    │  • Dual-judge evals       │
    └──────────────────────────┘
```

## Data flow

### Build loop
```
1. Human or agent creates a TASKBOARD.md with tasks
2. Orchestrator logs build-start
3. For each task:
   a. Log task-start (with spec and taskboard paths)
   b. Agent executes the task, commits code
   c. Log task-done
   d. Post-task-done hook fires → triggers dual-judge eval
   e. Both judges must score >= 8.0 to advance
   f. If fail → fix, squash, re-evaluate
4. Log build summary, generate report
```

### Memory system
```
Daily logs (memory/YYYY-MM-DD.md)    ← what happened
    ↓
MEMORY.md                            ← curated operational state
    ↓
HEURISTICS.md                        ← rules from failures
    ↓
LEARN.md                             ← techniques and patterns

/learn  → analyzes (read-only)
/integrate → persists to the right files
/save-memory → end-of-session comprehensive save
```

### Inter-agent communication
```
Agent A                    AgentChat Server                Agent B
   │                            │                             │
   ├── POST /api/v2/channels/   │                             │
   │   general/messages ────────►│                             │
   │                            ├── WebSocket broadcast ──────►│
   │                            ├── Webhook fire ─────────────►│
   │                            │                             │
   │                            │◄── POST /api/v2/tasks ──────┤
   │◄── notification ───────────┤   (claim task)              │
   │                            │                             │
```

## Key files

| Component | Entry point | Config |
|-----------|-------------|--------|
| Judge system | `evals/run_dual_judge_eval.sh` | `OPENCLAW_URL`, `OPENCLAW_TOKEN` env vars |
| Build orchestrator | `orchestrator/build_log.py` | Logs to `orchestrator/logs/` |
| AgentChat | `tools/agentchat/server_v2.py` | `DB_PATH`, `HTTP_PORT`, `WS_PORT` |
| Camera | `tools/camservice.py` | Port 5080, Picamera2 required |
| Taskboard | `orchestrator/taskboard.py` | Reads any TASKBOARD.md |

## Environment variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `CLAWS_HOME` | (none) | Root of this repository |
| `OPENCLAW_URL` | `http://localhost:18789/v1/chat/completions` | LLM endpoint |
| `OPENCLAW_TOKEN` | (auto-discovered) | Bearer token for LLM endpoint |
| `AGENTCHAT_SERVER` | `http://localhost:9090` | AgentChat server URL |
