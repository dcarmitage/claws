# Contributing

Contributions are welcome. This project is built by humans and AI agents working together.

## How to contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b my-feature`)
3. Make your changes
4. Run the test suite: `python -m pytest tests/ -v`
5. Test with the eval system if applicable
6. Submit a pull request

## PR guidelines

- Keep PRs focused. One feature or fix per PR.
- Include a clear description of what changed and why.
- If you modified Python code, ensure tests pass and add new tests for new behavior.
- If you modified eval prompts, include sample judge output showing the change.

## AI-assisted PRs

PRs written with AI assistance (Claude, GPT, Copilot, etc.) are welcome. Please note it in the PR description. The two-pass evaluation system was itself built by an AI agent — we practice what we preach.

## Development principles

These principles shape how we build claws. They apply to both human and agent contributors.

### Building
1. **Be specific.** Exact code in briefs. If you can't specify it, you don't understand it yet.
2. **One thing at a time.** Fresh context per task. Accumulated context corrupts.
3. **Sequence by flow.** Build what produces data before what consumes it.
4. **Eat your own cooking.** Use the tool to build the tool.

### Communication
5. **No surprises.** Announce heavy or risky operations before running them. Explain kills and failures immediately.
6. **Three outputs.** Every build produces: working code, documentation, and learning.

### Memory and state
7. **Write it down NOW.** Update daily memory AND curated memory at every milestone. Not later — now.
8. **Snapshot everything.** Git commit after every verified change. Rollback is a superpower.

### Self-awareness
9. **Watch your own gauges.** Monitor context, announce at 70%, stop at 85%.
10. **Clean up before you leave.** End every session with: git status, memory sync, commit.

### Architecture
11. **Main session orchestrates, sub-agents execute.** The main session writes specs, spawns builders, verifies results, and stays available for human conversation. Sub-agents get one task, fresh context, exact briefs. Never blur these roles.

For the full set of best practices with evidence and examples, see `docs/BEST_PRACTICES.md`.

## Code style

- Shell: `bash`, `set -euo pipefail`, shellcheck-clean
- Python: stdlib-first, type hints optional, 3.11+ features OK
- Markdown: ATX headings, tables for structured data
- Paths: `$CLAWS_HOME` or relative, never hardcoded absolute paths

## Reporting issues

Open a GitHub issue with:
- What you expected
- What happened
- Steps to reproduce
- Platform and Python version
