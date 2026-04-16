#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

import json
import os
import sys
import random
import subprocess
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.env')
except ImportError:
    pass

sys.path.insert(0, str(Path(__file__).parent / "utils"))
from messages import get_completion_messages


def get_tts_script_path():
    script_dir = Path(__file__).parent
    tts_dir = script_dir / "utils" / "tts"
    cached = tts_dir / "cached_tts.py"
    if cached.exists():
        return str(cached)
    if os.getenv('ELEVENLABS_API_KEY'):
        p = tts_dir / "elevenlabs_tts.py"
        if p.exists():
            return str(p)
    if os.getenv('OPENAI_API_KEY'):
        p = tts_dir / "openai_tts.py"
        if p.exists():
            return str(p)
    p = tts_dir / "system_voice_tts.py"
    return str(p) if p.exists() else None


def main():
    try:
        input_data = json.load(sys.stdin)

        # Global TTS kill switch
        if os.getenv('CLAUDE_TTS_ENABLED', 'true').lower() not in ('true', '1', 'yes'):
            sys.exit(0)

        tts_script = get_tts_script_path()
        if not tts_script:
            sys.exit(0)

        message = random.choice(get_completion_messages())

        # Prepend agent name if available
        agent_name = input_data.get('agent_name') or input_data.get('name', '')
        if agent_name:
            message = f"{agent_name}: {message}"

        subprocess.Popen(
            [sys.executable, tts_script, message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        sys.exit(0)

    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
