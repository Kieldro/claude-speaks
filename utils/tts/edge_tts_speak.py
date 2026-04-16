#!/usr/bin/env python3
"""Microsoft Edge TTS — free neural voices, no auth. Internet required."""

import asyncio
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

DEBUG_LOG = Path('/tmp/edge_tts_debug.log')

DEFAULT_VOICE = 'en-US-AriaNeural'


def _log(msg: str):
    try:
        with open(DEBUG_LOG, 'a') as f:
            f.write(f"[{datetime.now().isoformat()}] {msg}\n")
    except OSError:
        pass


async def _synthesize(text: str, voice: str, out_path: str):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(out_path)


def speak(text: str) -> bool:
    _log(f"speak() called, text_len={len(text)}, text_preview={text[:60]!r}")
    voice = os.getenv('EDGE_TTS_VOICE', DEFAULT_VOICE)
    _log(f"voice={voice}")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
            audio_file = f.name
        asyncio.run(_synthesize(text, voice, audio_file))
        size = os.path.getsize(audio_file)
        _log(f"synthesized {size} bytes -> {audio_file}")
        if size == 0:
            _log("FAIL: empty audio output")
            os.unlink(audio_file)
            return False
    except Exception as e:
        _log(f"FAIL: synthesis exception {type(e).__name__}: {e}")
        return False

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
    tts_dir = Path(__file__).parent
    path = tts_dir / 'system_voice_tts.py'
    if not path.exists():
        _log("FAIL: system_voice_tts.py not found")
        return 1
    _log("WARN: falling back to system_voice_tts.py")
    try:
        result = subprocess.run([sys.executable, str(path), message], timeout=60)
        return result.returncode
    except Exception as e:
        _log(f"system_voice_tts.py: exception {type(e).__name__}: {e}")
        return 1


if __name__ == '__main__':
    if len(sys.argv) <= 1:
        sys.exit(1)
    message = ' '.join(sys.argv[1:])
    if speak(message):
        sys.exit(0)
    sys.exit(fallback(message))
