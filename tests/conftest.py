"""Shared pytest fixtures and helpers."""
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
UTILS_DIR = REPO_ROOT / "utils"
TTS_DIR = UTILS_DIR / "tts"

# Make repo modules importable.
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(UTILS_DIR))
sys.path.insert(0, str(TTS_DIR))

TTS_CHAIN_LOG = Path("/tmp/tts_chain.log")
DEBUG_LOGS = [
    TTS_CHAIN_LOG,
    Path("/tmp/response_summary_debug.log"),
]


@pytest.fixture
def clean_debug_logs():
    """Clear all TTS debug logs before/after each test."""
    for log in DEBUG_LOGS:
        if log.exists():
            log.unlink()
    yield
    # Leave logs in place after the test for post-mortem.


@pytest.fixture
def repo_root():
    return REPO_ROOT


@pytest.fixture
def tts_dir():
    return TTS_DIR


def make_safe_env(extra=None):
    """Mirror the safe_env response_summary.py builds for spawned TTS subprocesses."""
    import site
    python_path = ":".join([site.getusersitepackages()] + site.getsitepackages())
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": os.environ.get("HOME", ""),
        "USER": os.environ.get("USER", ""),
        "TMPDIR": os.environ.get("TMPDIR", "/tmp"),
        "TTS_VOLUME": "0",
        "PYTHONPATH": python_path,
        "TERM": "xterm-256color",
        "XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", ""),
        "DBUS_SESSION_BUS_ADDRESS": os.environ.get("DBUS_SESSION_BUS_ADDRESS", ""),
    }
    if extra:
        env.update(extra)
    return env
