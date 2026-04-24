#!/usr/bin/env python3
"""Cartesia TTS — ultra-low latency (~90ms TTFB), no external deps beyond stdlib."""

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.env')
except ImportError:
    pass

DEBUG_LOG = Path('/tmp/tts_chain.log')
DEFAULT_VOICE = 'ec58877e-44ae-4581-9078-a04225d42bd4'  # Charles - Heroic Man


def _log(msg: str):
    try:
        with open(DEBUG_LOG, 'a') as f:
            f.write(f"[{datetime.now().isoformat()}] [cartesia] {msg}\n")
    except OSError:
        pass


def speak(text: str) -> bool:
    _log(f"speak() called, text_len={len(text)}, text_preview={text[:60]!r}")
    api_key = os.getenv('CARTESIA_API_KEY')
    if not api_key:
        _log("FAIL: no CARTESIA_API_KEY")
        return False

    voice_id = os.getenv('CARTESIA_VOICE_ID', DEFAULT_VOICE)
    _log(f"voice_id={voice_id}")

    body = json.dumps({
        "model_id": "sonic-3",
        "transcript": text,
        "voice": {"mode": "id", "id": voice_id},
        "output_format": {
            "container": "mp3",
            "bit_rate": 128000,
            "sample_rate": 44100,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.cartesia.ai/tts/bytes",
        data=body,
        method="POST",
        headers={
            "X-API-Key": api_key,
            "Cartesia-Version": "2024-06-10",
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
    )

    _log("POST Cartesia API")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            audio_bytes = resp.read()
    except urllib.error.HTTPError as e:
        err_body = e.read()[:500]
        _log(f"FAIL: API HTTPError status={e.code} body={err_body!r}")
        return False
    except Exception as e:
        _log(f"FAIL: request exception {type(e).__name__}: {e}")
        return False

    _log(f"API response status={status}, body_len={len(audio_bytes)}")

    if status != 200 or len(audio_bytes) == 0:
        _log(f"FAIL: bad response status={status} len={len(audio_bytes)}")
        return False

    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
        f.write(audio_bytes)
        audio_file = f.name
    _log(f"wrote audio file: {audio_file}")

    played = False
    for name, cmd in [
        ('afplay', ['afplay', audio_file]),
        ('mpg123', ['mpg123', '-q', audio_file]),
        ('ffplay', ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', audio_file]),
    ]:
        try:
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            _log(f"{name} exit={result.returncode} stderr={result.stderr[:300]!r}")
            if result.returncode == 0:
                played = True
                break
        except FileNotFoundError:
            _log(f"{name}: not installed")
        except subprocess.SubprocessError as e:
            _log(f"{name}: SubprocessError {type(e).__name__}: {e}")

    try:
        os.unlink(audio_file)
    except OSError:
        pass

    if not played:
        _log("FAIL: no player could play audio")
    return played


def fallback(message: str) -> int:
    """Try next TTS backends in the chain."""
    tts_dir = Path(__file__).parent
    for next_script in ('elevenlabs_tts.py', 'openai_tts.py', 'edge_tts_speak.py', 'system_voice_tts.py'):
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
