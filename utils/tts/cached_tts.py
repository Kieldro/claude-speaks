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


def get_cache_dir(backend: str = None, voice: str = None):
    """Get cache dir for a specific backend+voice (or current env defaults)."""
    script_dir = Path(__file__).parent
    base = script_dir / "cache"

    if backend == 'openai':
        voice = voice or os.getenv('OPENAI_TTS_VOICE', 'nova')
        sub = f'openai-{voice}'
    else:
        voice = voice or os.getenv('ELEVENLABS_VOICE_ID', DEFAULT_VOICE_ID)
        sub = voice

    d = base / sub
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_cache_key(text):
    """Generate cache key from text using MD5 hash."""
    return hashlib.md5(text.encode('utf-8')).hexdigest()


def get_cached_audio_path(text, backend: str = None, voice: str = None):
    """Get path to cached audio for given text+backend+voice."""
    cache_dir = get_cache_dir(backend, voice)
    return cache_dir / f"{get_cache_key(text)}.mp3"


def generate_openai_audio(text, audio_path, voice):
    """Generate audio via OpenAI TTS and save to cache. Returns True on success."""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return False
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        response = client.audio.speech.create(model='tts-1-hd', voice=voice, input=text)
        with open(audio_path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception:
        return False


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
    """Speak text via cache → OpenAI (generating + caching on miss) → ElevenLabs fallback."""
    result = {
        "cache_hit": False,
        "cache_file": None,
        "tts_backend": None,
        "voice_id": None,
        "fallback_used": False,
    }

    # Check ElevenLabs voice cache first (legacy pre-generated content)
    eleven_cached = get_cached_audio_path(text, backend='elevenlabs')
    if eleven_cached.exists():
        result.update(cache_file=str(eleven_cached), cache_hit=True,
                      tts_backend='cache', voice_id=eleven_cached.parent.name)
        if play_audio(eleven_cached):
            _log_tts_call(text, result)
            return result

    # Check OpenAI voice cache
    openai_voice = os.getenv('OPENAI_TTS_VOICE', 'nova')
    openai_cached = get_cached_audio_path(text, backend='openai', voice=openai_voice)
    if openai_cached.exists():
        result.update(cache_file=str(openai_cached), cache_hit=True,
                      tts_backend='cache', voice_id=f'openai-{openai_voice}')
        if play_audio(openai_cached):
            _log_tts_call(text, result)
            return result

    # Generate via OpenAI and cache (fast + cheap)
    if os.getenv('OPENAI_API_KEY'):
        result.update(tts_backend='openai', voice_id=f'openai-{openai_voice}',
                      cache_file=str(openai_cached), fallback_used=True)
        if generate_openai_audio(text, openai_cached, openai_voice):
            play_audio(openai_cached)
            _log_tts_call(text, result)
            return result

    # Fall through to whatever TTS script is available
    result["fallback_used"] = True
    tts_script = get_tts_script_path()
    if tts_script:
        result["tts_backend"] = Path(tts_script).stem
        try:
            subprocess.Popen(
                [sys.executable, tts_script, text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            _log_tts_call(text, result)
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    return result


def _log_tts_call(text: str, result: dict):
    """Append one line per TTS call to /tmp/cached_tts.log for debugging."""
    try:
        from datetime import datetime
        with open('/tmp/cached_tts.log', 'a') as f:
            ts = datetime.now().isoformat(timespec='seconds')
            f.write(f"{ts}  backend={result.get('tts_backend')}  "
                    f"cache_hit={result.get('cache_hit')}  "
                    f"fallback={result.get('fallback_used')}  "
                    f"text={text[:60]!r}\n")
    except Exception:
        pass


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
