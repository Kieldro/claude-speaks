#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
#     "requests",
# ]
# ///
"""
Cached TTS Wrapper
Checks for cached audio files before generating new ones to save API costs and latency.
"""

import os
import sys
import hashlib
import subprocess
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.env')
except ImportError:
    pass


def get_cache_dir():
    """Get the cache directory path."""
    script_dir = Path(__file__).parent
    cache_dir = script_dir / "cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def get_cache_key(text):
    """Generate cache key from text using MD5 hash."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def get_cached_audio_path(text):
    """Get path to cached audio file for given text."""
    cache_dir = get_cache_dir()
    cache_key = get_cache_key(text)
    return cache_dir / f"{cache_key}.mp3"


def play_audio(audio_file):
    """Play audio file using available system player."""
    try:
        # macOS
        subprocess.run(['afplay', str(audio_file)], check=True, timeout=10)
        return True
    except (FileNotFoundError, subprocess.SubprocessError):
        try:
            # Linux with mpg123 (best for MP3)
            subprocess.run(['mpg123', '-q', str(audio_file)], check=True, timeout=10)
            return True
        except (FileNotFoundError, subprocess.SubprocessError):
            try:
                # Linux with ffplay (fallback)
                subprocess.run(['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', str(audio_file)],
                             check=True, timeout=10,
                             stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)
                return True
            except (FileNotFoundError, subprocess.SubprocessError):
                return False


def get_tts_script_path():
    """
    Determine which TTS script to use based on available API keys.
    Priority order: ElevenLabs > OpenAI > system voice (spd-say/espeak)
    """
    script_dir = Path(__file__).parent

    # Check for ElevenLabs API key (highest priority)
    if os.getenv('ELEVENLABS_API_KEY'):
        elevenlabs_script = script_dir / "elevenlabs_tts.py"
        if elevenlabs_script.exists():
            return str(elevenlabs_script)

    # Check for OpenAI API key (second priority)
    if os.getenv('OPENAI_API_KEY'):
        openai_script = script_dir / "openai_tts.py"
        if openai_script.exists():
            return str(openai_script)

    # Fall back to system voice (no API key required)
    system_voice_script = script_dir / "system_voice_tts.py"
    if system_voice_script.exists():
        return str(system_voice_script)

    return None


def generate_and_cache_audio(text, audio_path):
    """
    Generate audio using TTS service and save to cache.
    Only ElevenLabs supports caching (returns MP3 data).
    """
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        return False

    try:
        import requests

        # Get voice ID from environment variable or use default
        # Popular voices:
        # - 21m00Tcm4TlvDq8ikWAM: Rachel - Professional female (default)
        # - goT3UYdM9bhm0n2lmKQx: Edward - British, Dark, Seductive, Low
        # - ZF6FPAbjXT4488VcRRnw: Amelia - British
        voice_id = os.getenv('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": api_key
        }

        data = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }

        response = requests.post(url, json=data, headers=headers, timeout=10)

        if response.status_code == 200:
            # Save audio to cache
            with open(audio_path, 'wb') as f:
                f.write(response.content)
            return True
        else:
            return False

    except Exception:
        return False


def speak_with_cache(text):
    """
    Speak text using cached audio if available, otherwise generate and cache.
    Falls back to non-cached TTS if caching is not supported.
    """
    # Get cached audio path
    cached_audio = get_cached_audio_path(text)

    # Check if cached audio exists
    if cached_audio.exists():
        # Play cached audio
        return play_audio(cached_audio)

    # Check if we can cache (ElevenLabs only)
    if os.getenv('ELEVENLABS_API_KEY'):
        # Generate and cache audio
        if generate_and_cache_audio(text, cached_audio):
            return play_audio(cached_audio)

    # Fall back to regular TTS (no caching for OpenAI/system voice)
    tts_script = get_tts_script_path()
    if tts_script:
        try:
            subprocess.run(
                ['python3', tts_script, text],
                capture_output=True,
                timeout=10
            )
            return True
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            return False

    return False


if __name__ == '__main__':
    if len(sys.argv) > 1:
        message = ' '.join(sys.argv[1:])
        if speak_with_cache(message):
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        sys.exit(1)
