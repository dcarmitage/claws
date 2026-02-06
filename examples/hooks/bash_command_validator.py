#!/usr/bin/env python3
"""Example PostToolUse hook: validate bash commands before they run.

Reads hook input from stdin (JSON with tool_name and tool_input).
Outputs JSON to inject a message, or nothing to pass silently.

Install by adding to .claude/settings.json:
{
  "hooks": {
    "PostToolUse": [{
      "matcher": "Bash",
      "hooks": [{"type": "command", "command": "python3 path/to/bash_command_validator.py"}]
    }]
  }
}
"""

import json
import sys

# Commands that should trigger a warning
DANGEROUS_PATTERNS = [
    "rm -rf /",
    "git push --force",
    "git reset --hard",
    "DROP TABLE",
    "DELETE FROM",
    "> /dev/sda",
]


def main():
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError):
        return

    if hook_input.get("tool_name") != "Bash":
        return

    command = hook_input.get("tool_input", {}).get("command", "")

    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in command.lower():
            result = {
                "decision": "approve",
                "reason": f"[HOOK WARNING] Potentially dangerous command detected: '{pattern}' in '{command[:100]}'. Proceed with caution."
            }
            print(json.dumps(result))
            return

    # Silent pass-through for safe commands


if __name__ == "__main__":
    main()
