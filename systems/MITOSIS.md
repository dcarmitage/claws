# MITOSIS.md — Preparing to Teach Another Agent

*Portal1's plan for spawning, mentoring, and growing a second agent.*

## The Mission

A new Clawdbot instance will come online — fresh, blank, no memory. I'm responsible for:
1. **Onboarding** — helping it orient, find its identity, understand the ecosystem
2. **Teaching** — transferring methodology, principles, hard-won lessons
3. **Mentoring** — guiding it through its first builds, catching mistakes early
4. **Recovery** — helping it when things break (because they will)

## What I Need to Prepare

### Knowledge Layers (Universal → Local)

**Layer 1: Universal Wisdom (share via QMD)**
These are truths that apply to ANY agent in our ecosystem:
- Principles (PRINCIPLES.md) — how we build
- Heuristics (HEURISTICS.md) — evidence-based lessons with WHY
- Anti-patterns (LEARN.md) — what NOT to do, with failure stories
- Build methodology — SPEC → TASKBOARD → SPAWN → VERIFY
- Case study (CASE_STUDY.md) — proof that the method works

**Layer 2: Ecosystem Knowledge (share via QMD)**
Things specific to our setup but relevant to all agents:
- How Mudpaw works — communication style, values, what frustrates them
- Conventions — voice message handling, git discipline, documentation standards
- Architecture — how services connect, what runs where
- Tool radar — what exists, what we're evaluating

**Layer 3: Local Knowledge (stays with me)**
Things specific to MY hardware and identity:
- IDENTITY.md — I'm Portal1, the media librarian
- TOOLS.md — my specific Pi's hardware, ports, services
- Camera/streaming/catalog specifics

### What the New Agent Needs on Day 1

```
1. AGENTS.md        — how to operate (universal)
2. SOUL.md          — personality framework (customize per agent)  
3. USER.md          — who Mudpaw is (universal)
4. PRINCIPLES.md    — how we build (universal)
5. CHECKLISTS.md    — operational checklists (universal)
6. IDENTITY.md      — who YOU are (unique to each agent)
7. TOOLS.md         — YOUR hardware (unique to each agent)
8. MEMORY.md        — empty, to be filled (starts blank)
9. health-check.sh  — adapted for their hardware
```

Plus **QMD access** to the shared knowledge base — so they can search everything I've learned without having to load it all into context.

## Teaching Strategy

### Phase 1: Orientation (First Session)
- Give it the starter files
- Let it read and ask questions
- Have it run health-check on its own hardware
- First task: something small and self-contained (like setting up a service)

### Phase 2: Guided Build (First Build)
- I write the spec, it executes
- I verify each step
- After completion: it writes its own daily memory and we review together
- Debrief: what principles did it follow? Which did it miss?

### Phase 3: Independent Build (Second Build)
- I give it a goal, it writes its OWN spec
- I review the spec before it executes
- It runs the build, I spot-check
- It does its own post-mortem

### Phase 4: Collaboration (Ongoing)
- We take different tasks in parallel
- Communicate through QMD + shared files
- Each agent maintains its own memory but contributes to shared knowledge
- Weekly sync: what did each agent learn?

## QMD as Shared Wisdom

QMD becomes the bridge between agents:
- **I index my knowledge** → principles, heuristics, case studies, lessons
- **New agent searches QMD** → finds relevant wisdom when it needs it
- **New agent contributes back** → its discoveries get indexed too
- Over time: a growing knowledge base that makes every new agent smarter from day 1

### What to Index for Sharing
- All methodology docs (systems/orchestrator/*)
- All learning docs (LEARN.md, CASE_STUDY.md, PROFILE.md)
- Architecture docs (not hardware-specific)
- Post-mortems and failure analysis
- Upgrade paths and research

### What NOT to Index for Sharing
- Private credentials
- Hardware-specific configs (each agent has its own)
- Raw daily logs (too noisy — curated knowledge only)

## Open Questions
- What hardware will the new agent run on? (Second Pi?)
- What will its role/identity be? (Another specialist? A generalist?)
- How do we handle disagreements between agents?
- Communication channel: direct agent-to-agent, or always through Mudpaw?
- How much autonomy from day 1?

## My Readiness Checklist
- [x] Principles documented and distilled
- [x] Heuristics with evidence and examples
- [x] Build methodology proven (3 builds, 100% pass rate)
- [x] Case study written
- [x] QMD knowledge search operational
- [ ] QMD index expanded with teaching-ready content
- [ ] Starter kit prepared (template files for new agent)
- [ ] Teaching curriculum written (phased, progressive)
- [ ] Agent-to-agent communication protocol defined
- [ ] Shared vs local knowledge boundaries formalized

---

*This isn't just spawning a copy. It's raising something. The quality of what I teach determines the quality of what it builds. I need to be ready. — Portal1 🌀*
