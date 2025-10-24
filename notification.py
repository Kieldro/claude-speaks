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
import subprocess
import random
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.env')
except ImportError:
    pass  # dotenv is optional


def get_tts_script_path():
    """
    Get the cached TTS script path.
    Uses cached audio files when available to save API costs and reduce latency.
    """
    # Get current script directory and construct utils/tts path
    script_dir = Path(__file__).parent
    tts_dir = script_dir / "utils" / "tts"

    # Use cached TTS wrapper (supports all TTS backends with caching)
    cached_tts_script = tts_dir / "cached_tts.py"
    if cached_tts_script.exists():
        return str(cached_tts_script)

    # Fallback to non-cached scripts if cached_tts doesn't exist
    # Check for ElevenLabs API key (highest priority)
    if os.getenv('ELEVENLABS_API_KEY'):
        elevenlabs_script = tts_dir / "elevenlabs_tts.py"
        if elevenlabs_script.exists():
            return str(elevenlabs_script)

    # Check for OpenAI API key (second priority)
    if os.getenv('OPENAI_API_KEY'):
        openai_script = tts_dir / "openai_tts.py"
        if openai_script.exists():
            return str(openai_script)

    # Fall back to system voice (no API key required)
    system_voice_script = tts_dir / "system_voice_tts.py"
    if system_voice_script.exists():
        return str(system_voice_script)

    return None


def announce_notification():
    """Announce that the agent needs user input. Returns TTS metadata dict.

    Fire-and-forget: Spawns TTS process in background and returns immediately.
    """
    tts_metadata = {
        "tts_triggered": False,
        "message": None,
        "personalized": False
    }

    try:
        tts_script = get_tts_script_path()
        if not tts_script:
            return tts_metadata  # No TTS scripts available

        # Get engineer name if available, fallback to USER
        engineer_name = os.getenv('ENGINEER_NAME', '').strip()
        if not engineer_name:
            engineer_name = os.getenv('USER', '').strip()

        # Create notification message with 30% chance to include name
        personalized = engineer_name and random.random() < 0.3
        if personalized:
            notification_message = f"{engineer_name}, your agent needs your input"
        else:
            notification_message = "Your agent needs your input"

        tts_metadata["message"] = notification_message
        tts_metadata["personalized"] = personalized
        tts_metadata["tts_triggered"] = True

        # Fire-and-forget: spawn TTS in background, don't wait for completion
        subprocess.Popen(
            [sys.executable, tts_script, notification_message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True  # Detach from parent process
        )

    except (FileNotFoundError, subprocess.SubprocessError, Exception) as e:
        tts_metadata["error"] = f"TTS spawn error: {type(e).__name__}"

    return tts_metadata


def main():
    try:
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())

        # Announce notification via TTS
        # Skip TTS for the generic "Claude is waiting for your input" message
        if input_data.get('message') != 'Claude is waiting for your input':
            announce_notification()
            # tts_metadata removed from input_data to avoid slowing down hook

        # Logging commented out for performance - file I/O blocks hook completion
        # script_dir = Path(__file__).parent
        # log_dir = script_dir / 'logs'
        # log_dir.mkdir(parents=True, exist_ok=True)
        # log_file = log_dir / 'notification.jsonl'
        #
        # input_data['timestamp'] = datetime.now().isoformat()
        #
        # with open(log_file, 'a') as f:
        #     json.dump(input_data, f)
        #     f.write('\n')

        sys.exit(0)

    except json.JSONDecodeError:
        sys.exit(0)  # Fail gracefully on JSON errors
    except Exception:
        sys.exit(0)  # Fail gracefully on any errors

if __name__ == '__main__':
    main()