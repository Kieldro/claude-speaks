#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# ///

import sys
import subprocess
import os

def speak(text):
    """Use system voice for text-to-speech."""
    # Get volume from environment variable (default: 0, range: -100 to +100)
    volume = os.getenv('TTS_VOLUME', '0')

    try:
        # Validate volume is a number
        vol_int = int(volume)
        vol_int = max(-100, min(100, vol_int))  # Clamp to valid range
        volume = str(vol_int)
    except ValueError:
        volume = '0'  # Default if invalid

    try:
        # macOS: use 'say' command (no volume control via CLI)
        subprocess.run(['say', text], check=True, timeout=10)
        return True
    except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
        try:
            # Linux: Use spd-say (speech-dispatcher) with volume control
            subprocess.run(['spd-say', '--volume', volume, text], check=True, timeout=10)
            return True
        except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
            try:
                # Fallback to espeak if spd-say fails (espeak uses different volume syntax)
                # espeak volume: 0-200, default 100
                espeak_vol = str(max(0, min(200, int(volume) + 100)))
                subprocess.run(['espeak', '-a', espeak_vol, text], check=True, timeout=10)
                return True
            except (subprocess.SubprocessError, FileNotFoundError, subprocess.TimeoutExpired):
                return False

if __name__ == '__main__':
    if len(sys.argv) > 1:
        message = ' '.join(sys.argv[1:])
        if speak(message):
            sys.exit(0)
        else:
            print("Error: No TTS system available", file=sys.stderr)
            sys.exit(1)
    else:
        print("Usage: system_voice_tts.py <message>", file=sys.stderr)
        sys.exit(1)
