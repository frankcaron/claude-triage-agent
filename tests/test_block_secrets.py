"""The org secrets hook blocks key-shaped strings on every tool it is matched to."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
HOOK = ROOT / "org-policy" / "hooks" / "block_secrets.py"
SETTINGS = ROOT / "org-policy" / "managed-settings.json"

# Every key-shaped value is built from pieces so this file never holds a literal
# one (the live hook would block writing it). All are synthetic.
FAKE_KEY = "sk-" + "ant-" + "SYNTHETICTESTKEY0000"  # 20 chars after the prefix
FAKE_AWS = "AK" + "IA" + "SYNTHETIC0000000"  # 16 chars after the prefix
FAKE_PEM = "-----BEGIN " + "RSA PRIVATE KEY-----"


def credential(name: str, value: str, quote: str = "'") -> str:
    """Build a `name = 'value'` assignment without writing one literally."""
    return name + " = " + quote + value + quote


def run_hook(stdin: str) -> subprocess.CompletedProcess:
    """Run the hook with raw stdin and return the finished process."""
    return subprocess.run(
        [sys.executable, str(HOOK)],
        check=False,
        input=stdin,
        capture_output=True,
        text=True,
    )


def run_tool(tool_input: object) -> subprocess.CompletedProcess:
    """Run the hook on a PreToolUse payload carrying this tool_input."""
    return run_hook(json.dumps({"tool_input": tool_input}))


@pytest.mark.parametrize(
    "tool_input",
    [
        {"file_path": "a.py", "content": FAKE_KEY},
        {"file_path": "a.py", "old_string": "x", "new_string": FAKE_KEY},
        {"file_path": "a.py", "edits": [{"old_string": "x", "new_string": FAKE_KEY}]},
        {"notebook_path": "n.ipynb", "new_source": FAKE_KEY},
        {"command": f"echo {FAKE_KEY} > config.py"},
    ],
    ids=["write", "edit", "multiedit", "notebookedit", "bash"],
)
def test_hook_blocks_key_on_each_tool_shape(tool_input: dict) -> None:
    result = run_tool(tool_input)
    assert result.returncode == 2
    assert "Blocked by org policy" in result.stderr


SECRETS = [
    (FAKE_KEY, "Anthropic API key"),
    (FAKE_AWS, "AWS access key"),
    (FAKE_PEM, "private key"),
    (credential("password", "SYNTHETICPW12"), "hard-coded credential"),
]
SECRET_IDS = ["anthropic", "aws", "private-key", "password"]


@pytest.mark.parametrize(("secret", "kind"), SECRETS, ids=SECRET_IDS)
def test_bash_block_names_kind_and_shell_target(secret: str, kind: str) -> None:
    result = run_tool({"command": f"echo {secret}"})
    assert result.returncode == 2
    assert f"contains a {kind} (target: a shell command)" in result.stderr


def test_notebook_block_names_notebook_path_as_target() -> None:
    result = run_tool({"notebook_path": "n.ipynb", "new_source": FAKE_KEY})
    assert "target: n.ipynb" in result.stderr


def test_file_block_names_file_path_as_target() -> None:
    result = run_tool({"file_path": "a.py", "content": FAKE_KEY})
    assert "target: a.py" in result.stderr


@pytest.mark.parametrize(("secret", "kind"), SECRETS, ids=SECRET_IDS)
def test_block_message_never_echoes_the_secret(secret: str, kind: str) -> None:
    value = secret.split("'")[1] if "'" in secret else secret
    result = run_tool({"command": f"echo {secret}"})
    assert result.returncode == 2
    assert result.stderr
    assert value not in result.stderr


@pytest.mark.parametrize(
    "tool_input",
    [
        {"command": "python -m pytest tests -q"},
        {"command": "git status"},
        {"command": "export " + credential("TOKEN", "$(gh auth token)", '"')},
        {"command": credential("PASSWORD", "$DB_PASS_VALUE", '"') + " ./run.sh"},
        {
            "notebook_path": "n.ipynb",
            "new_source": "x = os.environ['ANTHROPIC_API_KEY']",
        },
    ],
    ids=["pytest", "git", "export-from-cmd", "password-from-env", "notebook-environ"],
)
def test_hook_allows_clean_input(tool_input: dict) -> None:
    result = run_tool(tool_input)
    assert result.returncode == 0
    assert result.stderr == ""


@pytest.mark.parametrize("name", ["auth_token", "DB_PASSWORD", "client_secret"])
def test_prefixed_credential_names_are_blocked(name: str) -> None:
    result = run_tool({"command": credential(name, "x" * 12)})
    assert result.returncode == 2


def test_credential_value_at_minimum_length_is_blocked() -> None:
    assert run_tool({"command": credential("password", "x" * 12)}).returncode == 2


def test_credential_value_one_char_short_is_allowed() -> None:
    assert run_tool({"command": credential("password", "x" * 11)}).returncode == 0


def test_key_at_minimum_length_is_blocked() -> None:
    result = run_tool({"command": "echo " + FAKE_KEY[:-4]})  # 16 chars after prefix
    assert result.returncode == 2


def test_key_one_char_short_is_allowed() -> None:
    result = run_tool({"command": "echo " + FAKE_KEY[:-5]})  # 15 chars after prefix
    assert result.returncode == 0


def test_aws_key_one_char_short_is_allowed() -> None:
    assert run_tool({"command": "echo " + FAKE_AWS[:-1]}).returncode == 0


@pytest.mark.parametrize(
    "stdin",
    [
        "not json",
        json.dumps(["a list"]),
        json.dumps({"tool_input": "a string"}),
        "[" * 100_000 + "]" * 100_000,  # RecursionError in json.load
    ],
    ids=["malformed", "list-payload", "string-tool-input", "deeply-nested"],
)
def test_unreadable_input_fails_closed(stdin: str) -> None:
    result = run_hook(stdin)
    assert result.returncode == 2
    assert "could not read" in result.stderr


@pytest.mark.parametrize(
    "stdin",
    [
        json.dumps({}),
        json.dumps({"tool_input": {"file_path": "a.py", "edits": None}}),
    ],
    ids=["no-tool-input", "edits-null"],
)
def test_empty_input_is_allowed(stdin: str) -> None:
    assert run_hook(stdin).returncode == 0


def test_non_dict_edit_entries_are_skipped() -> None:
    result = run_tool(
        {"file_path": "a.py", "edits": ["junk", None, {"new_string": "ok"}]}
    )
    assert result.returncode == 0
    assert result.stderr == ""


def test_dict_edit_entry_with_key_is_still_scanned_beside_junk() -> None:
    edits = ["junk", None, {"new_string": FAKE_KEY}]
    result = run_tool({"file_path": "a.py", "edits": edits})
    assert result.returncode == 2
    assert "Anthropic API key" in result.stderr


def test_managed_matcher_covers_every_scanned_tool() -> None:
    entries = json.loads(SETTINGS.read_text())["hooks"]["PreToolUse"]
    hook_entry = next(
        e
        for e in entries
        if any("block_secrets.py" in h["command"] for h in e["hooks"])
    )
    tools = set(hook_entry["matcher"].split("|"))
    assert tools >= {"Edit", "Write", "MultiEdit", "NotebookEdit", "Bash"}


@pytest.mark.parametrize(
    "rule",
    [
        "Bash(* .env)",
        "Bash(* .env.*)",
        "Bash(*/.env*)",
        "Bash(* <.env*)",
        "Bash(*secrets/*)",
    ],
)
def test_managed_settings_deny_secret_reads_through_bash(rule: str) -> None:
    deny = json.loads(SETTINGS.read_text())["permissions"]["deny"]
    assert rule in deny
