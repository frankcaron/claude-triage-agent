---
paths:
  - "**/*.py"
---

# Python rules

- Type hints on every function signature, return type included.
- A one-line docstring on every new function: what it does, not how.
- Small functions: one job each, about 25 lines at most. Split rather than nest.
- New behaviour ships with a test in tests/ in the same change. Test rules are in [testing.md](testing.md).
- Run `ruff format` and `ruff check` on files you create. In existing files, match the surrounding style and don't touch lines the change doesn't need.
- No secrets in code. Read keys from `os.environ`. A hook blocks key-shaped strings anyway.
- No new dependencies. If the change needs one, STOP and ask.
- Data in code, comments and tests is synthetic only (`APP-SYN-*`, `LN-SYN-*`, `BA-SYN-*`).