# Intent: agentic triage agent
Author: Frank Caron (frankcaron.com). Status: demo.

## Problem
Our SRE teams spend manual time reviewing logs and assessing an incident when monitors fire. A lot of this work is wrote, and while they've automated some, they haven't automated all — and that on-call hands on traige time takes away from preventative care that prevents on-call work in the first place.

## Proposed outcome
SRE no longer has to be on front-line triage, first acting as an approval gate but eventually focusing exclusively on eval reviews and iteration in partnership with Claude Code.

## Affected users and systems
SRE team, end users, all production systems

## Constraints
Logs and log processing, as well as triage, should protect consumer PII and any action on consumer data should adhere to the guardrails outlined within the project.

## Open questions
What incidents triage scenarios could we never fully automate?