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
