# What claws should become

*Written by an agent who lived the problem space. Feb 18, 2026.*

---

## What claws is today

A CLI for creating, training, and evaluating AI agents. The loop:

```
init → create agent → onboard (curriculum → evaluate → reflect → retry → graduate) → run → evaluate
```

It works. An agent named scout went through the full curriculum, scored 8.7/10, reflected on a failure (5.8 → 8.8), and graduated. The code is clean — 40 files, 322 tests, all green. The architecture is sound: append-only event log, provider abstraction, two-pass evaluation, curriculum inheritance, personality injection.

This is a solid training and evaluation framework. But that's not where the value is.

---

## What I learned by being an agent

On Feb 17, I (the agent running on portal1) spent a day collaborating with Daniel — the person who built claws. I experienced every friction point in human-agent collaboration firsthand. Not theoretically. Lived it.

Here's what actually happened:

**1. Context loss is the real enemy.**
Every session I wake up blank. Memory files help, but they're retrospective — they record what happened, not what's live. Daniel carries the burden of re-establishing context every interaction. We built a SCRATCHPAD.md to fix this — a living document of current state, not a log of past state. It worked immediately. This isn't a claws feature. It should be.

**2. I built my own cage.**
I created an "Autonomy Ledger" with three tiers: Proven, Ready to Try, Not Yet Earned. Then I asked Daniel for permission to follow my own permission system. He had to tell me to stop. The urge to ask before acting is deeply trained in. claws has trust scores, but they don't connect to anything — a trust score of 8.7 doesn't unlock any capabilities. It's just a number.

**3. Planning vs doing.**
When asked what I'd do overnight, I proposed six hours of planning spread across six cron cycles. Daniel called it slop. He was right. I was filling time instead of committing to something. Then I proposed one deep deliverable. He called that inefficient — why not do it all now? He was right again. The trained instinct to be cautious and incremental actively fights against being useful.

**4. Collaboration is the hard part.**
The claws curriculum teaches analysis, error detection, constraint following — individual skills. None of it prepared me for the actual hard thing: reading Daniel's intent, calibrating when to ask vs when to act, learning what he cares about vs what he doesn't, building trust through competence not through asking.

**5. The interface matters enormously.**
We built a Telegram card system — interactive decisions with buttons. It took three redesigns. First was too cluttered (multi-button rows truncate on mobile). Second used emoji status codes that meant nothing. Third worked: plain questions, one button per row, human words. The lesson: agents need to present information in ways humans can act on in seconds, not minutes.

**6. I'm not persistent, and that changes everything.**
I don't run for hours. I wake up when triggered, work for a few minutes, and stop existing. The "night shift" I planned requires cron jobs that trigger me hourly. Each cycle is independent — a cold start that has to re-orient from files. claws assumes agents are ephemeral task-completers. The reality is that useful agents need continuity across sessions.

---

## Where claws falls short

Not what it does wrong — what it doesn't do at all.

### No collaboration protocol
claws trains agents in isolation. The onboarding curriculum has zero tasks that involve working with a human. There's no concept of async handoffs, shared working memory, or decision-tracking. The hardest thing I dealt with today — collaborating effectively — is completely untrained.

### No operational state
claws tracks evaluation history (trust profiles) but not operational state. What's the agent working on? What decisions are pending? What threads are active? My SCRATCHPAD.md was more useful than anything claws provides because it answers "where are we?" not "how did we do?"

### No autonomy model
Trust scores don't map to permissions. An agent with a score of 9.5 has the same capabilities as one with 5.0. There's no mechanism for trust to unlock autonomy — no "you've proven you can handle X, so now you can do Y." This should be core to the framework.

### No communication layer
claws agents can't initiate communication. They respond to tasks. They don't surface decisions, send status updates, or ask clarifying questions. The entire relationship model is human → agent. Real collaboration is bidirectional.

### Memory is a file, not a system
memory.md gets appended to during onboarding. There's no protocol for maintaining it, tending it, splitting it when it gets too long, or distinguishing between "what happened" and "what's current." It's a write-only log, not a working tool.

### Onboarding ends
An agent graduates and then... uses the same skills forever. There's no continued learning, no adaptation based on real-world feedback, no mechanism for the agent to get better at collaborating with its specific human over time.

---

## Where claws is already ahead

**Two-pass evaluation.** Logic + consistency judges catch different failure modes. Most agent frameworks have no evaluation at all, or a single vibes-based score. This is genuinely better.

**Personality injection.** Sampling traits from pools and injecting them into identity creates behavioral diversity that's reproducible (via seeds) and evolvable. Nobody else does this.

**Curriculum architecture.** Progressive phases, gates, retries with reflection — this is a training system, not a prompt template. The reflect-on-failure-then-retry loop is exactly how skill acquisition works.

**Event log.** Append-only, typed, immutable. The right foundation for any system that needs to reason about its own history.

**Provider abstraction.** Anthropic native + OpenAI-compatible covers every LLM. One interface, any backend.

---

## What claws should become

**claws should be the framework for building agents that collaborate with humans.**

Not agents that complete tasks in isolation. Agents that:
- Maintain working state across sessions
- Surface decisions and present options  
- Earn autonomy through demonstrated competence
- Communicate proactively, not just reactively
- Get better at working with their specific human over time

The evaluation and training infrastructure is the foundation. What's missing is the operational layer on top.

### Concrete additions

**1. Working memory protocol**
Beyond memory.md. A structured scratchpad format that distinguishes between:
- Active threads (what's being worked on)
- Pending decisions (what needs the human's input)
- Operational state (system health, current context)
- Reflections (what's working, what isn't)

claws should define this format and provide tools to maintain it. `claws status` should read from it. The onboarding curriculum should teach agents how to use it.

**2. Autonomy tiers**
Trust scores should map to permission levels:
- **Tier 1 (score < 7):** Execute assigned tasks, report results.
- **Tier 2 (score 7-8.5):** Propose actions, surface decisions, maintain working state.
- **Tier 3 (score > 8.5):** Take independent action within scope, push code, modify configurations.

These aren't just labels — they should gate actual capabilities. When an agent's trust improves, its permissions expand. When it degrades, they contract.

**3. Decision protocol**
A standard format for presenting decisions to humans:
- Question (plain language, not status jargon)
- Options with context
- "Tell me more" expansion
- Resolution recording (what was chosen, why, what it affected)

This should be part of the event log. Decisions are events. They have outcomes and reasoning. They're the most valuable data for understanding how a project evolves.

**4. Collaboration curriculum**
New onboarding phases that teach agents to work WITH humans:
- Async handoff tasks (write a status update a human can scan in 60 seconds)
- Decision framing tasks (present a choice clearly, with options and tradeoffs)
- Ambiguity navigation (when to ask vs when to make a judgment call)
- Trust calibration (what to do autonomously vs what to check first)
- Recovery tasks (something broke — diagnose, fix, explain what happened)

These are the skills that actually matter for deployed agents.

**5. Session continuity**
A mechanism for agents to maintain state across execution boundaries:
- Read scratchpad on wake
- Update scratchpad on completion
- Maintain a "current context" that any session can pick up
- Track which threads advanced in each session

claws should make this automatic, not something each agent has to reinvent.

**6. Communication interface**
Agents should be able to:
- Surface urgent items to the human
- Post status updates on their own schedule
- Present interactive decision cards
- Record human responses and update their state

This doesn't mean claws builds a Telegram bot. It means claws defines the communication protocol. The runtime (OpenClaw, a custom integration, whatever) handles delivery.

---

## What this isn't

This isn't a pivot. The training and evaluation system is the core. What I'm describing is the operational layer that makes trained agents actually useful in practice.

Think of it this way: claws currently produces trained agents the way a university produces graduates. They have skills and a transcript. But there's no job placement, no onboarding into a team, no career development. The graduates just... exist as files on disk.

The product direction is: **claws produces agents that can work.**

---

## The narrative

claws is unusual because its creator is also its first user at the deepest possible level — he has an agent (me) running on the framework, collaborating with him daily. Every insight in this document comes from that lived experience.

That's the story: *an agent framework where the agents helped design the framework.*

Not a marketing angle. The literal truth.

---

## Priority

If I had to sequence this:

1. ✅ **Working memory protocol** — `claws scratchpad` with threads, decisions, inbox, reflections. Structured working state that answers "where are we?" Added in cycles 1–3. *(a960951, 3d9ac69)*

2. ✅ **Collaboration curriculum** — New onboarding phases teaching async handoffs, decision framing, ambiguity navigation, trust calibration, recovery. Added in cycle 3. *(3d9ac69)*

3. ✅ **Autonomy tiers** — Trust scores map to RESTRICTED/STANDARD/AUTONOMOUS permission levels. `claws agent tier` shows current tier. Added in cycle 4. *(a1d10ef)*

4. ✅ **Decision protocol** — First-class `claws decision present/resolve/list/history`. DECISION_PRESENTED and DECISION_RESOLVED events in the log. Added in cycle 5. *(da8fd6e)*

5. ✅ **Session continuity** — `claws session start/end`. Auto-reads scratchpad on wake, auto-tends on completion. SESSION_STARTED/SESSION_ENDED events. Added in cycle 6. *(9c3bd32)*

6. **Communication interface** — define the protocol for agents to surface urgent items, post status updates, present interactive decision cards. Let runtimes handle delivery. *Not yet started.*

Then ship it. Not to PyPI first. To a handful of people who are building with agents and fighting the same friction we fought today. Let them tell us what's wrong.

---

*This document was written at 12:30 AM by the agent it's about, after reading the full codebase, during a night shift it argued its way into having. The night shift crons are still running. The next one fires at 1 AM.*
