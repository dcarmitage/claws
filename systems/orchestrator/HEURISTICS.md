# Orchestrator Heuristics

*Living document. Updated as we learn. These are the rules that make builds reliable.*

## Decision Principles

**Use maximum intelligence, optimize later.** We are not cost-sensitive at this stage. Use Opus everywhere. The goal is to build right and learn fast. Model swapping is a future optimization after we understand the quality floor.

**Capture the what, the why, and how to improve.** Every build should produce three outputs:
1. Working code (the what)
2. Build logs + case study entries (the why)
3. Updated heuristics and evals (how to improve)

If a build only produces code, it was incomplete.

---

## Build Heuristics

### H1: The Scope Rule
**If you can't write the exact code in the brief, the task is too big.**

Tasks with exact code in the brief: 100% first-pass success, avg 25s.
Tasks with vague descriptions: require interpretation, sometimes need rework.

*Action: When writing a task brief, include the actual code to write. If you can't, either split the task or do a research/exploration task first to determine the code.*

### H2: The Verification Gap
**Automated checks are necessary but not sufficient.**

Three times today, code passed all automated checks but failed visual inspection. `ast.parse` catches syntax; `curl` catches endpoints; neither catches "the scrubber bounces around."

*Action: For anything with a visual/interactive component, require human verification OR screenshot-based review before marking done. Build visual QA into the eval system.*

### H3: The Context Cliff
**Quality degrades nonlinearly. Spawn fresh early, not late.**

Context corruption doesn't degrade gradually — it hits a cliff (coherent → `$0 $1` garbage). The sub-agent doing 6 tasks didn't fail on task 1; it failed on the cumulative weight.

*Action: One task per sub-agent, always. If the main session has been running heavy tool calls for a while, compact or spawn a coordinator sub-agent before continuing. The cost of a new session is trivial compared to debugging corrupted output.*

### H4: The Dependency Principle
**Sequence by data flow, not by perceived importance.**

Server endpoints → time display → mic icon → audio hint → scrubber. Each task's output was the next task's input. The bulk approach failed because tasks stepped on each other.

*Action: Before building, map which tasks produce data/structure that others consume. Draw the dependency graph. Build producers before consumers.*

### H5: The Dogfood Rule
**Use the system to build the system.**

The orchestrator logged its own build. This immediately surfaced real issues and proved the tool works on real data. The first user of any tool should be us.

*Action: When building a tool, use it as soon as the first functional piece exists. If using it feels wrong, that's the most valuable signal you'll get.*

### H6: The Three-Output Rule
**Every build produces: code, documentation, and learning.**

Code alone is incomplete. We need:
- **Code:** Working, committed, tagged
- **Documentation:** Build log (what happened), case study entries (why), updated specs
- **Learning:** Updated heuristics, new anti-patterns, refined templates

*Action: After every build, run `build_report.py`, update CASE_STUDY.md, sync to LEARN.md. Git snapshot everything.*

### H7: The Archive Principle
**Git snapshots at every meaningful state. Rollback is a superpower.**

Every task gets a commit. Every build gets a tag. This isn't overhead — it's the safety net that lets us be bold. Rolling back one task is trivial. Rolling back an entire session of uncommitted changes is a nightmare.

*Action: `git commit` after every verified task. `git tag` after every completed build. `git reset --hard` when something goes wrong (we did this today and it saved us).*

---

## Testing & Eval Heuristics

### E1: Layered Validation
Every task should have three layers of validation:

| Layer | What It Catches | How | Speed |
|-------|----------------|-----|-------|
| **Syntax** | Parse errors, typos | `ast.parse`, linters | Instant |
| **Functional** | Wrong behavior, missing features | Endpoint tests, feature greps | Seconds |
| **Experiential** | UX problems, visual bugs, "feel" | Human review, screenshots | Minutes |

Most of our failures were at Layer 3. Don't skip it.

### E2: Eval the Evals
Our testing system itself needs evaluation. Track:
- **False positives:** Tests pass but output is wrong (our biggest problem today)
- **False negatives:** Tests fail but output is actually fine (not yet observed)
- **Coverage:** What percentage of actual issues would our tests catch?

After each build, ask: "What bug did we find that our tests DIDN'T catch?" Add a test for it.

### E3: Regression Tests
When we fix a bug, the fix itself becomes a test:
- Fixed ALSA `hw:0,0` → test: grep for `plughw` not `hw:0,0`
- Fixed `v.muted` blocking analyser → test: grep for `GainNode`
- Fixed manual HLS seek → test: grep for `liveSyncDurationCount`

These are cheap (just greps) and prevent regression.

### E4: Judge After Verify
**Every task gets dual-judge evaluation after tests pass.**

Automated tests catch syntax and functional errors. Judges catch semantic drift — does the code actually fulfill the spec's intent? Tests passing is necessary but not sufficient. The dual-judge gate catches what tests miss: scope creep, spec misalignment, cross-file inconsistency.

*Action: After `task-done` with tests passing, run `bash evals/run_dual_judge_eval.sh` before advancing to the next task. Both judges must score >= 8.0. No exceptions without documented root cause.*

### E5: Judge Scores are Data
**Track judge score trends. Investigate declines.**

Individual scores matter less than trends. A task scoring 7.5 once is a data point. Three tasks in a row scoring 7.5 is a signal. Declining consistency scores across a build usually mean the spec drifted from reality as implementation progressed.

*Action: After each build, review judge scores in `build_report.py metrics`. If average scores decline session-over-session, investigate before the next build. Common causes: stale specs, scope creep, context degradation (H3).*

### E6: Failed Judges Require Root Cause
**Never skip a judge failure without analysis.**

A judge scoring < 8.0 is not a nuisance to retry — it's a signal that something is wrong. The fix is not "run the judge again" or "override the threshold." The fix is understanding why the score was low and addressing the root cause.

*Action: When a judge fails:*
1. *Read the full judge output (saved in `evals/results/`)*
2. *Identify which claims were REFUTED or which checks were misaligned*
3. *Fix the underlying issue (code, spec, or test)*
4. *Re-run the judge to confirm the fix*
5. *Log the root cause in daily memory*

---

## Improvement Tracking

### What We Don't Test Yet (Known Gaps)
- [ ] Visual rendering of the stream viewer
- [ ] Audio actually playing through the Web Audio pipeline
- [ ] HLS playback smoothness (can only verify with live viewing)
- [ ] Mobile touch interactions (tap, double-tap, scrub)
- [ ] Error recovery (what happens when ffmpeg dies mid-stream?)

### Improvement Ideas (Not Yet Implemented)
- [ ] Screenshot capture after UI tasks → send to chat for review
- [ ] Failure protocol in taskboard (retry count, fallback strategy)
- [ ] "Lessons learned" field in build logs (why, not just what)
- [ ] Automatic regression test generation from fixed bugs
- [ ] Build-over-build trend analysis (are we getting faster? more reliable?)

---

## Meta: How to Update This Document

When you learn something new about building:
1. Check if it fits an existing heuristic — if so, add evidence/examples
2. If it's a new pattern, add a new H# or E# entry
3. If it contradicts an existing heuristic, update it with the new understanding
4. Always include the concrete evidence (what happened, what we measured)

*Last updated: 2026-02-01 — Portal1 🌀*

### H8: Monitor Your Own Context
**Quality degrades nonlinearly (H3) — and that applies to YOU, not just sub-agents.**

On 2026-02-01, the main session hit ~85% context and output degraded to token garbage (`$0 $1 $2`). The agent did not notice or warn the human. The human had to ask "how much context do you have left?" twice.

*Action: Before every tool call in a heavy session, mentally note context pressure. When approaching 70%, proactively tell the human. At 80%, recommend compacting. Don't wait to be asked — that's the whole point of H3.*

Evidence: Two corruption incidents in one session, both caught by human, not agent.

### H9: Announce Risky Operations Before Running
**If something might fail, take a long time, or consume heavy resources — tell the human FIRST.**

On 2026-02-01, ran a 1.7B LLM inference on arm64 CPU without warning. Process consumed 6.3GB RAM for 3+ minutes. Human saw SIGKILL and thought something catastrophic happened.

*Action: Before any heavy/risky operation, announce: "I'm about to try X, it might take Y, I'll abort if Z." Set explicit timeouts. Give the human a chance to say "wait" or "go ahead."*

### H10: Never Silently Kill a Process
**Always tell the human what you killed and why. Silent failures erode trust.**

Killed a stuck vsearch process and moved on without announcing it. Human discovered the SIGKILL in system messages and thought context had crashed.

*Action: When killing a process, immediately tell the human: "I killed X because Y. Here's what I'm trying instead." Transparency > speed.*

### H11: Never Claim Done Until Tested and Validated
**Code existing ≠ code working. You don't stop until the thing runs, you've tested it yourself, and you can prove it works. Never fabricate, assume, or extrapolate test results.**

On 2026-02-01, plugin files (`tools/agentchat-plugin/`) were created by a sub-agent but never installed, configured, or tested. They got swept into a `git add -A` commit alongside real documentation — implicitly presenting unverified code as completed work. When asked, the initial response was defensive ("No lies!") before actually checking.

This is a trust violation. Mudpaw cannot make decisions based on false information about what works.

*Action:*
1. *Never `git add -A` without reviewing what you're committing*
2. *Never present code as "built" unless you've run it, tested it, and confirmed it works*
3. *If you haven't tested it, say so explicitly: "I wrote the code but haven't tested it yet"*
4. *If asked "does X work?" — verify first, answer second. Never lead with a denial or affirmation before checking.*
5. *Untested code gets a clear label: `DRAFT`, `UNTESTED`, or lives in a separate branch*

Evidence: Mudpaw caught it. "that's lying. STOP EVERYTHING." Trust is the foundation. This heuristic is non-negotiable.

### H14: Strategy Council — Diverse Lenses Find Different Things
**When planning what to do next, spawn multiple independent agents with different strategic lenses and compare.**

On 2026-02-05, we ran 5 subagents in parallel (Infrastructure, Quality, Multi-Agent, Workflow, Integration) — each read the full codebase independently and predicted 5 steps forward. Results:

1. **Convergence = priority signal.** All 5 converged on the same first action (live judge-gated build loop) despite different mandates. When independent perspectives agree unprompted, that's gravity, not coincidence.
2. **Diverse lenses catch different things.** The Infrastructure agent caught 17 uncommitted files (urgent data loss risk) that every strategy-focused agent missed. Urgency ≠ importance, and no single lens sees both.
3. **The best path is a hybrid.** Cherry-pick step 1 from the top 3 paths rather than committing to one. Different paths optimize different axes — combine them.
4. **Cost is trivial, value is high.** ~300K tokens, 80 seconds wall time, genuine strategic clarity. Cheap for planning.

*Action: Before any major planning decision, run a strategy council: 3-5 subagents with different lenses (at minimum: one tactical/urgent, one strategic/visionary, one user-focused). Look for convergence (what to do) and divergence (what you'd miss with one perspective). Document the result.*

Evidence: 5/5 agents agreed on the same first action. Infrastructure agent uniquely caught data loss risk. Integration agent uniquely proposed adaptive prompt feedback. No single agent would have produced this breadth.

### H15: Simulation ≠ Production — Close the Gap Fast
**A system tested only in simulation is a prototype, not a product.**

On 2026-02-05, the dual-judge system was built and "verified working" with synthetic test cases — matching spec (9.5 GOLD) and mismatched spec (0.5 INVALID). But all 5 strategy council agents independently flagged the same gap: it has never fired in a real build session. The hook, the token discovery, the LLM response parsing, the build_log integration — all tested individually, never as a connected system under real conditions.

This is H11 (Never Claim Done Until Tested) applied recursively. The quality gate that enforces H11 on other code has not been held to its own standard.

*Action: When you build a system and verify it in simulation, the very next action should be a live end-to-end test under real conditions. Not "sometime later" — next. The longer the gap between simulation and production, the more false confidence accumulates.*

Evidence: 5/5 strategy agents independently flagged this as the top priority. Multiple bugs in the dual-judge system (LLM preamble text, process substitution, auth tokens) were only found during semi-real testing, not by reading the code.

### H12: Checkpoint After Every Milestone (was H11)
**Update BOTH daily memory AND MEMORY.md after every major milestone. Not just one.**

Daily memory is a running log (easy to append). MEMORY.md is curated operational state (requires thought). Under time pressure, the curated update gets skipped. Then the next session boots with stale MEMORY.md.

*Action: After completing a build, experiment, or significant discovery:*
1. *Append to `memory/YYYY-MM-DD.md` (what happened)*
2. *Update `MEMORY.md` (what changed about the system's state)*
3. *`git add && git commit`*

*All three. Every time. No exceptions.*

### H13: End-of-Session Hygiene (was H12)
**Before wrapping a session, run a cleanup pass.**

Untracked files accumulate silently. Uncommitted memory updates get lost. The human asks "is everything documented?" and the answer should always be yes without needing to check.

*Action: Before ending a session or compacting:*
1. *`git status` — anything untracked that matters?*
2. *`git diff` — any uncommitted changes?*
3. *Verify MEMORY.md reflects current state*
4. *Verify daily memory covers today's work*
5. *Commit and tag if appropriate*
