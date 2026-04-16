"""
Hook env propagation tests.

Verify response_summary.summarize_and_announce() spawns the right TTS script
with the model-specific voice in env (ELEVENLABS_VOICE_ID for opus/sonnet,
OPENAI_TTS_VOICE for haiku).
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

# response_summary lives at repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import response_summary

OPUS_ID = "Gfpl8Yo74Is0W6cPUWWT"
SONNET_ID = "EXAVITQu4vr4xnSDxMaL"


def _write_transcript(tmp_path: Path, model: str, text: str = "I added unit tests.") -> Path:
    path = tmp_path / "transcript.jsonl"
    entries = [
        {"type": "user", "message": {"role": "user", "content": "do work"}},
        {"type": "assistant", "message": {
            "role": "assistant", "model": model,
            "content": [{"type": "text", "text": text}],
        }},
    ]
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return path


@pytest.fixture
def captured_spawn(monkeypatch):
    """Capture the (cmd, env) that response_summary's TTS Popen receives.

    Also stubs the start-notification Popen and the LLM summarizer subprocess
    so the test runs offline and doesn't actually play audio.
    """
    captured = {}

    def fake_popen(cmd, *args, **kwargs):
        # The very first Popen is the start-notification (paplay/afplay).
        # Skip it; record only the TTS spawn.
        if "paplay" in cmd[0] or "afplay" in cmd[0]:
            return SimpleNamespace(pid=1)
        captured["cmd"] = cmd
        captured["env"] = kwargs.get("env", {})
        return SimpleNamespace(pid=2)

    def fake_run(cmd, *args, **kwargs):
        # The summarizer subprocess: pretend it returned a one-line summary.
        return SimpleNamespace(
            returncode=0,
            stdout="Added the unit tests successfully.\nmocked\n",
            stderr="",
        )

    monkeypatch.setattr(response_summary.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(response_summary.subprocess, "run", fake_run)
    # Skip the transcript-write polling delays so tests run fast.
    monkeypatch.setattr(response_summary.time, "sleep", lambda *_: None)
    return captured


def test_opus_routes_to_elevenlabs_with_max_voice(tmp_path, monkeypatch, captured_spawn):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")  # would normally win, but opus forces ElevenLabs
    transcript = _write_transcript(tmp_path, "claude-opus-4-6")

    metadata = response_summary.summarize_and_announce(str(transcript), cwd=str(tmp_path))

    assert metadata["tts_triggered"] is True
    assert "elevenlabs_tts.py" in captured_spawn["cmd"][0]
    assert captured_spawn["env"]["ELEVENLABS_VOICE_ID"] == OPUS_ID
    assert captured_spawn["env"]["ELEVENLABS_API_KEY"] == "test-key"
    assert metadata["voice_id"] == OPUS_ID


def test_sonnet_routes_to_elevenlabs_with_sarah_voice(tmp_path, monkeypatch, captured_spawn):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    transcript = _write_transcript(tmp_path, "claude-sonnet-4-6")

    response_summary.summarize_and_announce(str(transcript), cwd=str(tmp_path))

    assert "elevenlabs_tts.py" in captured_spawn["cmd"][0]
    assert captured_spawn["env"]["ELEVENLABS_VOICE_ID"] == SONNET_ID


def test_haiku_routes_to_openai_with_sage_voice(tmp_path, monkeypatch, captured_spawn):
    """Haiku has no ElevenLabs voice, so it should route to OpenAI with `sage`."""
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    transcript = _write_transcript(tmp_path, "claude-haiku-4-5-20251001")

    response_summary.summarize_and_announce(str(transcript), cwd=str(tmp_path))

    assert "openai_tts.py" in captured_spawn["cmd"][0]
    assert captured_spawn["env"]["OPENAI_TTS_VOICE"] == "sage"
    assert captured_spawn["env"]["OPENAI_API_KEY"] == "test-key"


def test_safe_env_includes_all_backend_keys_for_cascading_fallback(tmp_path, monkeypatch, captured_spawn):
    """All backend API keys + per-model voices must be in env so the
    fallback chain (eleven → openai → edge → system) can use the right
    voice at whichever level actually plays the audio."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "eleven-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    transcript = _write_transcript(tmp_path, "claude-opus-4-6")

    response_summary.summarize_and_announce(str(transcript), cwd=str(tmp_path))

    env = captured_spawn["env"]
    assert env.get("ELEVENLABS_API_KEY") == "eleven-key"
    assert env.get("OPENAI_API_KEY") == "openai-key"
    assert env.get("ELEVENLABS_VOICE_ID")  # Opus → Max
    assert env.get("OPENAI_TTS_VOICE") == "onyx"  # Opus fallback voice
    assert env.get("EDGE_TTS_VOICE") == "en-US-AndrewNeural"  # Opus edge voice


def test_safe_env_includes_pythonpath(tmp_path, monkeypatch, captured_spawn):
    """Regression guard: PYTHONPATH must be set so user-installed openai/edge_tts resolve."""
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    transcript = _write_transcript(tmp_path, "claude-haiku-4-5-20251001")

    response_summary.summarize_and_announce(str(transcript), cwd=str(tmp_path))

    assert captured_spawn["env"].get("PYTHONPATH"), "PYTHONPATH missing from spawned env"


def test_no_response_in_transcript_skips_tts(tmp_path, monkeypatch, captured_spawn):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    empty = tmp_path / "empty.jsonl"
    empty.write_text("")

    metadata = response_summary.summarize_and_announce(str(empty), cwd=str(tmp_path))
    assert metadata["tts_triggered"] is False
    assert "cmd" not in captured_spawn  # never spawned
