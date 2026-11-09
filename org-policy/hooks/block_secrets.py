#!/usr/bin/env python3
"""Claude Code PreToolUse hook: refuse any tool call that writes or runs a secret.

Best-effort: it scans literal text only, so encoded or runtime-built keys get past it.
"""

import json
import re
import sys

PATTERNS = {
    "Anthropic API key": r"sk-ant-[A-Za-z0-9_-]{16,}",
    "AWS access key": r"AKIA[0-9A-Z]{16}",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    # Any name ending in one of these (auth_token, DB_PASSWORD). Values starting with `$` are
    # taken as env lookups and allowed, so a literal like "$uper..." gets through: a trade-off.
    "hard-coded credential": r"(?i)(api_key|secret|password|token)\s*=\s*[\"'](?!\$)[^\"']{12,}[\"']",
}


def new_text(tool_input: dict) -> str:
    """Collect the text an edit would write or a shell command would run."""
    keys = ("content", "new_string", "new_source", "command")
    parts = [tool_input.get(k, "") for k in keys]
    edits = tool_input.get("edits") or []
    parts += [e.get("new_string", "") for e in edits if isinstance(e, dict)]
    return "\n".join(str(p) for p in parts)


def target_of(tool_input: dict) -> str:
    """Name what the tool call would write to, for the block message."""
    return (
        tool_input.get("file_path")
        or tool_input.get("notebook_path")
        or ("a shell command" if "command" in tool_input else "this file")
    )


def main() -> int:
    """Exit 2 (block, reason on stderr) if the call holds a secret or can't be read, else 0."""
    try:
        tool_input = json.load(sys.stdin).get("tool_input") or {}
        text = new_text(tool_input)
    except Exception:  # noqa: BLE001 - any failure must block, not exit 1 and let it through
        print(
            "Blocked by org policy: the secrets check could not read this tool call.",
            file=sys.stderr,
        )
        return 2
    for name, pattern in PATTERNS.items():
        if re.search(pattern, text):
            print(
                f"Blocked by org policy: this tool call contains a {name} "
                f"(target: {target_of(tool_input)}). Read it from the environment instead.",
                file=sys.stderr,
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
