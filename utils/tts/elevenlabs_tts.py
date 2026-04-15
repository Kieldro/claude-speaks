#!/usr/bin/env python3
"""Simple ElevenLabs TTS using requests - no complex dependencies"""

import os
import sys
import json
import subprocess
import tempfile
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# Load environment variables from ~/.env
try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.env')
except ImportError:
    pass  # dotenv is optional

DEBUG_LOG = Path('/tmp/elevenlabs_tts_debug.log')


def _log(msg: str):
    try:
        with open(DEBUG_LOG, 'a') as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except OSError:
        pass


def speak(text):
    """Use ElevenLabs API to generate and play speech"""
    _log(f"speak() called, text_len={len(text)}, text_preview={text[:60]!r}")
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        _log("FAIL: no ELEVENLABS_API_KEY")
        return False

    try:
        voice_id = os.getenv('ELEVENLABS_VOICE_ID', '21m00Tcm4TlvDq8ikWAM')
        _log(f"voice_id={voice_id}")
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        body = json.dumps({
            "text": text,
            "model_id": "eleven_flash_v2_5",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "speed": 1.0,
            },
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": api_key,
            },
        )

        _log("POST ElevenLabs API")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status = resp.status
                audio_bytes = resp.read()
        except urllib.error.HTTPError as e:
            err_body = e.read()[:500]
            _log(f"FAIL: API HTTPError status={e.code} body={err_body!r}")
            return False
        _log(f"API response status={status}, body_len={len(audio_bytes)}")

        if status == 200:
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                f.write(audio_bytes)
                audio_file = f.name
            _log(f"wrote audio file: {audio_file}")

            played = False
            for player_name, cmd in [
                ('afplay', ['afplay', audio_file]),
                ('mpg123', ['mpg123', '-q', audio_file]),
                ('ffplay', ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', audio_file]),
            ]:
                try:
                    result = subprocess.run(cmd, capture_output=True, timeout=15)
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
        else:
            _log(f"FAIL: unexpected status={status}")
            return False

    except Exception as e:
        _log(f"FAIL: exception {type(e).__name__}: {e}")
        return False

def fallback(message: str) -> int:
    """Try next TTS backend in the chain. Returns its exit code."""
    tts_dir = Path(__file__).parent
    for next_script in ('openai_tts.py', 'edge_tts_speak.py', 'system_voice_tts.py'):
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
