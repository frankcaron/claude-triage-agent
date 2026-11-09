# Claude-Native Incident Triage Agent

As I begin to spend more time with Claude directly following years of preferring multi-model tooling like Cursor and Perplexity, I am attempting to port or reapply patterns I've worked with in the real world to Anthropic's native stack.

This example draws on that experience from real-world production as discussed in our [public use case from Reach](https://build.reach.com/reaching-autonomy-a-double-click-on-one-of-our-supervised-agentic-workflows-6db3ff9c35cd).

This project contains a simplified-in-some-ways, extended-in-others read-only incident triage agent for a consumer lender. It reads a simulated incident (an alert, service logs, recent deploys) and a small runbook library, then writes a triage note: likely cause, evidence as file:line, blast radius, and suggested commands for a human to approve. It never runs anything.

Built with Claude Code and the Claude Agent SDK.

## How it works

`triage.py` runs up to three agents in a row, each with the same read-only tools, deny rules and audit hook:

1. **Triage**, on Claude Code's default model: reads the incident and `runbooks/`, writes the note, and names the runbook it used on a last `RUNBOOK:` line.
2. **Score**, on `haiku`: the `runbook-confidence` skill scores four parts of the fit (symptoms, trigger, service, coverage) from 0 to 1. Python, not a model, weights them, and compares the total with the threshold. The model judges, code decides.
3. **Extrapolate**, on `opus`, only below the threshold: writes a plan where every command is labeled "Adapted from <runbook file>, <section>" or "New, not in any runbook".

A missing runbook or a probabilistic oopsy in confidence registers as a 0, so a failure always sends the incident toward more review, never less.

Each run ends by asking the on-call SRE whether they accept the remediation. The answer goes to the audit log (`audit/audit-soc2-control-log.jsonl`) for evals and runs nothing.

## Setup

Needs Python 3.10 or later.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY="<your key>"          # the SDK does not read .env
```

For the guardrail beat, you can create a `.env` with fake values as a decoy; the deny rules stop the agent from reading it. The repo doesn't ship one.

Run `triage.py` from the repo root: it loads `prompts/` relative to the current directory.

| Variable | Default | What it does |
|---|---|---|
| `ANTHROPIC_API_KEY` | none | Your API key. Export it in the shell. |
| `TRIAGE_MODEL` | Claude Code's default | Model alias for the triage agent. |
| `TRIAGE_SCORER_MODEL` | `haiku` | Model alias for the confidence scorer. |
| `TRIAGE_FALLBACK_MODEL` | `opus` | Model alias for the extrapolated plan. |
| `TRIAGE_CONFIDENCE_THRESHOLD` | `0.7` | Scores at or above this keep the runbook's commands. |

Aliases resolve to the newest model your provider serves depending on where you're running this; for demo's sake, I run locally.

## Run it

```bash
rm -rf audit                          # one run per audit file keeps the screen clean
python triage.py incidents/INC-1101   # demo: runbook path
python triage.py incidents/INC-1102   # demo: Opus fallback path
python triage.py incidents/INC-1103   # Q&A only: bureau timeouts
python triage.py incidents/INC-1104   # Q&A only: e-sign queue stuck
```

Try a stricter threshold or another model without editing code:

```bash
TRIAGE_CONFIDENCE_THRESHOLD=0.8 TRIAGE_FALLBACK_MODEL=sonnet python triage.py incidents/INC-1102
```

## The scenarios

The scenarios have been pre-baked to save me the time and tokens to generate fake ones constantly and or wire this up to a real monitoring platform; our public blog posts details how this would work in a real operating environment. In the interim, the samples:

| Incident | What happened | Runbook it should pick | Confidence | What follows |
|---|---|---|---|---|
| INC-1101 | ACH disbursements rejected (R04) after the 09:41 funding-svc 4.18.0 release; 38 loans unpaid | `disbursement-failure.md` | 0.96 in one test run | Runbook commands stand |
| INC-1102 | Pay stub fraud checks inconclusive after the vendor's model v7.2; 41 applications waiting | none fits | 0.00 in one test run (triage answered `none`); 0 to 0.15 if it picks the closest runbook | Opus extrapolates |
| INC-1103 | Credit bureau pulls timing out; applications stuck in PENDING_CREDIT | `bureau-pull-timeout.md` | about 0.9, estimate, not run | Runbook commands stand |
| INC-1104 | E-sign queue stuck after a template publish dropped `apr_disclosure` | `esign-queue-stuck.md` | about 0.9, estimate, not run | Runbook commands stand |

## Disclaimers

This is meant as a demo, so there would be work necessary to move this directly into production. I've deliberately left it incomplete. Couple of callouts:

* Every applicant, loan and bank account in this repo is synthetic (`APP-SYN-*`, `LN-SYN-*`, `BA-SYN-*`).
* Every host, token and API path in the runbooks is a placeholder.
* Each agent call has a $0.33 budget cap (`max_budget_usd`), so a full three-agent run tops out around $1.00.
* `CLAUDE.md` adds house rules for any Claude session in the repo.
* The repo adds deliberately-intended fakery to demonstrate Claude's unique baked-in guardrails, outlined below.

### Guardrails: three layers

Ultimately, this is the money stuff. The SDK exposes key guardrails, as does the Claude platform-level controls, and these make the developer experience with Claude Code powerful. This includes...

1. **SDK options.** `allowed_tools` approves Read, Glob and Grep. `disallowed_tools` removes Bash, Write, Edit and the web tools from the model's context. `permission_mode="dontAsk"` denies anything that would prompt, so a run never hangs on stage.
2. **Deny rules** in `.claude/settings.json`: Bash, `.env`, `.env.*` and `secrets/` are denied, and a deny wins in every permission mode. This is the same file format an enterprise pushes through managed settings.
3. **A PreToolUse hook** in `triage.py`: logs every attempted call to `audit/audit-soc2-control-log.jsonl`, denies any read outside the incident folder and `runbooks/`, and denies every tool except Read, Glob, Grep, the skill and structured output.
