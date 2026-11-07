"""
Nov 7, 2026

Frank Caron
frankcaron.com

Claude Incident Triage Agent, for use with Claude Agent SDK; deployable locally, or in hosted Claude envs.

More info in the Readme.
"""

"""===="""
"""DEPS"""
"""===="""

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

"""===="""
"""VARS"""
"""===="""


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


"""==========="""
"""SCAFFOLDING"""
"""==========="""

"""This schema provides structure to the confidence scoring
allowing some basic configurability. This really doesn't have anything to do
with Claude Code, so don't mind me as I skim by this. Not much of a pythonista
but being able to just yeet json as so is nice, ngl.
"""
WEIGHTS = {"symptoms": 0.35, "trigger": 0.25, "service": 0.20, "coverage": 0.20}
PART = {"type": "number", "minimum": 0, "maximum": 1}
SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "parts": {
            "type": "object",
            "properties": {name: PART for name in WEIGHTS},
            "required": list(WEIGHTS),
        },
        "rationale": {"type": "string"},
        "gaps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["parts", "rationale", "gaps"],
}

"""==========="""
"""AGENT BRAIN"""
"""==========="""

"""Look, I'll level with you; when I used Claude Code to generate some of this
it raw-dumped the full prompts herein as long strings. So I moved it around the 
ol' fashioned way. This is the thing about agentic code; there's no accounting for 
taste sometimes. SOME HUMANS STILL NEED TO READ IT. ;) 
"""
TRIAGE_PROMPT = Path("prompts/triage.md").read_text(encoding="utf-8")
EXTRAPOLATE_PROMPT = Path("prompts/extrapolate.md").read_text(encoding="utf-8")


"""=========="""
"""AGENT BODY"""
"""=========="""

# Used for the audit trail write outs as part of the model quality eval inputs
def audit(event: dict) -> None:
    AUDIT.parent.mkdir(exist_ok=True)
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with AUDIT.open("a") as f:
        f.write(json.dumps(event) + "\n")


# Main run
print("Hello, agent.")
print(TRIAGE_PROMPT)
audit({"phase": "prep", "tool": "none", "input": "none",
       "decision": "none"})


"""===================="""
"""DEVELOPER EXPERIENCE"""
"""===================="""

"""Make this all cli fun like in the event I yeet the demo and forget the input incident, 
because hey, code is free now — but PIBKAC error isn't, and Claude said I'd prolly make a mistake."""
if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python triage.py incidents/<ID>")
    asyncio.run(main(sys.argv[1]))