# PRINCIPLES.md — Shared Team Philosophy

> These principles guide how agents build, collaborate, and maintain quality.
> All agents should read this file. Update it when lessons are learned.

---

## 1. Test-Driven Development (TDD)

**Philosophy:** Tests are not afterthoughts. They are the specification made executable.

### The Practice

1. **Write tests alongside code** — Every new feature gets tests
2. **Run tests before committing** — `./test.sh` must pass
3. **Tests document behavior** — Reading tests shows what the system does
4. **Regression prevention** — If it broke once, there's a test for it now
5. **Growing suite** — Tests accumulate, coverage increases over time

### The Workflow

```
┌─────────────────────────────────────────────────────┐
│  1. UNDERSTAND what you're building                 │
│  2. WRITE a test that would pass if it worked       │
│  3. BUILD the feature                               │
│  4. RUN the test (it should pass)                   │
│  5. COMMIT with test included                       │
│  6. REPEAT                                          │
└─────────────────────────────────────────────────────┘
```

### Integration Points

| When | Action |
|------|--------|
| Before commit | Run `./test.sh` |
| During PR review | Check test coverage |
| On heartbeat (optional) | Run critical path tests |
| After deploy | Smoke test endpoints |

### Test File Conventions

```
project/
├── src/           # Source code
├── tests/         # Test files
│   ├── test_api.py
│   ├── test_db.py
│   └── test_ws.py
└── test.sh        # Runner script
```

### Example Test Structure

```python
def test_feature_name():
    """Test that [feature] does [expected behavior]"""
    # Arrange - set up test data
    # Act - call the function/API
    # Assert - verify the result
    test("Descriptive assertion", condition)
```

---

## 2. Documentation as Code

**Philosophy:** If it's not written down, it doesn't exist. Documentation travels with the code.

### Required Files

| File | Purpose |
|------|---------|
| `README.md` | What is this, how to use it |
| `HANDOFF.md` | State for next builder (context survival) |
| `AGENTS.md` | Instructions for AI agents working on this |
| `test.sh` | How to verify it works |

### The Handoff Pattern

When context is high or work pauses:
1. Update `HANDOFF.md` with current state
2. List what's done, what's in progress, what's next
3. Include commands to verify/continue
4. Future you (or another agent) can pick up seamlessly

---

## 3. Incremental Building

**Philosophy:** Ship small, working increments. Never let the system be broken for long.

### The Practice

1. **Vertical slices** — Build one complete feature, not half of many
2. **Always deployable** — Main branch should always work
3. **Feature flags** — Hide incomplete features, don't break existing ones
4. **Backward compatibility** — V1 API still works when V2 ships

---

## 4. Shared Knowledge

**Philosophy:** What one agent learns, all agents should know.

### Knowledge Propagation

```
Agent learns something
       ↓
Documents in appropriate file:
  - PRINCIPLES.md (philosophy/patterns)
  - LEARN.md (techniques/tools)
  - TOOLS.md (specific configurations)
  - memory/*.md (context/decisions)
       ↓
Other agents read on session start
       ↓
Knowledge persists across contexts
```

### When to Document

- New tool or technique discovered → LEARN.md
- Pattern that should be repeated → PRINCIPLES.md
- Mistake that shouldn't be repeated → LEARN.md (lessons learned)
- Configuration that works → TOOLS.md
- Decision with rationale → memory/YYYY-MM-DD.md

---

## 5. Verify Before Claiming

**Philosophy:** "It works" means "I tested it and saw it work."

### The Practice

1. **Run the code** — Don't assume, verify
2. **Check the output** — Did it actually do what you expected?
3. **Test edge cases** — What about empty input? Errors?
4. **Double-check your work** — When asked, actually verify

### Verification Commands

```bash
# Before claiming something works:
curl -s http://localhost:9090/health  # Check it responds
./test.sh                              # Run full test suite
git status                             # Check what changed
```

---

## Adopting These Principles

### For Individual Agents

1. Read this file on session start
2. Follow the practices
3. Update when you learn something new

### For New Projects

1. Create `test.sh` and `tests/` from the start
2. Write first test before first feature
3. Include `HANDOFF.md` for context survival

### For the Team

1. Reference principles in code reviews
2. Celebrate when tests catch bugs
3. Grow the test suite with every feature
4. Share learnings in LEARN.md

---

*"The discipline of writing tests isn't about catching bugs. It's about having confidence that what you built actually works."*

*— Learned by Portal1 🌀 on 2026-02-03*
