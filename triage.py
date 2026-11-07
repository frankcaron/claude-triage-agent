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

"""Demo point so Frank doesn't forget and helps our CTO feel comfortable: 
Safety is about more than just saying no to dodgey data use. It's also about runaway cost control.
The SDK provides the control plane for cost management explictly, including model invocation. 
The triage agent's confidence scoring system is powered by direct-control model swaps.
In this example, the model aliases are generalized to allow level ups as Anthropic improves. 
But the example here shows how you could pin if you need or want to.
"""

TRIAGE_MODEL = os.environ.get("TRIAGE_MODEL")  # None = Claude Code's default
SCORER_MODEL = os.environ.get("TRIAGE_SCORER_MODEL", "haiku")
FALLBACK_MODEL = os.environ.get("TRIAGE_FALLBACK_MODEL", "opus")
THRESHOLD = float(os.environ.get("TRIAGE_CONFIDENCE_THRESHOLD", "0.7"))

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