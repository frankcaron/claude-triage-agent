---
name: write-code
description: Adds or changes Python code in this repo, with a test, then formats, lints and tests it. Use when asked to add a feature, fix a bug or refactor.
argument-hint: "[change to make]"
---

# Write code

Change: $ARGUMENTS

1. Understand the change requested and the context in the code. 
    Ask discovery questions against requirements before outright attempting a fix. Work to ascertain how the code is meant to function relative to the bigger business context around the application.
2. Read the code you'll touch. Say in two lines what you'll change and which files.
    If the change touches prompts/, runbooks/, incidents/ or .claude/, or needs a new dependency, STOP and ask first.
3. Make the smallest change that does it, following the Python rules.
4. Add a test in tests/ for the new behaviour, following the testing rules.
5. Run `ruff format <new files>`, `ruff check <new files>` and `python -m pytest tests -q`. Fix the code, not the test, until they pass. Three failed tries: STOP and show the failure.
6. Run the code-reviewer agent on the changed code outside tests/, passing each file and its changed lines. Show its findings and suggested fixes. Don't apply them without the human's OK.
7. Then run the test-reviewer agent on the tests you added, passing along any behaviours code-reviewer said the tests should cover.
8. Reply with one line per file changed, the test result and both reviews. Don't commit or push. The human reviews the diff.