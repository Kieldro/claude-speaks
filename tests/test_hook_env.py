"""
Hook env propagation tests.

Verify response_summary.summarize_and_announce() spawns the right TTS script
with the model-specific voice in env. Routing preference is
Cartesia (when CARTESIA_API_KEY is set) → ElevenLabs → OpenAI → edge.
Each test pins the relevant API keys so results don't depend on ~/.env.
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

OPUS_ID = "qNkzaJoHLLdpvgh5tISm"    # Carter the Mountain King
SONNET_ID = "EXAVITQu4vr4xnSDxMaL"  # Sarah
CARTESIA_OPUS = "ec58877e-44ae-4581-9078-a04225d42bd4"   # Charles - Heroic Man
CARTESIA_FABLE = "87748186-23bb-4158-a1eb-332911b0b708"  # Alaric - Wizard


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


def test_opus_routes_to_cartesia_when_key_present(tmp_path, monkeypatch, captured_spawn):
    monkeypatch.setenv("CARTESIA_API_KEY", "test-key")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    transcript = _write_transcript(tmp_path, "claude-opus-4-6")

    metadata = response_summary.summarize_and_announce(str(transcript), cwd=str(tmp_path))

    assert metadata["tts_triggered"] is True
    assert "cartesia_tts.py" in captured_spawn["cmd"][0]
    assert captured_spawn["env"]["CARTESIA_VOICE_ID"] == CARTESIA_OPUS
    assert metadata["voice_id"] == CARTESIA_OPUS


def test_fable_routes_to_cartesia_with_wizard_voice(tmp_path, monkeypatch, captured_spawn):
    monkeypatch.setenv("CARTESIA_API_KEY", "test-key")
    transcript = _write_transcript(tmp_path, "claude-fable-5")

    metadata = response_summary.summarize_and_announce(str(transcript), cwd=str(tmp_path))

    assert metadata["tts_triggered"] is True
    assert "cartesia_tts.py" in captured_spawn["cmd"][0]
    assert captured_spawn["env"]["CARTESIA_VOICE_ID"] == CARTESIA_FABLE
    # Fallback voices for the rest of the chain
    assert captured_spawn["env"]["OPENAI_TTS_VOICE"] == "fable"
    assert captured_spawn["env"]["EDGE_TTS_VOICE"] == "en-GB-RyanNeural"
    assert metadata["voice_id"] == CARTESIA_FABLE


def test_opus_routes_to_elevenlabs_without_cartesia_key(tmp_path, monkeypatch, captured_spawn):
    monkeypatch.delenv("CARTESIA_API_KEY", raising=False)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")  # would normally win, but opus forces ElevenLabs
    transcript = _write_transcript(tmp_path, "claude-opus-4-6")

    metadata = response_summary.summarize_and_announce(str(transcript), cwd=str(tmp_path))

    assert metadata["tts_triggered"] is True
    assert "elevenlabs_tts.py" in captured_spawn["cmd"][0]
    assert captured_spawn["env"]["ELEVENLABS_VOICE_ID"] == OPUS_ID
    assert captured_spawn["env"]["ELEVENLABS_API_KEY"] == "test-key"
    assert metadata["voice_id"] == OPUS_ID


def test_sonnet_routes_to_elevenlabs_without_cartesia_key(tmp_path, monkeypatch, captured_spawn):
    monkeypatch.delenv("CARTESIA_API_KEY", raising=False)
    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    transcript = _write_transcript(tmp_path, "claude-sonnet-4-6")

    response_summary.summarize_and_announce(str(transcript), cwd=str(tmp_path))

    assert "elevenlabs_tts.py" in captured_spawn["cmd"][0]
    assert captured_spawn["env"]["ELEVENLABS_VOICE_ID"] == SONNET_ID


def test_haiku_routes_to_openai_with_nova_voice(tmp_path, monkeypatch, captured_spawn):
    """Haiku has no ElevenLabs voice; without Cartesia it routes to OpenAI with `nova`."""
    monkeypatch.delenv("CARTESIA_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    transcript = _write_transcript(tmp_path, "claude-haiku-4-5-20251001")

    response_summary.summarize_and_announce(str(transcript), cwd=str(tmp_path))

    assert "openai_tts.py" in captured_spawn["cmd"][0]
    assert captured_spawn["env"]["OPENAI_TTS_VOICE"] == "nova"
    assert captured_spawn["env"]["OPENAI_API_KEY"] == "test-key"


def test_fable_routes_to_openai_with_fable_voice(tmp_path, monkeypatch, captured_spawn):
    """Fable has no ElevenLabs voice; without Cartesia it routes to OpenAI with `fable`."""
    monkeypatch.delenv("CARTESIA_API_KEY", raising=False)
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    transcript = _write_transcript(tmp_path, "claude-fable-5")

    response_summary.summarize_and_announce(str(transcript), cwd=str(tmp_path))

    assert "openai_tts.py" in captured_spawn["cmd"][0]
    assert captured_spawn["env"]["OPENAI_TTS_VOICE"] == "fable"


def test_safe_env_includes_all_backend_keys_for_cascading_fallback(tmp_path, monkeypatch, captured_spawn):
    """All backend API keys + per-model voices must be in env so the
    fallback chain (cartesia → eleven → openai → edge → system) can use the
    right voice at whichever level actually plays the audio."""
    monkeypatch.setenv("CARTESIA_API_KEY", "cartesia-key")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "eleven-key")
    monkeypatch.setenv("OPENAI_API_KEY", "openai-key")
    transcript = _write_transcript(tmp_path, "claude-opus-4-6")

    response_summary.summarize_and_announce(str(transcript), cwd=str(tmp_path))

    env = captured_spawn["env"]
    assert env.get("CARTESIA_API_KEY") == "cartesia-key"
    assert env.get("ELEVENLABS_API_KEY") == "eleven-key"
    assert env.get("OPENAI_API_KEY") == "openai-key"
    assert env.get("CARTESIA_VOICE_ID") == CARTESIA_OPUS
    assert env.get("ELEVENLABS_VOICE_ID") == OPUS_ID
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
