#!/usr/bin/env python3
"""Select ElevenLabs voice based on which Claude model produced the transcript."""

import json
from pathlib import Path
from typing import Optional

MODEL_VOICE_MAP = {
    "opus": "qNkzaJoHLLdpvgh5tISm",    # Carter the Mountain King
    "sonnet": "EXAVITQu4vr4xnSDxMaL",  # Sarah — mature, reassuring, confident
    # haiku intentionally omitted — routes through OpenAI with sage voice below
}

# OpenAI TTS voices — used when no ElevenLabs override exists for the model
MODEL_OPENAI_VOICE_MAP = {
    "opus": "onyx",       # deep male
    "sonnet": "alloy",    # neutral
    "haiku": "nova",      # high-pitched female
}

# Edge TTS voices — free Microsoft neural voices, no quota
MODEL_EDGE_VOICE_MAP = {
    "opus": "en-US-AndrewNeural",   # warm, confident, authoritative
    "sonnet": "en-US-AvaNeural",    # expressive, caring, pleasant
    "haiku": "en-US-EmmaNeural",    # cheerful, clear, bright
}


def get_model_from_transcript(transcript_path: str) -> Optional[str]:
    path = Path(transcript_path)
    if not path.exists():
        return None
    try:
        with open(path, 'r') as f:
            lines = f.readlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            entry = json.loads(line.strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if entry.get('type') != 'assistant':
            continue
        model = entry.get('message', {}).get('model')
        if model:
            return model
    return None


def _lookup(model: Optional[str], mapping: dict) -> Optional[str]:
    if not model:
        return None
    model_lower = model.lower()
    for key, value in mapping.items():
        if key in model_lower:
            return value
    return None


def get_voice_id_for_model(model: Optional[str]) -> Optional[str]:
    return _lookup(model, MODEL_VOICE_MAP)


def get_openai_voice_for_model(model: Optional[str]) -> Optional[str]:
    return _lookup(model, MODEL_OPENAI_VOICE_MAP)


def get_edge_voice_for_model(model: Optional[str]) -> Optional[str]:
    return _lookup(model, MODEL_EDGE_VOICE_MAP)


def get_voice_id_for_transcript(transcript_path: Optional[str]) -> Optional[str]:
    if not transcript_path:
        return None
    return get_voice_id_for_model(get_model_from_transcript(transcript_path))


def get_openai_voice_for_transcript(transcript_path: Optional[str]) -> Optional[str]:
    if not transcript_path:
        return None
    return get_openai_voice_for_model(get_model_from_transcript(transcript_path))


def get_edge_voice_for_transcript(transcript_path: Optional[str]) -> Optional[str]:
    if not transcript_path:
        return None
    return get_edge_voice_for_model(get_model_from_transcript(transcript_path))


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        model = get_model_from_transcript(sys.argv[1])
        print(f"model={model} elevenlabs={get_voice_id_for_model(model)} openai={get_openai_voice_for_model(model)} edge={get_edge_voice_for_model(model)}")
