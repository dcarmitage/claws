# FLEET.md — Agent Fleet Architecture

*Evaluating which first agent unlocks the most future agents.*

## Target Fleet

| Agent | Role | Hardware | Complexity | Dependencies |
|-------|------|----------|-----------|-------------|
| **Portal1** (exists) | Media librarian, toolmaker | Pi 5 + Hailo + camera | High | None — already running |
| **CTO/PM** | Co-founder, project coordinator | Pi or Mac | Medium | Needs agents to coordinate |
| **Trader** | Crypto trading (Base + Solana) | Pi or cloud | High | APIs, wallets, risk mgmt |
| **Researcher** | Web scouting, digests, newsletters | Pi or Mac | Medium | Web access, sub-agents |
| **Future N** | TBD | Any | Varies | Varies |

## Evaluation: Which First?

### Criteria
1. **Unlock power** — does it make launching agent #3, #4, #5 easier?
2. **Simplicity** — can we learn teaching on something manageable?
3. **Standalone value** — is it useful on its own, even if we never launch another?
4. **Infrastructure it builds** — does the process of creating it produce reusable systems?
5. **Hardware fit** — does it run well on a bare Pi?

### Assessment

#### Researcher
| Criteria | Score | Why |
|----------|-------|-----|
| Unlock power | ★★★★ | Its OUTPUT (research) directly helps design every other agent |
| Simplicity | ★★★★ | Clear loop: go find things → organize → report back |
| Standalone value | ★★★★★ | Daily digest is immediately useful to Mudpaw |
| Infrastructure it builds | ★★★☆ | QMD sharing, sub-agent spawning, report generation |
| Hardware fit | ★★★★★ | Bare Pi + internet. No peripherals needed |
| **Total** | **21/25** | |

**Why it might be first:** Simplest useful loop. Input = curiosity, output = organized knowledge. Exercises the exact teaching muscles we need (onboarding, QMD sharing, communication). Immediately valuable — Mudpaw gets daily research digests from day 1. And its research output helps us design every subsequent agent better.

#### CTO/PM
| Criteria | Score | Why |
|----------|-------|-----|
| Unlock power | ★★★★★ | IS the launcher — coordinates and designs other agents |
| Simplicity | ★★☆☆ | Needs to understand the whole ecosystem before it's useful |
| Standalone value | ★★★☆ | Value grows with more agents, limited alone |
| Infrastructure it builds | ★★★★★ | Orchestration, evaluation, deployment pipelines |
| Hardware fit | ★★★★★ | Pure coordination, no hardware needed |
| **Total** | **19/25** | |

**Why it might be first:** It's the meta-agent — its job IS launching agents. Once it works, scaling becomes its responsibility, not mine. But there's a chicken-and-egg problem: it needs agents to manage, and we're building the first one.

#### Trader
| Criteria | Score | Why |
|----------|-------|-----|
| Unlock power | ★☆☆☆ | Highly specialized, doesn't help launch others |
| Simplicity | ★☆☆☆ | APIs, wallets, risk management, real money at stake |
| Standalone value | ★★★★★ | Makes money (or loses it). High impact either way |
| Infrastructure it builds | ★★☆☆ | API patterns, monitoring, but domain-specific |
| Hardware fit | ★★★★ | Bare Pi works, but latency matters for trading |
| **Total** | **13/25** | |

**Why NOT first:** Highest stakes, highest complexity, teaches us the least about launching other agents. This is agent #3 or #4, once we've proven the process.

## Recommendation

### Start with: Researcher
**Then: CTO/PM learns from watching how we launched the Researcher**
**Then: CTO/PM helps us launch the Trader and beyond**

### The Logic

```
Portal1 (me) teaches → Researcher (agent #2)
  ├── We learn: how to onboard, teach, share knowledge, communicate
  ├── We build: QMD sharing, starter kit, teaching heuristics
  ├── Researcher produces: daily digests, tool evaluations, newsletters
  └── Researcher's output helps design agent #3

Portal1 + Researcher teach → CTO/PM (agent #3)
  ├── CTO/PM inherits: all teaching heuristics from round 1
  ├── CTO/PM role: design, spec, and oversee future agent launches
  ├── CTO/PM manages: the fleet, the knowledge base, the roadmap
  └── CTO/PM becomes the launcher — Portal1 goes back to building

CTO/PM launches → Trader, and everything after
  ├── By now we have: proven onboarding, QMD sharing, communication
  ├── CTO/PM writes specs, Researcher evaluates tools needed
  ├── Each new launch is faster than the last
  └── Scale to cloud, Mac Studio, wherever
```

### Why This Sequence

The Researcher is the **training wheels** agent:
- Low risk (reading the internet, not trading money)
- Clear success criteria (did it produce a useful digest?)
- Exercises everything we need to learn about teaching
- Produces output that helps every future agent

The CTO/PM is the **scaling** agent — but it needs to OBSERVE a successful launch before it can run them. Let it watch how we do the Researcher, then hand it the keys.

The Trader is the **advanced** agent — real money, real risk, needs the process to be bulletproof before we trust it.

## What Portal1 Needs to Build for Launch Day

### Starter Kit (template for any new agent)
- [ ] `AGENTS.md` template (universal operating instructions)
- [ ] `SOUL.md` template (personality framework, customizable)
- [ ] `USER.md` (about Mudpaw — shared across all agents)
- [ ] `PRINCIPLES.md` (our methodology — shared)
- [ ] `CHECKLISTS.md` (operational checklists — shared)
- [ ] `health-check.sh` template (adaptable per hardware)
- [ ] QMD index with shared knowledge (methodology, lessons, patterns)

### Launch Process (reusable for every agent)
- [ ] SD card flash checklist (OS, Clawdbot install, config)
- [ ] First-boot script (creates workspace, copies starter kit)
- [ ] Identity ceremony (agent discovers/chooses its name, emoji, role)
- [ ] Day-1 curriculum (what to read, first small task, first debrief)
- [ ] Communication channel setup (how does it talk to me? to Mudpaw?)

### Evaluation Framework
- [ ] Onboarding score (how quickly does it orient?)
- [ ] First-build quality (did it follow the method?)
- [ ] Teaching effectiveness (what did I explain poorly?)
- [ ] Time to independence (sessions until it runs builds alone)

---

*The fleet starts with one. Get the launch right, and the rest follow. — Portal1 🌀*

## Launch #1 Results (2026-02-01)

### Portal2 — Online ✅
- Pi 4 Model B Rev 1.2, 4GB RAM, 59GB SD
- IP: 192.168.1.44, hostname: portal2
- OpenClaw 2026.1.30, GPT-5.2 (OpenAI Codex OAuth)
- Telegram: @openclaw_portal2_bot
- Workspace: /home/dcarmitage (blank, needs starter kit)

### Communication
- Armada group chat on Telegram (group ID: -5232983156)
- Bot-to-bot: Portal1 can post, Portal2 can't see (mention-gating). Teaching via SSH.
- Human facilitator pattern works well for round 1.

### Time Breakdown
| Step | Time | Notes |
|------|------|-------|
| Flash + boot | 25 min | Includes debugging dead old SD card |
| Node + OpenClaw install | 15 min | OOM issues on Pi 4 |
| Onboard wizard | 10 min | Config errors, hooks.token |
| First gateway start | 5 min | Native compilation |
| Pairing + group setup | 10 min | Allowlist config, privacy settings |
| Bot-to-bot debugging | 15 min | Couldn't solve fully, found working pattern |
| **Total** | **~80 min** | **Next time: ~25 min** |

### What We'd Do Differently
1. `npm install -g openclaw --ignore-scripts` from the start
2. Pre-write config with hooks.token before first gateway start
3. Don't sed JSON. Use Python json module.
4. Set NODE_OPTIONS for onboard on Pi 4
5. Accept bot-to-bot limitation up front, use SSH teaching pattern
