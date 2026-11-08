"""
Nov 7, 2026

Frank Caron
frankcaron.com

REAL-TIME INCIDENT TRIAGE
Built with Claude Agent SDK.
Deployable locally or in hosted Claude Code capable envs.
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
FALLBACK_MODEL = os.environ.get("TRIAGE_FALLBACK_MODEL", "opusplan")
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

        #Explictly allow-list only specific shell tools
        allowed_tools=["Read", "Glob", "Grep"],

        #Explictly deny-list specific shell tools and cloud tools
        disallowed_tools=["Bash", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch"],

        #Enforce a certain approach to the model asking for elevated permissions
        permission_mode="dontAsk",

        #Apply the deny rules in .claude/settings.json
        setting_sources=["project"],
        cwd=str(ROOT),

        #Set a fixed budget cap to control cost acros each individual call
        max_budget_usd=0.33,

        #Point to hooks that run before the model does anything to catch oopsies
        hooks={"PreToolUse": [HookMatcher(hooks=[make_guard(incident_dir, phase)])]},
        **extra,
    )

# Used to valide the specific tools and lock down what the agent is capable of
# This is critical, deterministic, and definitive.
def make_guard(incident_dir: Path, phase: str):
    readable = (incident_dir, RUNBOOKS)

    async def guard(input_data, tool_use_id, context):
        tool = input_data.get("tool_name")
        args = input_data.get("tool_input", {})
        reason = None
        if tool in ("Read", "Glob", "Grep"):
            if tool == "Glob":
                # Judge a Glob by its base folder plus the pattern's fixed prefix,
                # so "incidents/INC-1101/**" passes even when path is the repo root.
                pattern = args.get("pattern", "")
                target = ROOT / (args.get("path") or ".") / pattern.split("*")[0]
                if ".." in pattern:
                    target = ROOT  # never let a pattern climb out of a folder
            else:
                target = ROOT / (args.get("file_path") or args.get("path") or ".")
            resolved = target.resolve()
            if not any(resolved.is_relative_to(d) for d in readable):
                reason = "Only the incident folder and runbooks/ may be read."
        elif tool not in ("Skill", "StructuredOutput"):
            reason = "This agent reads and suggests; a human runs commands."
        audit({"phase": phase, "tool": tool, "input": args,
               "decision": "deny" if reason else "allow"})
        if reason is None:
            return {}
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }

    return guard


"""==========="""
"""AGENT LIMBS"""
"""==========="""

# Used for the audit trail write outs as part of the model quality eval inputs
def audit(event: dict) -> None:
    AUDIT.parent.mkdir(exist_ok=True)
    event["ts"] = datetime.now(timezone.utc).isoformat()
    with AUDIT.open("a") as f:
        f.write(json.dumps(event) + "\n")

# Used for the audit trail to memorialize whether the SRE on call accepted the agent's guidance or not
# This audit trail output helps us get to our "SRE Acceptance Rate" from the deckware and would be
# What we can anchor evals on to improve in the future, manually or with Claude Code itself
def ask_sre(incident: str, runbook: str, score: float, path: str, remediation: str) -> None:
    """Record the on-call SRE's verdict for evals. A yes runs nothing."""
    answer = ""
    while answer not in ("y", "n"):
        answer = input("\nDo you accept this remediation? Nothing runs either way. [y/n] ").strip().lower()[:1]
    accepted = answer == "y"
    reason = "" if accepted else input("Why not? (optional, Enter to skip) ").strip()
    audit({"phase": "verdict", "incident": Path(incident).name, "runbook": runbook,
           "score": score, "path": path, "remediation": remediation,
           "accepted": accepted, "reason": reason or None})
    print("Verdict recorded in audit/audit.jsonl.")

# Used to support scoring calcs to determine course of action
def combine(data: dict | None) -> float:
    """Weight the scorer's parts in code. No runbook, or no valid score,
    counts as zero confidence: fail toward review."""
    if not data:
        return 0.0
    return round(sum(w * data["parts"][k] for k, w in WEIGHTS.items()), 2)

# The core SDK invoke for calling the Claude messaging API
# This generic method is used in different contexts with the supplied prompts
# To get different jobs done based on the agent-specific algo that follows.
async def run(prompt: str, opts: ClaudeAgentOptions, show: bool = True):
    result = None
    async for message in query(prompt=prompt, options=opts):
        if show and isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock) and block.name != "StructuredOutput":
                    print(f"  -> {block.name} {json.dumps(block.input)}")
                elif isinstance(block, TextBlock):
                    print(block.text)
        elif isinstance(message, ResultMessage):
            result = message
            print(f"[{message.subtype}, ${message.total_cost_usd or 0:.3f}]")
    return result


"""==========="""
"""AGENT TORSO"""
"""==========="""

"""This is the main meat-and-potatoes of the agent itself.
The overall algo is fairly readable to the naked eye, but to provide the basic gist:

Based on the input sample incident, which you could imagine gets invoked by an event stream
hitting your AWS infra directly from either Cloudwatch or say another monitoring platform like
Datadog, the agent kicks off.

`triage` invokes the first agent, to attempt to triage the incident, and that agent returns a result.

`plan` invokes the fallback second agent, of stronger muscle, to assess if the first agent isn't confident
enough in its result.
"""

async def main(incident: str) -> None:
    incident_dir = (ROOT / incident).resolve()

    # Run the first agent to triage and identify correct runbook, if it can
    print("== Triage ==")
    triage = await run(
        f"Triage the incident in {incident}. Start with alert.json, "
        "then find the matching runbook in runbooks/.",
        options(incident_dir, "triage", model=TRIAGE_MODEL, system_prompt=TRIAGE_PROMPT,
                skills=[], max_turns=25),
    )
    found = re.search(r"^RUNBOOK:\s*(\S+)", (triage.result or "") if triage else "", re.M)
    runbook = found.group(1) if found else "none"

    # Run the second agent to score based on its confidence
    print(f"\n== Runbook confidence ({SCORER_MODEL}) ==")
    data = None
    if runbook != "none":
        scored = await run(
            f"/runbook-confidence {incident} {runbook}",
            options(incident_dir, "score", model=SCORER_MODEL, skills=["runbook-confidence"],
                    max_turns=10, output_format={"type": "json_schema", "schema": SCORE_SCHEMA}),
            show=False,
        )
        data = scored.structured_output if scored else None
    score = combine(data)
    print(f"Runbook: {runbook}")
    print(f"Confidence: {score:.2f} (threshold {THRESHOLD:.2f})")
    if data:
        for name in WEIGHTS:
            print(f"  {name}: {data['parts'][name]:.2f}")
        print(f"Why: {data['rationale']}")
        for gap in data["gaps"]:
            print(f"  gap: {gap}")
    audit({"phase": "score", "runbook": runbook, "score": score, "threshold": THRESHOLD})

    # If the score is above our threshold, let rip and ask SRE for approval
    if score >= THRESHOLD:
        print("Above the threshold: the runbook commands above stand, pending human approval.")
        ask_sre(incident, runbook, score, "runbook", (triage.result or "") if triage else "")
        return

    # If the score is below our threshold, run the third agent to ideate an alternative
    # Then ask the SRE to take over
    print(f"\n== Extrapolated plan ({FALLBACK_MODEL}) ==")
    gaps = "; ".join(data["gaps"]) if data else "no usable score"
    plan = await run(
        f"Incident folder: {incident}. Closest runbook: {runbook}, confidence {score:.2f}. "
        f"Gaps found by the scorer: {gaps}. Write the extrapolated plan.",
        options(incident_dir, "extrapolate", model=FALLBACK_MODEL,
                system_prompt=EXTRAPOLATE_PROMPT, skills=[], max_turns=25),
    )
    ask_sre(incident, runbook, score, "fallback", (plan.result or "") if plan else "")

"""===================="""
"""DEVELOPER EXPERIENCE"""
"""===================="""

"""Make this all cli fun like in the event I yeet the demo and forget the input incident, 
because hey, code is free now — but PIBKAC error isn't, and Claude said I'd prolly make a mistake.
At this point, it also allows root access technically, but I'm not going to overdo it here. 
Claude already told me I was slacking herein... which itself is a good demonstration of its value as
a peer programmer.
"""
if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Hello, agent.")
        audit({"phase": "pre-run test", "tool": "none", "input": "none", "decision": "none"})
    if len(sys.argv) != 2:
        sys.exit("usage: python triage.py incidents/<ID>")
        audit({"phase": "pre-run goose", "tool": "none", "input": "none", "decision": "none"})
    asyncio.run(main(sys.argv[1]))