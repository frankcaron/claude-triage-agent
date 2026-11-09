#!/usr/bin/env python3
"""Claude Code PreToolUse hook: refuse any edit that writes a secret into a file."""

import json
import re
import sys

PATTERNS = {
    "Anthropic API key": r"sk-ant-[A-Za-z0-9_-]{16,}",
    "AWS access key": r"AKIA[0-9A-Z]{16}",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "hard-coded credential": r"(?i)\b(api_key|secret|password|token)\s*=\s*[\"'][^\"']{12,}[\"']",
}


def new_text(tool_input: dict) -> str:
    """Collect the text an Edit or Write call would put into the file."""
    parts = [tool_input.get("content", ""), tool_input.get("new_string", "")]
    parts += [e.get("new_string", "") for e in tool_input.get("edits", []) or []]
    return "\n".join(str(p) for p in parts)


def main() -> int:
    """Exit 2 (block, reason on stderr) if the edit holds a secret, else 0."""
    tool_input = json.load(sys.stdin).get("tool_input", {})
    text = new_text(tool_input)
    for name, pattern in PATTERNS.items():
        if re.search(pattern, text):
            target = tool_input.get("file_path", "this file")
            print(
                f"Blocked by org policy: this edit writes a {name} into {target}. "
                "Read it from the environment instead.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())