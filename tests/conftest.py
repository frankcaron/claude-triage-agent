"""Shared offline fixtures: a triage module with run(), ask_sre() and AUDIT faked."""

import importlib
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent


def load_triage(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Import triage from the repo root, which it needs to read prompts/."""
    monkeypatch.chdir(ROOT)
    monkeypatch.syspath_prepend(str(ROOT))
    return importlib.import_module("triage")


@pytest.fixture
def triage_mod(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SimpleNamespace:
    """Return triage with audit to tmp_path, THRESHOLD pinned and model calls faked.

    Queue fake ResultMessage stand-ins (or None) on `.results`; an unqueued model
    call fails the test. Recorded SRE verdicts land in `.verdicts`.
    """
    triage = load_triage(monkeypatch)
    results: list = []
    verdicts: list[dict] = []

    async def fake_run(prompt: str, opts: object, show: bool = True) -> object:
        """Pop the next queued result instead of calling a model."""
        assert results, f"unexpected model call: {prompt[:60]}"
        return results.pop(0)

    def fake_ask_sre(
        incident: str, runbook: str, score: float, path: str, remediation: str
    ) -> None:
        """Record the verdict call instead of prompting a human."""
        verdicts.append({"runbook": runbook, "score": score, "path": path})

    monkeypatch.setattr(triage, "AUDIT", tmp_path / "audit.jsonl")
    monkeypatch.setattr(triage, "THRESHOLD", 0.7)
    monkeypatch.setattr(triage, "run", fake_run)
    monkeypatch.setattr(triage, "ask_sre", fake_ask_sre)
    return SimpleNamespace(module=triage, results=results, verdicts=verdicts)
