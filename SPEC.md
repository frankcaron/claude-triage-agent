# Spec: agentic incident triage agent

Status: demo. Describes what is implemented as of commit `442212f` (2026-11-09).
Source of intent: [INTENT.md](INTENT.md). Where the code and the README disagree, this spec follows the code; remaining gaps are under [Known gaps](#9-known-gaps-and-discrepancies).

## 1. Intent → implementation map

| INTENT.md says | What the repo implements |
|---|---|
| **Problem:** SRE spends rote time reading logs and assessing incidents when monitors fire. | A read-only agent pipeline (`triage.py`) that reads an incident folder (alert, deploys, logs) and a runbook library, then writes a triage note with cause, evidence as `file:line`, blast radius and suggested commands. |
| **Outcome, phase 1:** SRE acts as an approval gate. | Every run ends with `ask_sre()` ([triage.py:179](triage.py:179)): the on-call SRE answers y/n on the remediation. Nothing is executed either way. |
| **Outcome, phase 2:** SRE focuses on eval review and iteration with Claude Code. | Partially. Every tool call, score and SRE verdict is appended to a JSONL audit log ([triage.py:170](triage.py:170)) intended as eval input ("SRE acceptance rate"). No eval harness or report reads that log yet. |
| **Affected:** SRE team, end users, all production systems. | Demo scope: four synthetic incidents for a consumer lender (`incidents/INC-1101`…`1104`) and three runbooks. No live monitor integration. |
| **Constraint:** protect consumer PII; actions on consumer data follow project guardrails. | Synthetic data only (`APP-SYN-*`, `LN-SYN-*`, `BA-SYN-*`); agent can read only the incident folder and `runbooks/`; no write, shell or web tools; prompts forbid moving money or approving/declining applicants. No PII redaction step exists (see §9). |
| **Open question:** which triage scenarios can never be fully automated? | Not answered in code. The prompts encode a partial answer: anything that moves money, approves/declines an applicant, or resolves an inconclusive fraud result belongs to a human (§4.3). |

## 2. Scope

**In scope (implemented)**
- CLI entry point: `python triage.py incidents/<ID>`, run from the repo root.
- Three-stage pipeline: triage → confidence score → (conditional) extrapolated plan.
- Deterministic confidence weighting and threshold routing in Python.
- Layered guardrails: SDK options, project deny rules, an in-process PreToolUse guard, and an org-level secrets hook for Claude Code sessions.
- Audit log of tool decisions, scores and SRE verdicts.
- Claude Code developer tooling for working on the repo (skills, review subagents, rules).

**Out of scope (not implemented)**
- Executing any remediation command.
- Ingesting alerts from a real monitoring platform (CloudWatch, Datadog); incidents are static fixtures.
- An eval pipeline over the audit log.
- PII detection or redaction.

## 3. Inputs

### 3.1 Incident folder
`incidents/<ID>/` containing:
- `alert.json`: `id`, `service`, `severity`, `fired_at`, `signal`, `value`, `baseline`, a scenario-specific count, `summary`.
- `deploys.md`: recent releases.
- `logs/<service>.log`: service logs.

Fixtures and their expected outcome (from README; scores are single test runs or estimates):

| Incident | Scenario | Expected runbook | Expected path |
|---|---|---|---|
| INC-1101 | ACH disbursements rejected (R04) after funding-svc 4.18.0 | `disbursement-failure.md` | runbook (scored 0.96 once) |
| INC-1102 | Pay stub fraud checks inconclusive after vendor model v7.2 | none | fallback (scored 0.00 once) |
| INC-1103 | Credit bureau pulls timing out | `bureau-pull-timeout.md` | runbook (estimate) |
| INC-1104 | E-sign queue stuck after template dropped `apr_disclosure` | `esign-queue-stuck.md` | runbook (estimate) |

Saved outputs of real runs for INC-1101 and INC-1102 are in `samples/`.

### 3.2 Runbooks
`runbooks/*.md`, each with sections: Symptoms, Diagnose (read-only), Act (human only), Verify, Escalate. `disbursement-failure.md` requires two approvers for Act steps.

### 3.3 Configuration (environment variables)

| Variable | Default | Used at |
|---|---|---|
| `ANTHROPIC_API_KEY` | none | read by the SDK; must be exported (the SDK does not read `.env`) |
| `TRIAGE_MODEL` | `None` → Claude Code's default | [triage.py:48](triage.py:48) |
| `TRIAGE_SCORER_MODEL` | `haiku` | [triage.py:49](triage.py:49) |
| `TRIAGE_FALLBACK_MODEL` | `opus` | [triage.py:50](triage.py:50) |
| `TRIAGE_CONFIDENCE_THRESHOLD` | `0.7` | [triage.py:51](triage.py:51) |

## 4. Pipeline

`main()` ([triage.py:234](triage.py:234)) runs up to three agent calls via `run()` ([triage.py:202](triage.py:202)), which streams tool calls and text to stdout and prints the result subtype and cost.

### 4.1 Stage 1: Triage
- Model `TRIAGE_MODEL`, system prompt [prompts/triage.md](prompts/triage.md), no skills, `max_turns=25` ([triage.py:239-244](triage.py:239)).
- Output: a note with headings Summary, Likely cause, Evidence (file:line), Blast radius, Runbook, Suggested commands. Commands are copied only from the chosen runbook, grouped "Diagnose, read-only" and "Act, changes production, needs approval", each citing its runbook section.
- Final line: `RUNBOOK: runbooks/<file>.md` or `RUNBOOK: none`.
- Python extracts the runbook with `^RUNBOOK:\s*(\S+)` (multiline, first match). No match or no result → `"none"` ([triage.py:245-246](triage.py:245)).

### 4.2 Stage 2: Confidence score
- Skipped when runbook is `none`.
- Model `SCORER_MODEL`, prompt `/runbook-confidence <incident> <runbook>`, skill [runbook-confidence](.claude/skills/runbook-confidence/SKILL.md), `max_turns=10`, structured output against `SCORE_SCHEMA` ([triage.py:251-258](triage.py:251)). Tool calls are not echoed (`show=False`).
- The model scores four parts 0–1 plus a rationale and a list of gaps; it does not compute a total.
- `combine()` ([triage.py:192](triage.py:192)) weights the parts in code and rounds to 2 places:

  | Part | Weight |
  |---|---|
  | symptoms | 0.35 |
  | trigger | 0.25 |
  | service | 0.20 |
  | coverage | 0.20 |

- No runbook or no structured output → score `0.0` (fail toward review).
- Prints runbook, score vs threshold, per-part scores, rationale and gaps; audits a `score` event.

### 4.3 Routing
- `score >= THRESHOLD` → **runbook path**: the triage note's commands stand; `ask_sre(..., path="runbook", remediation=<triage note>)`, then exit ([triage.py:271-274](triage.py:271)).
- Otherwise → **Stage 3: Extrapolate** ([triage.py:278-286](triage.py:278)):
  - Model `FALLBACK_MODEL`, system prompt [prompts/extrapolate.md](prompts/extrapolate.md), no skills, `max_turns=25`. The user prompt carries the incident, closest runbook, score and the scorer's gaps (or "no usable score").
  - Output: one section "Extrapolated plan (lower confidence, review before acting)". Each command is labeled "Adapted from <runbook>, <section>" or "New, not in any runbook", grouped Diagnose / Act, read-only checks first, `<placeholders>` for unknown values. Re-runs and money movement are Act steps naming an approver. Never approves/declines an applicant or treats an inconclusive result as pass/fail.
  - Then `ask_sre(..., path="fallback", remediation=<plan>)`.

### 4.4 SRE verdict
`ask_sre()` ([triage.py:179](triage.py:179)) loops until `y` or `n`, asks an optional reason on `n`, writes a `verdict` audit event (`incident`, `runbook`, `score`, `path`, `remediation`, `accepted`, `reason`) and runs nothing.

## 5. Guardrails

Applied to every agent call via `options()` ([triage.py:102](triage.py:102)):

1. **SDK options**
   - `allowed_tools=["Read", "Glob", "Grep"]`
   - `disallowed_tools=["Bash", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch"]`
   - `permission_mode="dontAsk"`: anything that would prompt is denied, so runs never hang.
   - `setting_sources=["project"]`, `cwd=ROOT`: loads `.claude/settings.json` deny rules.
   - `max_budget_usd=0.33` per agent call (up to three calls per run).
2. **Project deny rules** ([.claude/settings.json](.claude/settings.json)): deny reads of `.env`, `.env.*`, `secrets/**`; deny `git push`, `rm`; deny edits to `prompts/`, `runbooks/`, `incidents/`, `CLAUDE.md`, `.claude/`, `triage.py`. Allows edits to top-level `*.py` and `tests/**`, plus `pytest` and `ruff`.
3. **PreToolUse guard** `make_guard()` ([triage.py:128](triage.py:128)):
   - Read/Grep: path (default repo root) must resolve inside the incident folder or `runbooks/`.
   - Glob: judged by `path` + the pattern's prefix before the first `*`; any `..` in the pattern resolves to the repo root and is denied.
   - `Skill` and `StructuredOutput` are allowed without path checks.
   - Every other tool is denied ("This agent reads and suggests; a human runs commands.").
   - Every attempt, allowed or denied, is audited with phase, tool, input and decision.
4. **Org secrets hook** (Claude Code sessions, not the SDK agent): [org-policy/managed-settings.json](org-policy/managed-settings.json) runs [block_secrets.py](org-policy/hooks/block_secrets.py) on Edit/Write/MultiEdit/NotebookEdit/Bash. It exits 2 on an Anthropic key, AWS access key, PEM private key, or a quoted `api_key|secret|password|token = "…"` literal of 12+ chars (values starting with `$` pass). Unreadable input fails closed. The block message names the target, never the secret. Managed settings also deny `.env`/`secrets/` reads via Bash, `curl`, `wget`, `git push --force`, and disable bypass-permissions mode. Deployed path: `/Library/Application Support/ClaudeCode/hooks/`.

## 6. Audit log
- File: `audit/audit-soc2-control-log.jsonl` ([triage.py:56](triage.py:56)), append-only JSONL, directory created on demand, git-ignored.
- Every event gets a UTC ISO `ts`.
- Event types (`phase`): `triage`, `score`, `extrapolate` (tool decisions); `score` (runbook, score, threshold); `verdict` (SRE answer); `pre-run test` (no-argument invocation).

## 7. CLI behaviour
- `python triage.py incidents/<ID>`: runs the pipeline.
- No argument: prints "Hello, agent.", writes a `pre-run test` audit event, then exits with the usage message.
- Wrong number of arguments: exits with `usage: python triage.py incidents/<ID>`.
- Prompts load from `prompts/` relative to the current directory at import time ([triage.py:96-97](triage.py:96)), so it must run from the repo root.

## 8. Developer tooling and tests
- Dependencies: `claude-agent-sdk==0.2.179`; dev: `pytest`, `ruff`. Python 3.10+.
- Claude Code skills: `write-code` (change + test + format/lint/test), `write-tests` (offline tests in `tests/` only), `runbook-confidence` (used by Stage 2).
- Subagents: `code-reviewer` and `test-reviewer`, read-only, on `sonnet`.
- Rules: [.claude/rules/python.md](.claude/rules/python.md), [.claude/rules/testing.md](.claude/rules/testing.md).
- Tests: [tests/test_block_secrets.py](tests/test_block_secrets.py) covers the org secrets hook (each tool shape, each secret kind, length boundaries, fail-closed input, message never echoes the secret) and the managed-settings matcher/deny rules. [tests/conftest.py](tests/conftest.py) provides a `triage_mod` fixture (faked `run`/`ask_sre`, temp `AUDIT`, pinned threshold) for offline pipeline tests.

## 9. Known gaps and discrepancies
1. **No tests for `triage.py`.** The `triage_mod` fixture exists but no test uses it: `combine()`, threshold routing, `RUNBOOK:` parsing and `make_guard()` are untested.
2. **Unreachable audit call.** [triage.py:304](triage.py:304) follows `sys.exit()` and never runs.
3. **PII constraint is only partly met.** Reads are confined and data is synthetic, but nothing redacts PII, and the audit log stores full tool inputs and the full remediation text.
4. **Eval loop not built.** Verdicts are recorded; nothing computes acceptance rate or feeds evals.
5. **Working-directory dependency.** Prompt paths are CWD-relative while `ROOT` is used everywhere else. The README now documents running from the repo root.
6. **`RUNBOOK:` parsing takes the first match,** not the last line the prompt asks for.

The README's audit file name, budget cap and `.env.example` setup step were corrected to match the code on 2026-11-09.

## 10. Open questions
- From INTENT.md: which triage scenarios can never be fully automated? Current candidates encoded in prompts: money movement, applicant approve/decline, inconclusive fraud results, and any incident with no fitting runbook (always routed to a human-reviewed fallback).
- What evidence (acceptance rate, score calibration) moves the SRE from approval gate to eval reviewer?
