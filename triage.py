"""
Nov 7, 2026

Frank Caron
frankcaron.com

Claude Incident Triage Agent, for use with Claude Agent SDK; deployable locally, or in hosted Claude envs.

More info in the Readme.
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

"""Demo point so Frank doesn't forget and helps our CTO feel comfortable: 
the SDK provides the control plane for security before it even gets to Anthropic. """
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    HookMatcher,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

"""Reference paths for the supporting documentation for my agent o' triage triumphy"""
ROOT = Path(__file__).resolve().parent
RUNBOOKS = ROOT / "runbooks"
AUDIT = ROOT / "audit" / "audit.jsonl"

"""Main runtime"""
print("Hello, agent.")

"""Make this all cli fun like in the event I yeet the demo and forget the input incident, 
because hey, code is free now — but PIBKAC error isn't."""
if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python triage.py incidents/<ID>")
    asyncio.run(main(sys.argv[1]))