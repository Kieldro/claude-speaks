#!/usr/bin/env python3
"""Select ElevenLabs voice based on which Claude model produced the transcript."""

import json
from pathlib import Path
from typing import Optional

MODEL_VOICE_MAP = {
    "opus": "Gfpl8Yo74Is0W6cPUWWT",   # Max
    "haiku": "cgSgspJ2msm6clMCkdW9",  # Jessica
}

# OpenAI TTS voices — onyx is deep/commanding, shimmer is bright/high
MODEL_OPENAI_VOICE_MAP = {
    "opus": "onyx",
    "haiku": "shimmer",
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


def get_voice_id_for_transcript(transcript_path: Optional[str]) -> Optional[str]:
    if not transcript_path:
        return None
    return get_voice_id_for_model(get_model_from_transcript(transcript_path))


def get_openai_voice_for_transcript(transcript_path: Optional[str]) -> Optional[str]:
    if not transcript_path:
        return None
    return get_openai_voice_for_model(get_model_from_transcript(transcript_path))


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        model = get_model_from_transcript(sys.argv[1])
        print(f"model={model} elevenlabs={get_voice_id_for_model(model)} openai={get_openai_voice_for_model(model)}")
