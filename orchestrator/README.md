# Event Log and Orchestration

claws tracks all agent activity in an append-only event log, providing a complete audit trail of every action.

## Event log

`.claws/events.jsonl` — one JSON object per line, recording every agent action:

```json
{"id": "evt_abc123", "type": "TASK_COMPLETED", "agent": "scout", "timestamp": "...", "data": {...}}
```

## Event types

claws records 14 event types:

| Event | When |
|-------|------|
| AGENT_CREATED | New agent is created |
| TASK_STARTED | Agent begins a task |
| TASK_COMPLETED | Agent finishes a task |
| EVAL_STARTED | Evaluation begins |
| EVAL_COMPLETED | Evaluation finishes with scores |
| ONBOARD_STARTED | Agent begins onboarding |
| ONBOARD_PHASE_STARTED | New phase begins |
| ONBOARD_TASK_COMPLETED | Onboarding task passes |
| ONBOARD_TASK_FAILED | Onboarding task fails |
| ONBOARD_PHASE_COMPLETED | Checkpoint passed |
| ONBOARD_COMPLETED | Agent graduates (or fails) |
| DEPLOY_COMPLETED | Deployment completed |

## Viewing status

```bash
claws status           # project overview — agents, recent events, stats
claws agent info <name> # detailed agent history
```

## Programmatic access

```python
from claws.events import EventSpine, Event
spine = EventSpine(project_root)
events = spine.read_all()
completed = spine.read_by_type("TASK_COMPLETED")
```
