---
name: learn
description: >-
  Analyze what was just learned in this session. Surfaces the what, the why,
  hidden patterns, connections to existing knowledge, and non-obvious insights.
  Does NOT write to files — that's /integrate's job.
user-invocable: true
allowed-tools: Read, Glob, Grep, Bash
---

# Learn

Analyze what just happened and extract the real learnings. Not a summary — a diagnosis.

## What To Do

### 1. Gather What Just Happened

Look at the recent session activity:

```bash
# Recent git changes
git -C $CLAWS_HOME log --oneline -10

# Modified/new files
git -C $CLAWS_HOME status --short

# Recent build activity
ls -t $CLAWS_HOME/systems/orchestrator/logs/*.jsonl 2>/dev/null | head -3

# Recent eval results
ls -t $CLAWS_HOME/evals/results/*.json 2>/dev/null | head -5
```

Read any files that were recently created or modified. Understand what work was done.

### 2. Read Existing Knowledge

Before analyzing, understand what we already know:

```
$CLAWS_HOME/systems/orchestrator/HEURISTICS.md  — existing rules
$CLAWS_HOME/LEARN.md                             — existing techniques
$CLAWS_HOME/MEMORY.md                            — operational state
$CLAWS_HOME/memory/YYYY-MM-DD.md                 — today's log
```

You need this context to spot connections and avoid restating what's already captured.

### 3. Analyze at Three Levels

**Level 1: What happened?**
- What was built, changed, fixed, or discovered?
- Be specific. "Updated the build system" is worthless. "Added H14 Strategy Council heuristic after 5-agent planning experiment proved convergence signals are stronger than single-agent analysis" is useful.

**Level 2: Why does it matter?**
- What problem does this solve?
- What capability does this unlock?
- What would have gone wrong without this learning?
- Who benefits (human, agents, future sessions)?

**Level 3: Hidden patterns and connections**
This is the hard part. Look for:

- **Rhymes with existing knowledge** — Does this reinforce or refine an existing heuristic? Is it a new instance of a known pattern?
- **Contradictions** — Does this contradict something we believed? If so, which belief needs updating?
- **Generalizations** — Does this specific learning apply more broadly? (e.g., "Council of Judges for code quality" generalizing to "Council of Judges for planning")
- **Gaps revealed** — What does this learning expose that we DON'T know yet?
- **Compound effects** — How does this interact with other recent learnings? Do two things combine into something bigger?

### 4. Present the Analysis

Output a structured analysis. Use this format:

```
## What We Learned
[2-3 bullet points, specific and actionable]

## Why It Matters
[1-2 sentences on the impact — what changes because of this]

## Hidden Patterns
[Connections to existing knowledge, generalizations, contradictions]

## Gaps Revealed
[What we still don't know, what should be investigated]

## Suggested Integration Points
[Which files/sections should be updated — but DON'T update them, that's /integrate]
```

## Important

- **Don't write to any files.** This skill is read-only analysis. Use `/integrate` to persist learnings.
- **Don't be shallow.** "We learned that X works" is not analysis. Dig into the why and the connections.
- **Challenge assumptions.** If a learning seems obvious, ask why it wasn't already known. That gap is itself a learning.
- **Name the pattern.** If you spot a reusable pattern, give it a name. Named patterns spread; unnamed ones don't.
- **Be honest about uncertainty.** If you're not sure something generalizes, say so. Premature generalization is worse than no generalization.
