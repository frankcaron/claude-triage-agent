---
name: write-tests
description: Writes offline pytest tests for one behaviour of the triage agent. Use when asked to add, extend or fix tests.
argument-hint: "[behaviour to test]"
---

# Write tests

Behaviour to test: $ARGUMENTS

1. Read `tests/conftest.py` and any existing tests, then the part of `triage.py` that holds the behaviour.
2. Say in one sentence what you'll test and the one file you'll write, `tests/test_<topic>.py`.
   If it needs more than one new file, or any change outside tests/, STOP and ask first.
3. Write the tests, following the testing rules.
4. Don't run them. Reply with what each test checks, one line each, then the command to run them.
5. Offer a review by the test-reviewer agent.
