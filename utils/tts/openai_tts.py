#!/usr/bin/env python3
"""OpenAI TTS. Requires `openai` package installed for the system python3."""

import os
import sys
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.env')
except ImportError:
    pass

DEBUG_LOG = Path('/tmp/openai_tts_debug.log')


def _log(msg: str):
    try:
        with open(DEBUG_LOG, 'a') as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except OSError:
        pass


def speak(text):
    """Use OpenAI TTS to generate and play speech"""
    _log(f"speak() called, text_len={len(text)}, text_preview={text[:60]!r}")
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        _log("FAIL: no OPENAI_API_KEY")
        return False

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        voice = os.getenv('OPENAI_TTS_VOICE', 'nova')
        _log(f"voice={voice}, calling tts-1-hd")

        response = client.audio.speech.create(
            model="tts-1-hd",
            voice=voice,
            input=text
        )
        _log(f"API returned {len(response.content)} bytes")

        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
            f.write(response.content)
            audio_file = f.name
        _log(f"wrote audio file: {audio_file}")

        env = os.environ.copy()

        played = False
        for player_name, cmd in [
            ('afplay', ['afplay', audio_file]),
            ('mpg123', ['mpg123', '-q', audio_file]),
            ('ffplay', ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', audio_file]),
        ]:
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=60, env=env)
                _log(f"{player_name} exit={result.returncode} stderr={result.stderr[:300]!r}")
                if result.returncode == 0:
                    played = True
                    break
            except FileNotFoundError:
                _log(f"{player_name}: not installed")
            except subprocess.SubprocessError as e:
                _log(f"{player_name}: SubprocessError {type(e).__name__}: {e}")

        if not played:
            _log("FAIL: no player could play audio")

        try:
            os.unlink(audio_file)
        except OSError:
            pass

        return played

    except Exception as e:
        _log(f"FAIL: exception {type(e).__name__}: {e}")
        return False

def fallback(message: str) -> int:
    """Try edge-tts (free neural), then system voice."""
    tts_dir = Path(__file__).parent
    for next_script in ('edge_tts_speak.py', 'system_voice_tts.py'):
        path = tts_dir / next_script
        if not path.exists():
            continue
        _log(f"WARN: falling back to {next_script}")
        try:
            result = subprocess.run([sys.executable, str(path), message], timeout=60)
            if result.returncode == 0:
                return 0
            _log(f"{next_script}: exit={result.returncode}")
        except Exception as e:
            _log(f"{next_script}: exception {type(e).__name__}: {e}")
    _log("FAIL: all fallbacks exhausted")
    return 1


if __name__ == '__main__':
    if len(sys.argv) <= 1:
        sys.exit(1)
    message = ' '.join(sys.argv[1:])
    if speak(message):
        sys.exit(0)
    sys.exit(fallback(message))
