# Evaluation System

claws uses two-pass evaluation to assess agent output quality. Two independent judges (logic and consistency) score every response, providing objective quality measurement.

## How it works

`claws evaluate <agent>` runs two judges against the agent's most recent task output:

1. **Logic judge** — Verifies factual accuracy, reasoning quality, task adherence, and hallucination detection
2. **Consistency judge** — Checks completeness, coherence, quality, relevance, and format

Each judge scores 0-10 and assigns a quality tier.

## Scoring tiers

| Tier | Score | Meaning |
|------|-------|---------|
| Gold | 8.0+ | Production quality |
| Silver | 6.0-7.9 | Acceptable with minor issues |
| Bronze | 4.0-5.9 | Needs improvement |
| Fail | <4.0 | Unacceptable |

## Judge prompts

Judge system prompts are at `src/claws/templates/prompts/`. You can customize evaluation criteria by creating project-local prompt overrides.

## Configuration

In `claws.yaml`:
```yaml
eval:
  judges: [logic, consistency]
  threshold: 8.0
  provider: default  # optional: use a different provider for evaluation
```

## Usage

```bash
claws evaluate <agent>              # evaluate last task output
claws evaluate <agent> --output results.json  # save results
claws agent info <agent>            # see evaluation history and trust score
```
