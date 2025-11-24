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

# Default voice ID (Edward from ElevenLabs)
DEFAULT_VOICE_ID = 'goT3UYdM9bhm0n2lmKQx'


def get_cache_dir():
    """Get the cache directory path for the current voice."""
    script_dir = Path(__file__).parent
    base_cache_dir = script_dir / "cache"

    # Get voice ID from environment or use default
    voice_id = os.getenv('ELEVENLABS_VOICE_ID', DEFAULT_VOICE_ID)

    # Create voice-specific subdirectory
    voice_cache_dir = base_cache_dir / voice_id
    voice_cache_dir.mkdir(parents=True, exist_ok=True)
    return voice_cache_dir


def get_cache_key(text):
    """Generate cache key from text using MD5 hash."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def get_cached_audio_path(text):
    """Get path to cached audio file for given text and current voice."""
    cache_dir = get_cache_dir()
    cache_key = get_cache_key(text)
    return cache_dir / f"{cache_key}.mp3"


def play_audio(audio_file):
    """Play audio file using available system player (non-blocking)."""
    # Preserve audio environment variables for PipeWire/PulseAudio
    env = os.environ.copy()

    try:
        # macOS - spawn in background to avoid blocking
        subprocess.Popen(
            ['afplay', str(audio_file)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env
        )
        return True
    except FileNotFoundError:
        try:
            # Linux with ffplay (primary - works with PipeWire)
            subprocess.Popen(
                ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'error', '-volume', '100', str(audio_file)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env
            )
            return True
        except FileNotFoundError:
            try:
                # Linux with mpg123 (fallback)
                subprocess.Popen(
                    ['mpg123', '-q', str(audio_file)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env
                )
                return True
            except FileNotFoundError:
                return False


def get_tts_script_path():
    """
    Determine which TTS script to use based on available API keys.
    Priority order: OpenAI > ElevenLabs > system voice (spd-say/espeak)
    """
    script_dir = Path(__file__).parent

    # Check for OpenAI API key (highest priority - fastest and cheapest)
    if os.getenv('OPENAI_API_KEY'):
        openai_script = script_dir / "openai_tts.py"
        if openai_script.exists():
            return str(openai_script)

    # Check for ElevenLabs API key (second priority - higher quality but more expensive)
    if os.getenv('ELEVENLABS_API_KEY'):
        elevenlabs_script = script_dir / "elevenlabs_tts.py"
        if elevenlabs_script.exists():
            return str(elevenlabs_script)

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
        # See README.md for available voice IDs
        voice_id = os.getenv('ELEVENLABS_VOICE_ID', DEFAULT_VOICE_ID)
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


def speak_with_cache(text, verbose=False):
    """
    Speak text using cached audio if available, otherwise generate and cache.
    Falls back to non-cached TTS if caching is not supported.
    Returns dict with metadata for logging.
    """
    result = {
        "cache_hit": False,
        "cache_file": None,
        "tts_backend": None,
        "voice_id": None,
        "fallback_used": False
    }

    # Get cached audio path
    cached_audio = get_cached_audio_path(text)
    result["cache_file"] = str(cached_audio)

    # Check if cached audio exists
    if cached_audio.exists():
        # Extract voice ID from cache path (cache/{voice_id}/hash.mp3)
        # This reflects the actual voice used, not the current env var
        result["voice_id"] = cached_audio.parent.name
        result["cache_hit"] = True
        result["tts_backend"] = "cache"
        if play_audio(cached_audio):
            return result
        # If playback failed, continue to regenerate

    # Check if we can cache (ElevenLabs only)
    elevenlabs_success = False
    if os.getenv('ELEVENLABS_API_KEY'):
        voice_id = os.getenv('ELEVENLABS_VOICE_ID', DEFAULT_VOICE_ID)
        result["tts_backend"] = "elevenlabs"
        result["voice_id"] = voice_id
        # Generate and cache audio
        if generate_and_cache_audio(text, cached_audio):
            if play_audio(cached_audio):
                elevenlabs_success = True
                return result

    # Fall back to regular TTS if ElevenLabs failed or unavailable
    if not elevenlabs_success:
        result["fallback_used"] = True
        tts_script = get_tts_script_path()
        if tts_script:
            result["tts_backend"] = Path(tts_script).stem
            try:
                # Run TTS script synchronously to ensure completion
                subprocess.run(
                    [sys.executable, tts_script, text],
                    capture_output=True,
                    timeout=5,
                    check=False
                )
                return result
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass

    return result


if __name__ == '__main__':
    if len(sys.argv) > 1:
        # Check for --json flag
        output_json = '--json' in sys.argv

        # Filter out --json flag from arguments to get the actual message
        message_args = [arg for arg in sys.argv[1:] if arg != '--json']
        message = ' '.join(message_args)

        result = speak_with_cache(message, verbose=True)

        # Output metadata as JSON for parent process to capture
        if output_json:
            import json
            print(json.dumps(result))
        sys.exit(0 if result.get("tts_backend") else 1)
    else:
        sys.exit(1)
