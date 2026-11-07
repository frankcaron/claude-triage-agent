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

# Used for the scoring system. Just normal Python stuff. No demo point needed.
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

Jokes aside, this is where some of the more general LLM instrumentation comes
into contact with what Anthropic is doing specifically with its SDK, wrapping
the models in supporting developer tools that ensure probabilistic operation
doesn't become... problematic.
"""

# Used to power the model calls
TRIAGE_PROMPT = Path("prompts/triage.md").read_text(encoding="utf-8")
EXTRAPOLATE_PROMPT = Path("prompts/extrapolate.md").read_text(encoding="utf-8")

# Used to instantiate the SDK with all the right things
# Important call outs here based on the SDK deps callouts
# Step through all these
def options(incident_dir: Path, phase: str, **extra) -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        allowed_tools=["Read", "Glob", "Grep"],
        disallowed_tools=["Bash", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch"],
        permission_mode="dontAsk",
        setting_sources=["project"],
        cwd=str(ROOT),
        max_budget_usd=1.00,
        hooks={"PreToolUse": [HookMatcher(hooks=[make_guard(incident_dir, phase)])]},
        **extra,
    )

"""==========="""
"""AGENT LIMBS"""
"""==========="""

# Used for the audit trail write outs as part of the model quality eval inputs
def audit(event: dict) -> None:
    AUDIT.parent.mkdir(exist_ok=True)
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with AUDIT.open("a") as f:
        f.write(json.dumps(event) + "\n")

# Used to support scoring calcs to determine course of action
def combine(data: dict | None) -> float:
    """Weight the scorer's parts in code. No runbook, or no valid score,
    counts as zero confidence: fail toward review."""
    if not data:
        return 0.0
    return round(sum(w * data["parts"][k] for k, w in WEIGHTS.items()), 2)

"""==========="""
"""AGENT TORSO"""
"""==========="""

# Main run
print("Hello, agent.")
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