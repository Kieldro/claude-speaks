#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "openai",
#     "python-dotenv",
# ]
# ///

import os
import sys
import subprocess
import tempfile
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.env')
except ImportError:
    pass

def speak(text):
    """Use OpenAI TTS to generate and play speech"""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        return False

    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)

        # Generate audio using TTS-1 (standard quality, fast)
        response = client.audio.speech.create(
            model="tts-1",
            voice="ash",
            input=text
        )

        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp3') as f:
            f.write(response.content)
            audio_file = f.name

        # Play using system command
        # Preserve audio environment variables for PulseAudio/PipeWire
        env = os.environ.copy()

        try:
            # macOS
            subprocess.run(['afplay', audio_file], check=True, timeout=10, env=env)
        except (FileNotFoundError, subprocess.SubprocessError):
            try:
                # Linux with mpg123 (best for MP3)
                subprocess.run(['mpg123', '-q', audio_file], check=True, timeout=10, env=env)
            except (FileNotFoundError, subprocess.SubprocessError):
                try:
                    # Linux with ffplay (fallback)
                    subprocess.run(['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', audio_file],
                                 check=True, timeout=10,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL,
                                 env=env)
                except (FileNotFoundError, subprocess.SubprocessError):
                    pass

        # Clean up temp file
        try:
            os.unlink(audio_file)
        except OSError:
            pass

        return True

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
