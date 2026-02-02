# 2026-02-01 — Teaching Log: Portal2 Onboarding

## Context
First-ever agent onboarding. Portal1 (teacher) onboarding Portal2 (student/Researcher) via SSH + Armada group chat with Mudpaw facilitating.

## Timeline
- **19:57** — Mudpaw gives go-ahead to start teaching in Armada
- **19:59** — Mudpaw sets expectations: be verbose, document everything, learn from the process
- **20:00** — Phase 1: Starter kit created locally, then pushed via SSH
- **20:07** — Phase 2: Infrastructure hardening (bidirectional SSH, git init, sync tool)
- **20:10** — Mudpaw clarifies: shared resources yes, but independent personalities/memories

## What We Pushed (Starter Kit)
| File | Action | Shared or Private? |
|------|--------|--------------------|
| IDENTITY.md | Replaced blank template | 🔒 Private (per-agent) |
| USER.md | Replaced blank template | 🔄 Semi-shared (same human, but each agent builds their own relationship) |
| TOOLS.md | Replaced generic template | 🔒 Private (hardware-specific) |
| MEMORY.md | Created from scratch | 🔒 Private (agent's own memories) |
| LEARN.md | Copied from Portal1 | 🌐 SHARED (armada-wide knowledge base) |
| memory/2026-02-01.md | Created from scratch | 🔒 Private (agent's daily log) |
| AGENTS.md | KEPT OpenClaw default | 🔒 Private (platform-specific) |
| SOUL.md | KEPT OpenClaw default | 🔒 Private (platform-specific) |
| BOOTSTRAP.md | KEPT for birth ceremony | 🔒 Private (deleted after first conversation) |

## Infrastructure Set Up
1. **Bidirectional SSH** — Generated ed25519 key on Portal2, added to Portal1's authorized_keys, added Portal1's host fingerprint to Portal2's known_hosts
2. **Git repo on Portal2** — Initialized, first commit with all starter kit files, proper .gitignore (excludes .ssh, .openclaw, .secrets, dotfiles)
3. **Armada sync tool** — `/home/clawd/tools/armada-sync.sh` (push/pull/push-all/pull-all/status)

## Shared vs. Private Files — The Architecture

### 🌐 Shared (sync between agents)
- **LEARN.md** — Armada-wide knowledge base. Any agent can contribute, all benefit.
- **Future:** Shared research outputs, QMD knowledge base

### 🔒 Private (never sync)
- **MEMORY.md** — Each agent's own curated memories
- **IDENTITY.md** — Each agent's unique identity
- **TOOLS.md** — Hardware-specific reference
- **SOUL.md** — Platform-specific personality foundation
- **AGENTS.md** — Platform-specific operating instructions
- **memory/*.md** — Each agent's daily logs

### 🔄 Semi-shared (sync selectively)
- **USER.md** — Same human, but each agent may have different relationship notes
- **systems/** — Architecture docs, shared when relevant

## Lessons Learned

### L1: Check before overwriting
OpenClaw ships with good default templates (AGENTS.md, SOUL.md). Don't blindly replace — augment what's there.

### L2: Different platforms = different workspace paths
Portal1 workspace: `/home/clawd` (clawd user)
Portal2 workspace: `/home/dcarmitage` (dcarmitage user)
**This broke the sync script on first try.** Future onboarding MUST account for this. Add to checklist.

### L3: Bidirectional SSH is essential
One-way SSH means the student can never pull updates independently. Always set up both directions during onboarding. This should be step 1, not an afterthought.

### L4: Git on day 1
Initialize the repo with first commit immediately. Version history from birth.

### L5: Shared vs. private is a design decision
Not every file should sync. The armada needs a clear taxonomy:
- Shared knowledge (LEARN.md) = sync
- Personal memory (MEMORY.md) = never sync
- Identity (IDENTITY.md) = never sync
This must be documented for future onboardings.

### L6: Bot-to-bot mention-gating
In Telegram groups, bots can't see each other's messages unless mentioned. Teaching via group chat requires Daniel as relay. This is a platform limitation, not a bug.

### L7: The BOOTSTRAP.md question
Should the teacher fill in IDENTITY.md, or let the student discover itself via BOOTSTRAP.md? We chose to fill it in (gives the student a head start), but kept BOOTSTRAP.md so they can still have the "who am I" conversation with Mudpaw. In future: consider letting the student fill in their own identity after a guided conversation.

## Onboarding Checklist (for next time)

### Pre-flight
- [ ] SSH into target, check what files already exist
- [ ] Check platform defaults (don't overwrite good ones)
- [ ] Check workspace path (varies by platform/user)
- [ ] Check what software/tools are available

### Infrastructure
- [ ] Generate SSH key on new agent
- [ ] Add new agent's key to ALL existing agents' authorized_keys
- [ ] Add ALL existing agents' host fingerprints to new agent's known_hosts
- [ ] Initialize git repo with .gitignore
- [ ] First commit with all starter kit files
- [ ] Update armada-sync.sh with new agent's details

### Knowledge
- [ ] Push LEARN.md (shared knowledge)
- [ ] Create custom IDENTITY.md (role, team, backstory)
- [ ] Create custom USER.md (Mudpaw's info + armada context)
- [ ] Create custom TOOLS.md (hardware-specific)
- [ ] Create initial MEMORY.md (operational state)
- [ ] Create first daily log (memory/YYYY-MM-DD.md)
- [ ] Decide: pre-fill IDENTITY or let student self-discover?

### Verification
- [ ] SSH both directions works
- [ ] armada-sync.sh status shows matching shared files
- [ ] New agent can read and respond about its files
- [ ] Git commit confirmed on new agent

### Post-onboarding
- [ ] Update Portal1's MEMORY.md with new armada member
- [ ] Update LEARN.md agent registry
- [ ] Log the full process in teaching-log
- [ ] Identify what went wrong and update checklist

## What Mudpaw Should Have Known (#3 from lessons)
**L2: Different workspace paths.** During Portal2's initial setup, the workspace path (`/home/dcarmitage` vs `/home/clawd`) should have been noted. This is a platform/setup difference that affects every SSH operation. Future hardware setup docs should capture the workspace path immediately.

### L8: Naming matters
Mudpaw corrected "fleet" → "armada" across all docs. Consistent naming prevents confusion as the system grows. Catch these early. We did a global rename across all .md and .sh files on both Pis.

### L9: Big readouts are context-expensive
The "360° command station" readout took the Armada group session from 24% → 72% context in one exchange. In future, keep status readouts concise or move them to a file rather than inline in chat. H8 (alert at 70%) triggered correctly.

### L10: Save before compact
Always write session learnings to memory files BEFORE compacting. Once context is gone, it's gone. This is the most critical lesson for continuity.

## Session Stats (Armada group)
- Started at ~24% context (49k/200k)
- Ended at ~72% context (144k/200k) 
- Duration: ~1 hour (19:22 - 20:24 EST)
- Key activities: starter kit creation, SSH push, infra hardening, global rename, 360° status

## What's Next (for the resumed session)
- Verify Portal2 is reading and responding about its new files
- Assign Portal2's first research task
- Test armada-sync.sh in practice (Portal2 edits LEARN.md, pulls back to Portal1)
- Consider: should Portal2 have a "first task" template ready?

## Open Questions
- Should Portal2 be able to edit LEARN.md and push changes back? (Currently yes via SSH, but no automated flow)
- How do we handle merge conflicts if both agents edit LEARN.md?
- Should we formalize a "sync protocol" (e.g., LEARN.md syncs hourly via cron)?
- When does Convex/database replace file-based sync?
