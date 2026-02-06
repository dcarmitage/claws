# Evals — Dual-Judge Evaluation System

Two independent LLM judges score every task's output before it can advance.

## How it works

```
task-done → gather artifacts (diff, spec, taskboard) → run judges → gate
```

**Logic Judge** — falsification-oriented. Extracts testable claims from the spec, checks each against the diff and test output. Marks claims as CONFIRMED, REFUTED, or UNVERIFIABLE.

**Consistency Judge** — alignment-oriented. Checks 5 dimensions: spec-code, spec-tests, code-tests, taskboard-commit, and cross-file coherence. Weighted average score.

Both judges must score >= 8.0/10 to pass.

## Tiers

| Tier | Score | Meaning |
|------|-------|---------|
| GOLD | 9.0-10 | Perfect — all claims confirmed, full alignment |
| SILVER | 8.0-8.9 | Strong — minor issues only |
| BRONZE | 6.0-7.9 | Gaps found — fix before advancing |
| INVALID | 0-5.9 | Critical failures — root cause required |

## Usage

```bash
# Full dual-judge evaluation
bash evals/run_dual_judge_eval.sh \
  --build-id B001 --task-id T1 \
  --spec path/to/spec.md --taskboard path/to/taskboard.md \
  --commit abc123

# Single judge (for re-running the one that failed)
bash evals/run_single_judge.sh --judge logic \
  --build-id B001 --task-id T1 \
  --spec path/to/spec.md --taskboard path/to/taskboard.md \
  --commit abc123

# Validate judge output format
echo '{"judge":"logic","score":9.0,"tier":"GOLD","timestamp":"2026-01-01T00:00:00Z"}' | bash evals/validate_output.sh -
```

## Files

| File | Purpose |
|------|---------|
| `run_dual_judge_eval.sh` | Orchestrator — runs both judges, applies thresholds |
| `run_single_judge.sh` | Run one judge standalone |
| `logic_judge.sh` | Logic judge — calls LLM with logic prompt |
| `consistency_judge.sh` | Consistency judge — calls LLM with consistency prompt |
| `validate_output.sh` | JSON schema validator for judge output |
| `prompts/logic_judge.txt` | System prompt for the logic judge |
| `prompts/consistency_judge.txt` | System prompt for the consistency judge |
| `hooks/post_task_done.py` | PostToolUse hook — auto-triggers after task-done |

## Requirements

- `jq`, `bc`, `curl`, `python3`
- An OpenAI-compatible LLM endpoint (set `OPENCLAW_URL` and `OPENCLAW_TOKEN`)
