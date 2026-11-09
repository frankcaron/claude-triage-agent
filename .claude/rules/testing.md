---
paths:
  - "tests/**"
---

# Testing rules

- Tests are offline: no API key, no network, no model calls. Replace `triage.run()` and `triage.ask_sre()` with fakes via `monkeypatch`.
- Point `triage.AUDIT` at `tmp_path` so a test never writes to the real audit/ folder.
- Pin `triage.THRESHOLD` in any test that depends on it, so an environment variable can't change the result.
- One behaviour per test. The test name says the behaviour, e.g. `test_score_at_threshold_takes_runbook_path`.
- Test boundaries on both sides: the exact cutoff and the value just below it.
- Data is synthetic only: `APP-SYN-*`, `LN-SYN-*`, `BA-SYN-*`.
- Never change core .py files in the main folder, `prompts/`, `runbooks/` or `incidents/` to make a test pass. If the code looks wrong, STOP and say so.
- Run `python -m pytest tests -q` and show the output before reporting done