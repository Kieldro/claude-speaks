#!/usr/bin/env python3
"""Simple ElevenLabs TTS using requests - no complex dependencies"""

import os
import sys
import json
import subprocess
import tempfile
from pathlib import Path

# Load environment variables from ~/.env
try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.env')
except ImportError:
    pass  # dotenv is optional

def speak(text):
    """Use ElevenLabs API to generate and play speech"""
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
            # Save audio to temp file (MP3 format)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
                f.write(response.content)
                audio_file = f.name

            # Play using system command
            # Try different players based on OS
            try:
                # macOS
                subprocess.run(['afplay', audio_file], check=True, timeout=10)
            except (FileNotFoundError, subprocess.SubprocessError):
                try:
                    # Linux with mpg123 (best for MP3)
                    subprocess.run(['mpg123', '-q', audio_file], check=True, timeout=10)
                except (FileNotFoundError, subprocess.SubprocessError):
                    try:
                        # Linux with ffplay (fallback)
                        subprocess.run(['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', audio_file],
                                     check=True, timeout=10,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    except (FileNotFoundError, subprocess.SubprocessError):
                        pass

            # Clean up temp file
            try:
                os.unlink(audio_file)
            except OSError:
                pass  # File cleanup failure is non-critical

            return True
        else:
            return False

    except Exception:
        return False

if __name__ == '__main__':
    if len(sys.argv) > 1:
        message = ' '.join(sys.argv[1:])
        if speak(message):
            sys.exit(0)
        else:
            sys.exit(1)
    else:
        sys.exit(1)
