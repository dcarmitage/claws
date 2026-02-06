# Contributing

Contributions are welcome. This project is built by humans and AI agents working together.

## How to contribute

1. Fork the repository
2. Create a feature branch (`git checkout -b my-feature`)
3. Make your changes
4. Test with the eval system if applicable
5. Submit a pull request

## PR guidelines

- Keep PRs focused. One feature or fix per PR.
- Include a clear description of what changed and why.
- If you modified shell scripts, verify they work with `set -euo pipefail`.
- If you modified eval prompts, include sample judge output showing the change.

## AI-assisted PRs

PRs written with AI assistance (Claude, GPT, Copilot, etc.) are welcome. Please note it in the PR description. The dual-judge system was itself built by an AI agent — we practice what we preach.

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
- Platform (Pi model, OS version, Python version)
