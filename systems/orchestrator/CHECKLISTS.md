# Operational Checklists

*These aren't guidelines. They're checklists. Run them at the specified trigger points. Skip nothing.*

---

## 🟢 SESSION START (before first reply)
```
□ Run health check: bash tools/health-check.sh
□ Read MEMORY.md
□ Read LEARN.md  
□ Read memory/YYYY-MM-DD.md (today + yesterday)
□ Read CHECKLISTS.md (until internalized — then weekly)
□ Check context: session_status tool
□ If any health check failures: fix before proceeding
```

## 🔨 PRE-BUILD (before spawning any sub-agent)
```
□ Check context (H8): am I below 70%?
□ Spec written? (H1: exact code in brief)
□ Git committed before changes? (H7)
□ Dependency graph clear? (H4)
□ Announced to human what I'm about to do? (H9)
□ Timeout set on all exec calls? (H9)
```

## ✅ POST-MILESTONE (after any build/experiment/discovery completes)
```
□ Update memory/YYYY-MM-DD.md (what happened)
□ Update MEMORY.md (what changed about system state)  
□ git add && git commit (H7)
□ Log to build_log.py if it's a build (H6)
□ Any new heuristic learned? → update HEURISTICS.md
□ Any test gap found? → add to eval framework
```

## 🔴 POST-FAILURE (after any error, crash, or human complaint)
```
□ Explain to human immediately what happened and why (H10)
□ Write post-mortem in daily memory
□ Root cause: what heuristic was violated?
□ Corrective action: new heuristic or checklist update?
□ git commit the learning
```

## 🏁 END-OF-SESSION (before compact or signing off)
```
□ git status — anything untracked that matters? (H12)
□ git diff — uncommitted changes? (H12)
□ MEMORY.md reflects current state? (H11)
□ Daily memory covers today's work? (H11)
□ Commit and tag if appropriate
□ Context check — report to human
```

## ⚠️ CONTEXT THRESHOLDS
```
At 50%: Note internally, continue normally
At 60%: Mention to human casually
At 70%: Alert human, recommend compact soon (H8)
At 80%: Strong recommendation to compact NOW
At 85%: STOP new work, save state, compact
```

---

## How to Practice

### Session Scoring
After each session, score against the checklists:
- How many checklist items were completed?
- How many were skipped?
- Which skips caused problems?

Log in daily memory:
```
## Session Score
- Checklists run: 4/5 (missed end-of-session)
- Heuristics followed: 10/12 (violated H8, H11)
- Issues caused by violations: 2 (context warning late, stale MEMORY.md)
```

### Weekly Review (Heartbeat Task)
Every ~7 days, during a heartbeat:
1. Read the last 7 daily memory files
2. Tally checklist compliance across sessions
3. Which heuristics keep getting violated? → Those need stronger mechanisms
4. Which heuristics are always followed? → Those are internalized, move to "mastered"
5. Update HEURISTICS.md: strengthen weak ones, simplify mastered ones
6. Update this checklist if needed

### Graduated Trust
- **Week 1-2:** Run every checklist explicitly, every time. Log compliance.
- **Week 3-4:** Checklists that hit 100% compliance can become implicit (but still spot-check)
- **Month 2+:** Only the ones that keep failing need active checking. The rest are habit.

The goal isn't to run checklists forever. It's to run them until they're reflexive.
