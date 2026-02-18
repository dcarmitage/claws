"""Scratchpad — structured working memory for agents.

The scratchpad is a living document that maintains operational state
across sessions. It distinguishes between:
- Active threads (what's being worked on)
- Pending decisions (what needs the human's input)
- Reflections (what's working, what isn't)

Unlike memory.md (retrospective), the scratchpad answers "where are we?"
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Status markers used in scratchpad format
STATUS_NEXT = "→"       # next action
STATUS_BLOCKED = "⏸"    # blocked on something
STATUS_DONE = "✓"       # done — archive soon
STATUS_QUESTION = "?"   # needs human input


@dataclass
class Thread:
    """An active work stream in the scratchpad."""
    name: str
    state: str = ""
    next_action: str = ""
    blocking: str = ""
    notes: list[str] = field(default_factory=list)

    def to_markdown(self) -> str:
        lines = [f"### {self.name}"]
        if self.state:
            lines.append(f"**State:** {self.state}")
        if self.next_action:
            lines.append(f"{STATUS_NEXT} {self.next_action}")
        if self.blocking:
            lines.append(f"{STATUS_BLOCKED} {self.blocking}")
        for note in self.notes:
            lines.append(f"- {note}")
        return "\n".join(lines)


@dataclass
class Decision:
    """A pending decision that needs human input."""
    number: int
    question: str
    context: str = ""
    urgency: str = "normal"
    resolved: bool = False
    resolution: str = ""

    def to_markdown_row(self) -> str:
        if self.resolved:
            return f"| ~~{self.number}~~ | ~~{self.question}~~ → **{self.resolution}** | {self.context} | ✓ Done |"
        return f"| {self.number} | {self.question} | {self.context} | {self.urgency} |"


@dataclass
class Scratchpad:
    """Full scratchpad state for an agent."""
    agent_name: str
    last_tended: str = ""
    threads: list[Thread] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    reflections: list[str] = field(default_factory=list)
    inbox: list[str] = field(default_factory=list)

    @property
    def next_decision_number(self) -> int:
        if not self.decisions:
            return 1
        return max(d.number for d in self.decisions) + 1

    def find_thread(self, name: str) -> Thread | None:
        """Find a thread by name (case-insensitive partial match)."""
        name_lower = name.lower()
        for t in self.threads:
            if t.name.lower() == name_lower:
                return t
        # Try partial match
        for t in self.threads:
            if name_lower in t.name.lower():
                return t
        return None

    def find_decision(self, number: int) -> Decision | None:
        """Find a decision by number."""
        for d in self.decisions:
            if d.number == number:
                return d
        return None

    def to_markdown(self) -> str:
        """Render the full scratchpad as markdown."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        self.last_tended = now

        lines = [
            f"# Scratchpad — {self.agent_name}",
            "",
            f"> Working memory. Last tended: {self.last_tended}",
            "",
            "---",
            "",
        ]

        # Threads
        lines.append("## 🧵 Open Threads")
        lines.append("")
        if self.threads:
            active_threads = [t for t in self.threads]
            for t in active_threads:
                lines.append(t.to_markdown())
                lines.append("")
        else:
            lines.append("_No active threads._")
            lines.append("")

        lines.append("---")
        lines.append("")

        # Decisions
        lines.append("## ⚖️ Decisions Waiting")
        lines.append("")
        lines.append("| # | Decision | Context | Urgency |")
        lines.append("|---|----------|---------|---------|")
        if self.decisions:
            for d in self.decisions:
                lines.append(d.to_markdown_row())
        else:
            lines.append("| - | _No pending decisions._ | | |")
        lines.append("")

        lines.append("---")
        lines.append("")

        # Inbox
        lines.append("## 📬 Inbox")
        lines.append("")
        if self.inbox:
            for item in self.inbox:
                lines.append(f"- {item}")
        else:
            lines.append("_(empty)_")
        lines.append("")

        lines.append("---")
        lines.append("")

        # Reflections
        lines.append("## 🪞 Reflections")
        lines.append("")
        if self.reflections:
            for r in self.reflections:
                lines.append(f"- {r}")
        else:
            lines.append("_No reflections yet._")
        lines.append("")

        return "\n".join(lines)


def scratchpad_path(project_root: Path, agent_name: str) -> Path:
    """Return the path to an agent's scratchpad.md."""
    return project_root / "agents" / agent_name / "scratchpad.md"


def load_scratchpad(project_root: Path, agent_name: str) -> Scratchpad | None:
    """Load a scratchpad from disk. Returns None if it doesn't exist."""
    path = scratchpad_path(project_root, agent_name)
    if not path.exists():
        return None
    return parse_scratchpad(path.read_text(), agent_name)


def save_scratchpad(project_root: Path, scratchpad: Scratchpad) -> Path:
    """Write a scratchpad to disk. Returns the file path."""
    path = scratchpad_path(project_root, scratchpad.agent_name)
    path.write_text(scratchpad.to_markdown())
    return path


def parse_scratchpad(text: str, agent_name: str) -> Scratchpad:
    """Parse a scratchpad.md file into a Scratchpad object.

    Tolerant parser — extracts what it can, ignores what it can't.
    """
    sp = Scratchpad(agent_name=agent_name)

    # Extract last tended
    tended_match = re.search(r"Last tended:\s*(.+?)(?:\n|$)", text)
    if tended_match:
        sp.last_tended = tended_match.group(1).strip()

    # Split into sections by ## headers
    sections = _split_sections(text)

    for header, body in sections:
        header_lower = header.lower()
        if "thread" in header_lower:
            sp.threads = _parse_threads(body)
        elif "decision" in header_lower:
            sp.decisions = _parse_decisions(body)
        elif "inbox" in header_lower:
            sp.inbox = _parse_list_items(body)
        elif "reflection" in header_lower:
            sp.reflections = _parse_list_items(body)

    return sp


def _split_sections(text: str) -> list[tuple[str, str]]:
    """Split markdown text into (header, body) pairs at ## level."""
    sections = []
    current_header = ""
    current_lines: list[str] = []

    for line in text.split("\n"):
        if line.startswith("## "):
            if current_header:
                sections.append((current_header, "\n".join(current_lines)))
            current_header = line.lstrip("# ").strip()
            current_lines = []
        elif current_header:
            current_lines.append(line)

    if current_header:
        sections.append((current_header, "\n".join(current_lines)))

    return sections


def _parse_threads(body: str) -> list[Thread]:
    """Parse threads from the Open Threads section."""
    threads = []
    current_thread: Thread | None = None

    for line in body.split("\n"):
        if line.startswith("### "):
            if current_thread:
                threads.append(current_thread)
            name = line.lstrip("# ").strip()
            current_thread = Thread(name=name)
        elif current_thread:
            stripped = line.strip()
            if stripped.startswith("**State:**"):
                current_thread.state = stripped.replace("**State:**", "").strip()
            elif stripped.startswith(STATUS_NEXT):
                current_thread.next_action = stripped[len(STATUS_NEXT):].strip()
            elif stripped.startswith(STATUS_BLOCKED):
                current_thread.blocking = stripped[len(STATUS_BLOCKED):].strip()
            elif stripped.startswith("- "):
                current_thread.notes.append(stripped[2:])

    if current_thread:
        threads.append(current_thread)

    return threads


def _parse_decisions(body: str) -> list[Decision]:
    """Parse decisions from the Decisions Waiting section."""
    decisions = []

    for line in body.split("\n"):
        line = line.strip()
        if not line.startswith("|"):
            continue
        # Skip header and separator rows
        if line.startswith("| #") or line.startswith("|---"):
            continue
        # Skip empty placeholder rows
        if "No pending decisions" in line:
            continue

        parts = [p.strip() for p in line.split("|")[1:-1]]
        if len(parts) < 4:
            continue

        num_str = parts[0]
        question = parts[1]
        context = parts[2]
        urgency = parts[3]

        # Check if resolved (strikethrough)
        resolved = "~~" in num_str
        resolution = ""
        if resolved:
            num_str = num_str.replace("~~", "").strip()
            # Extract resolution from question
            res_match = re.search(r"→\s*\*\*(.+?)\*\*", question)
            if res_match:
                resolution = res_match.group(1)
            question = re.sub(r"~~(.+?)~~.*", r"\1", question).strip()
            urgency = "resolved"

        try:
            number = int(num_str)
        except ValueError:
            continue

        decisions.append(Decision(
            number=number,
            question=question,
            context=context,
            urgency=urgency,
            resolved=resolved,
            resolution=resolution,
        ))

    return decisions


def _parse_list_items(body: str) -> list[str]:
    """Parse markdown list items from a section body."""
    items = []
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped.startswith("- "):
            items.append(stripped[2:])
    return items
