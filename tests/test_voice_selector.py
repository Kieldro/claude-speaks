"""Voice selector unit tests."""
import json
from pathlib import Path

import pytest

from voice_selector import (
    get_cartesia_voice_for_model,
    get_cartesia_voice_for_transcript,
    get_edge_voice_for_model,
    get_openai_voice_for_model,
    get_openai_voice_for_transcript,
    get_voice_id_for_model,
    get_voice_id_for_transcript,
)

# ElevenLabs
OPUS_ID = "qNkzaJoHLLdpvgh5tISm"    # Carter the Mountain King
SONNET_ID = "EXAVITQu4vr4xnSDxMaL"  # Sarah

# Cartesia (primary provider)
CARTESIA_OPUS = "ec58877e-44ae-4581-9078-a04225d42bd4"    # Charles - Heroic Man
CARTESIA_SONNET = "bf0a246a-8642-498a-9950-80c35e9276b5"  # Sophie - Teacher
CARTESIA_HAIKU = "58fbaf73-d7de-4e82-a6b3-118180e7057c"   # Janet - Sunny Speaker
CARTESIA_FABLE = "87748186-23bb-4158-a1eb-332911b0b708"   # Alaric - Wizard


@pytest.mark.parametrize("model,expected", [
    ("claude-opus-4-6", OPUS_ID),
    ("claude-opus-4-5-20250930", OPUS_ID),
    ("claude-sonnet-4-6", SONNET_ID),
    ("claude-sonnet-4-5", SONNET_ID),
    ("claude-haiku-4-5-20251001", None),  # intentionally omitted — OpenAI handles it
    ("claude-fable-5", None),             # intentionally omitted — OpenAI handles it
    (None, None),
    ("", None),
    ("gpt-4", None),
])
def test_elevenlabs_voice_lookup(model, expected):
    assert get_voice_id_for_model(model) == expected


@pytest.mark.parametrize("model,expected", [
    ("claude-opus-4-6", "onyx"),
    ("claude-sonnet-4-6", "alloy"),
    ("claude-haiku-4-5-20251001", "nova"),
    ("claude-fable-5", "fable"),
    (None, None),
])
def test_openai_voice_lookup(model, expected):
    assert get_openai_voice_for_model(model) == expected


@pytest.mark.parametrize("model,expected", [
    ("claude-opus-4-6", CARTESIA_OPUS),
    ("claude-sonnet-4-6", CARTESIA_SONNET),
    ("claude-haiku-4-5-20251001", CARTESIA_HAIKU),
    ("claude-fable-5", CARTESIA_FABLE),
    ("gpt-4", None),
    (None, None),
])
def test_cartesia_voice_lookup(model, expected):
    assert get_cartesia_voice_for_model(model) == expected


@pytest.mark.parametrize("model,expected", [
    ("claude-opus-4-6", "en-US-AndrewNeural"),
    ("claude-sonnet-4-6", "en-US-AvaNeural"),
    ("claude-haiku-4-5-20251001", "en-US-EmmaNeural"),
    ("claude-fable-5", "en-GB-RyanNeural"),
    (None, None),
])
def test_edge_voice_lookup(model, expected):
    assert get_edge_voice_for_model(model) == expected


def _write_transcript(tmp_path: Path, model: str) -> Path:
    transcript = tmp_path / "transcript.jsonl"
    entries = [
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {"type": "assistant", "message": {"role": "assistant", "model": model,
                                          "content": [{"type": "text", "text": "hello"}]}},
    ]
    with open(transcript, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    return transcript


def test_voice_for_transcript_opus(tmp_path):
    transcript = _write_transcript(tmp_path, "claude-opus-4-6")
    assert get_voice_id_for_transcript(str(transcript)) == OPUS_ID
    assert get_openai_voice_for_transcript(str(transcript)) == "onyx"
    assert get_cartesia_voice_for_transcript(str(transcript)) == CARTESIA_OPUS


def test_voice_for_transcript_sonnet(tmp_path):
    transcript = _write_transcript(tmp_path, "claude-sonnet-4-6")
    assert get_voice_id_for_transcript(str(transcript)) == SONNET_ID
    assert get_openai_voice_for_transcript(str(transcript)) == "alloy"
    assert get_cartesia_voice_for_transcript(str(transcript)) == CARTESIA_SONNET


def test_voice_for_transcript_haiku(tmp_path):
    transcript = _write_transcript(tmp_path, "claude-haiku-4-5-20251001")
    assert get_voice_id_for_transcript(str(transcript)) is None
    assert get_openai_voice_for_transcript(str(transcript)) == "nova"
    assert get_cartesia_voice_for_transcript(str(transcript)) == CARTESIA_HAIKU


def test_voice_for_transcript_fable(tmp_path):
    transcript = _write_transcript(tmp_path, "claude-fable-5")
    assert get_voice_id_for_transcript(str(transcript)) is None
    assert get_openai_voice_for_transcript(str(transcript)) == "fable"
    assert get_cartesia_voice_for_transcript(str(transcript)) == CARTESIA_FABLE


def test_voice_for_transcript_missing_file():
    assert get_voice_id_for_transcript("/nonexistent/path.jsonl") is None
    assert get_voice_id_for_transcript(None) is None


def test_voice_for_transcript_uses_last_assistant(tmp_path):
    """Last-wins: most recent assistant entry's model should determine the voice."""
    transcript = tmp_path / "mixed.jsonl"
    entries = [
        {"type": "assistant", "message": {"role": "assistant", "model": "claude-haiku-4-5"}},
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {"type": "assistant", "message": {"role": "assistant", "model": "claude-opus-4-6"}},
    ]
    with open(transcript, "w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")
    assert get_voice_id_for_transcript(str(transcript)) == OPUS_ID
