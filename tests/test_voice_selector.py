"""Voice selector unit tests."""
import json
from pathlib import Path

import pytest

from voice_selector import (
    get_openai_voice_for_model,
    get_openai_voice_for_transcript,
    get_voice_id_for_model,
    get_voice_id_for_transcript,
)

OPUS_ID = "Gfpl8Yo74Is0W6cPUWWT"
SONNET_ID = "EXAVITQu4vr4xnSDxMaL"


@pytest.mark.parametrize("model,expected", [
    ("claude-opus-4-6", OPUS_ID),
    ("claude-opus-4-5-20250930", OPUS_ID),
    ("claude-sonnet-4-6", SONNET_ID),
    ("claude-sonnet-4-5", SONNET_ID),
    ("claude-haiku-4-5-20251001", None),
    (None, None),
    ("", None),
    ("gpt-4", None),
])
def test_elevenlabs_voice_lookup(model, expected):
    assert get_voice_id_for_model(model) == expected


@pytest.mark.parametrize("model,expected", [
    ("claude-opus-4-6", "onyx"),
    ("claude-haiku-4-5-20251001", "sage"),
    ("claude-sonnet-4-6", None),
    (None, None),
])
def test_openai_voice_lookup(model, expected):
    assert get_openai_voice_for_model(model) == expected


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


def test_voice_for_transcript_sonnet(tmp_path):
    transcript = _write_transcript(tmp_path, "claude-sonnet-4-6")
    assert get_voice_id_for_transcript(str(transcript)) == SONNET_ID
    assert get_openai_voice_for_transcript(str(transcript)) is None


def test_voice_for_transcript_haiku(tmp_path):
    transcript = _write_transcript(tmp_path, "claude-haiku-4-5-20251001")
    assert get_voice_id_for_transcript(str(transcript)) is None
    assert get_openai_voice_for_transcript(str(transcript)) == "sage"


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
