---
name: judge
description: >-
  Run dual-judge evaluation (logic + consistency) on a task's commit.
  Use when evaluating whether a completed task meets spec requirements.
  Triggered automatically after task-done, or invoke manually with /judge.
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash
---

# Dual-Judge Evaluation

Run two LLM judges against a task's output to verify quality before advancing.

## Arguments

The user invoked this command with: $ARGUMENTS

Arguments can be:
- A commit SHA: `/judge a5f7dce`
- A commit SHA + spec path: `/judge a5f7dce specs/my-task.md`
- Nothing (uses HEAD): `/judge`

## What To Do

1. **Resolve the commit.** If `$ARGUMENTS` contains a SHA, use it. Otherwise use HEAD:
   ```bash
   git -C /home/clawd log --oneline -1 HEAD
   ```

2. **Find the spec.** If a spec path was given, use it. Otherwise, check:
   - Is there a spec file mentioned in recent context?
   - Check `systems/orchestrator/logs/` for the latest build's task entries
   - If no spec is found, ask the human: "Which spec file should I judge this commit against?"

3. **Find the taskboard.** Look for the most relevant one:
   - Check for `IMPLEMENTATION_PLAN.md` or `taskboard.md` in the working directory
   - If none found, create a minimal one from the commit message

4. **Get the auth token:**
   ```bash
   OPENCLAW_TOKEN=$(python3 -c "import json; print(json.load(open('/home/dcarmitage/.openclaw/openclaw.json'))['gateway']['auth']['token'])")
   ```

5. **Run both judges in parallel:**
   ```bash
   # Save diff to temp file (process substitution doesn't work reliably)
   git -C /home/clawd show <commit> --format="" > /tmp/judge_diff.txt

   OPENCLAW_TOKEN=$OPENCLAW_TOKEN bash /home/clawd/evals/logic_judge.sh \
     --spec <spec_path> \
     --diff /tmp/judge_diff.txt \
     --test-output "<any test output from the build, or describe what was verified>"

   OPENCLAW_TOKEN=$OPENCLAW_TOKEN bash /home/clawd/evals/consistency_judge.sh \
     --spec <spec_path> \
     --taskboard <taskboard_path> \
     --diff /tmp/judge_diff.txt \
     --changed-files "$(git -C /home/clawd show <commit> --name-only --format=""  | tr '\n' ',')"
   ```

6. **Present results clearly.** Use a formatted summary like:
   ```
   DUAL-JUDGE EVALUATION — Commit <sha>
   "<commit message>"

   LOGIC JUDGE:  X.X/10  (TIER)
     ✓/✗ [severity] claim text
     ...

   CONSISTENCY JUDGE:  X.X/10  (TIER)
     ✓/✗ check name: X/10
     ...

   VERDICT: PASS/FAIL (threshold: >= 8.0 both judges)
   ```

7. **If either judge fails (< 8.0):** Tell the human what failed and why. Reference E6 — failed judges require root cause analysis, not retries.

## Important

- Always save the diff to a temp file. Do NOT use bash process substitution (`<(...)`) — it doesn't reliably pass content to the scripts.
- Always set `OPENCLAW_TOKEN` from the config file.
- Present results in human-readable format, not raw JSON.
- If judges score below 8.0, the task is blocked. Don't sugarcoat it.
