"""
Subprocess module-resolution regression tests.

The `response_summary.py` hook spawns each TTS script in a stripped `safe_env`.
A previous regression: `openai_tts.py` had a `#!/usr/bin/env -S uv run --script`
shebang that gave it an isolated venv hiding the system `openai` package.
This suite verifies each TTS script can resolve its required imports under
the same `safe_env` mapping.
"""
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import TTS_DIR, make_safe_env

# (script filename, module imports the script needs to resolve at startup)
SCRIPT_REQUIREMENTS = [
    ("elevenlabs_tts.py", ["urllib.request", "json", "subprocess"]),
    ("openai_tts.py", ["openai"]),
    ("edge_tts_speak.py", ["edge_tts", "asyncio"]),
    ("system_voice_tts.py", ["subprocess"]),
]


@pytest.mark.parametrize("script_name,modules", SCRIPT_REQUIREMENTS)
def test_script_imports_resolve_in_safe_env(script_name, modules):
    """Spawn `python3 -c "import <mods>"` with safe_env to ensure deps are findable."""
    script_path = TTS_DIR / script_name
    assert script_path.exists(), f"Missing script: {script_path}"

    safe_env = make_safe_env()
    import_line = "; ".join(f"import {m}" for m in modules)
    result = subprocess.run(
        [sys.executable, "-c", import_line],
        env=safe_env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, (
        f"Imports {modules} failed under safe_env. stderr={result.stderr}"
    )


@pytest.mark.parametrize("script_name,_modules", SCRIPT_REQUIREMENTS)
def test_script_executes_under_safe_env(script_name, _modules):
    """
    Spawn the actual script with no args under safe_env and verify it does
    not crash with ModuleNotFoundError. The script should exit (usually 1
    for "no message provided") rather than failing to start.
    """
    script_path = TTS_DIR / script_name
    safe_env = make_safe_env()
    result = subprocess.run(
        [sys.executable, str(script_path)],
        env=safe_env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    combined = (result.stdout + result.stderr).lower()
    assert "modulenotfounderror" not in combined, (
        f"{script_name} hit ModuleNotFoundError under safe_env: {result.stderr}"
    )
    assert "no module named" not in combined, (
        f"{script_name} import failed under safe_env: {result.stderr}"
    )


def test_no_uv_shebang_in_critical_scripts():
    """Regression guard: response_summary.py and openai_tts.py must not use uv shebang."""
    for path in [
        Path(__file__).resolve().parent.parent / "response_summary.py",
        TTS_DIR / "openai_tts.py",
    ]:
        first_line = path.read_text().splitlines()[0]
        assert "uv run" not in first_line, (
            f"{path.name} has a uv shebang ({first_line!r}) — this hides "
            f"system packages from spawned subprocesses."
        )
