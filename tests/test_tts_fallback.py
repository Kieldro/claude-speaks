"""
Fallback chain regression tests.

We exercise each TTS script's `speak()` and `fallback()` functions in-process
with mocks (no real network, no audio playback). The chain ordering is:
    elevenlabs -> openai -> edge -> system_voice
    openai -> edge -> system_voice
    edge -> system_voice
"""
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import elevenlabs_tts
import openai_tts
import edge_tts_speak
import system_voice_tts


# ---------- elevenlabs_tts.speak() ----------

def test_elevenlabs_speak_no_api_key(monkeypatch, clean_debug_logs):
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    assert elevenlabs_tts.speak("hi") is False


def test_elevenlabs_speak_http_error_returns_false(monkeypatch, clean_debug_logs):
    import urllib.error
    monkeypatch.setenv("ELEVENLABS_API_KEY", "bad-key")

    def fake_urlopen(*args, **kwargs):
        raise urllib.error.HTTPError(
            url="http://x", code=401, msg="unauth",
            hdrs=None, fp=MagicMock(read=lambda: b"unauthorized"),
        )

    monkeypatch.setattr(elevenlabs_tts.urllib.request, "urlopen", fake_urlopen)
    assert elevenlabs_tts.speak("hi") is False
    log = Path("/tmp/elevenlabs_tts_debug.log").read_text()
    assert "HTTPError" in log
    assert "401" in log


# ---------- openai_tts.speak() ----------

def test_openai_speak_no_api_key(monkeypatch, clean_debug_logs):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert openai_tts.speak("hi") is False
    log = Path("/tmp/openai_tts_debug.log").read_text()
    assert "no OPENAI_API_KEY" in log


def test_openai_speak_api_failure(monkeypatch, clean_debug_logs):
    monkeypatch.setenv("OPENAI_API_KEY", "bad-key")

    def fake_client(**kwargs):
        client = MagicMock()
        client.audio.speech.create.side_effect = RuntimeError("API down")
        return client

    with patch("openai.OpenAI", fake_client):
        assert openai_tts.speak("hi") is False
    log = Path("/tmp/openai_tts_debug.log").read_text()
    assert "FAIL" in log


# ---------- edge_tts.speak() ----------

def test_edge_speak_synthesis_failure(monkeypatch, clean_debug_logs):
    async def boom(text, voice, out_path):
        raise RuntimeError("network")

    monkeypatch.setattr(edge_tts_speak, "_synthesize", boom)
    assert edge_tts_speak.speak("hi") is False
    log = Path("/tmp/edge_tts_debug.log").read_text()
    assert "synthesis exception" in log


# ---------- fallback() chain wiring ----------

def _capture_fallback_subprocess_calls(monkeypatch):
    """Capture the script paths that fallback() invokes."""
    calls = []

    def fake_run(cmd, *args, **kwargs):
        # cmd = [sys.executable, str(script_path), message]
        calls.append(Path(cmd[1]).name)
        return SimpleNamespace(returncode=1, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


def test_elevenlabs_fallback_order(monkeypatch, clean_debug_logs):
    calls = _capture_fallback_subprocess_calls(monkeypatch)
    elevenlabs_tts.fallback("hi")
    assert calls == ["openai_tts.py", "edge_tts_speak.py", "system_voice_tts.py"]


def test_openai_fallback_order(monkeypatch, clean_debug_logs):
    calls = _capture_fallback_subprocess_calls(monkeypatch)
    openai_tts.fallback("hi")
    assert calls == ["edge_tts_speak.py", "system_voice_tts.py"]


def test_edge_fallback_order(monkeypatch, clean_debug_logs):
    calls = _capture_fallback_subprocess_calls(monkeypatch)
    edge_tts_speak.fallback("hi")
    assert calls == ["system_voice_tts.py"]


def test_elevenlabs_fallback_stops_on_success(monkeypatch, clean_debug_logs):
    """As soon as a fallback script returns 0, we stop trying further ones."""
    calls = []

    def fake_run(cmd, *args, **kwargs):
        calls.append(Path(cmd[1]).name)
        # First call (openai) succeeds.
        rc = 0 if "openai" in cmd[1] else 1
        return SimpleNamespace(returncode=rc, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    rc = elevenlabs_tts.fallback("hi")
    assert rc == 0
    assert calls == ["openai_tts.py"]


# ---------- system_voice_tts: nothing installed → returns False ----------

def test_system_voice_speak_all_missing(monkeypatch):
    """When say/spd-say/espeak all FileNotFoundError, speak() returns False."""
    def always_missing(*args, **kwargs):
        raise FileNotFoundError("not installed")
    monkeypatch.setattr(subprocess, "run", always_missing)
    assert system_voice_tts.speak("hi") is False


def test_system_voice_clamps_volume(monkeypatch):
    """TTS_VOLUME outside [-100, 100] should be clamped, invalid should default to 0."""
    captured = {}

    def fake_run(cmd, *args, **kwargs):
        captured["cmd"] = cmd
        if cmd[0] == "say":
            raise FileNotFoundError
        return SimpleNamespace(returncode=0)

    monkeypatch.setenv("TTS_VOLUME", "9999")
    monkeypatch.setattr(subprocess, "run", fake_run)
    system_voice_tts.speak("hi")
    # spd-say should be called with clamped volume "100"
    assert captured["cmd"][:3] == ["spd-say", "--volume", "100"]
