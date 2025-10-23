#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "python-dotenv",
# ]
# ///

import argparse
import json
import os
import sys
import random
import subprocess
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.env')
except ImportError:
    pass  # dotenv is optional

# Import shared message definitions
sys.path.insert(0, str(Path(__file__).parent / "utils"))
from messages import get_completion_messages

# LLM completion message generation timeout (seconds)
LLM_TIMEOUT = 2


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


def get_llm_completion_message_with_backend():
    """
    Generate completion message using available LLM services.
    Priority order: OpenAI > Anthropic > Ollama > fallback to random message

    Returns:
        tuple: (message: str, backend: str or None)
    """
    # Get current script directory and construct utils/llm path
    script_dir = Path(__file__).parent
    llm_dir = script_dir / "utils" / "llm"

    # Try OpenAI first (highest priority)
    if os.getenv('OPENAI_API_KEY'):
        oai_script = llm_dir / "oai.py"
        if oai_script.exists():
            try:
                result = subprocess.run([
                    "uv", "run", str(oai_script), "--completion"
                ],
                capture_output=True,
                text=True,
                timeout=LLM_TIMEOUT
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip(), "openai"
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass

    # Try Anthropic second
    if os.getenv('ANTHROPIC_API_KEY'):
        anth_script = llm_dir / "anth.py"
        if anth_script.exists():
            try:
                result = subprocess.run([
                    "uv", "run", str(anth_script), "--completion"
                ],
                capture_output=True,
                text=True,
                timeout=LLM_TIMEOUT
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip(), "anthropic"
            except (subprocess.TimeoutExpired, subprocess.SubprocessError):
                pass

    # Try Ollama third (local LLM)
    ollama_script = llm_dir / "ollama.py"
    if ollama_script.exists():
        try:
            result = subprocess.run([
                "uv", "run", str(ollama_script), "--completion"
            ],
            capture_output=True,
            text=True,
            timeout=LLM_TIMEOUT
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip(), "ollama"
        except (subprocess.TimeoutExpired, subprocess.SubprocessError):
            pass

    # Fallback to random predefined message
    messages = get_completion_messages()
    return random.choice(messages), "fallback"

def get_llm_completion_message():
    """
    Generate completion message using available LLM services.
    Priority order: OpenAI > Anthropic > Ollama > fallback to random message

    Returns:
        str: Generated or fallback completion message
    """
    message, _ = get_llm_completion_message_with_backend()
    return message

def announce_completion():
    """Announce completion using the best available TTS service. Returns metadata dict."""
    metadata = {
        "tts_triggered": False,
        "message": None,
        "llm_generated": False,
        "llm_backend": None,
        "error": None
    }

    try:
        tts_script = get_tts_script_path()
        if not tts_script:
            metadata["error"] = "No TTS script available"
            return metadata

        # 5% chance to generate original LLM message, 95% use cached
        use_llm = random.random() < 0.05
        if use_llm:
            # Try LLM-generated message
            completion_message, llm_backend = get_llm_completion_message_with_backend()
            metadata["llm_generated"] = True
            metadata["llm_backend"] = llm_backend
        else:
            # Use cached message
            messages = get_completion_messages()
            completion_message = random.choice(messages)
            metadata["llm_generated"] = False

        metadata["message"] = completion_message
        metadata["tts_triggered"] = True

        # Call the TTS script with the completion message and capture metadata
        result = subprocess.run([
            sys.executable, tts_script, completion_message, "--json"
        ],
        capture_output=True,
        text=True,
        timeout=10
        )

        # Parse TTS backend metadata if available
        if result.returncode == 0 and result.stdout.strip():
            try:
                tts_details = json.loads(result.stdout.strip())
                metadata.update(tts_details)
            except json.JSONDecodeError:
                metadata["error"] = "Failed to parse TTS metadata"

    except subprocess.TimeoutExpired:
        metadata["error"] = "TTS timeout"
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        metadata["error"] = f"TTS subprocess error: {type(e).__name__}"
    except Exception as e:
        metadata["error"] = f"Unexpected error: {type(e).__name__}"

    return metadata


def main():
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument('--chat', action='store_true', help='Copy transcript to chat.json')
        parser.add_argument('--notify', action='store_true', help='Enable TTS completion announcement')
        args = parser.parse_args()
        
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        # Extract required fields
        session_id = input_data.get("session_id", "")
        stop_hook_active = input_data.get("stop_hook_active", False)

        # Ensure log directory exists relative to this script
        script_dir = Path(__file__).parent
        log_dir = script_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "stop.json"

        # Read existing log data or initialize empty list
        if os.path.exists(log_path):
            with open(log_path, 'r') as f:
                try:
                    log_data = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    log_data = []
        else:
            log_data = []

        # Append new data with timestamp
        input_data['timestamp'] = datetime.now().isoformat()

        # Handle --notify flag - announce completion and capture metadata
        if args.notify:
            completion_metadata = announce_completion()
            input_data['tts_metadata'] = completion_metadata

        log_data.append(input_data)

        # Write back to file with formatting
        with open(log_path, 'w') as f:
            json.dump(log_data, f, indent=2)

        # Handle --chat switch
        if args.chat and 'transcript_path' in input_data:
            transcript_path = input_data['transcript_path']
            if os.path.exists(transcript_path):
                # Read .jsonl file and convert to JSON array
                chat_data = []
                try:
                    with open(transcript_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                try:
                                    chat_data.append(json.loads(line))
                                except json.JSONDecodeError:
                                    pass  # Skip invalid lines

                    # Write to hooks/logs/chat.json
                    chat_file = log_dir / 'chat.json'
                    with open(chat_file, 'w') as f:
                        json.dump(chat_data, f, indent=2)
                except Exception:
                    pass  # Fail silently

        sys.exit(0)

    except json.JSONDecodeError:
        # Handle JSON decode errors gracefully
        sys.exit(0)
    except Exception:
        # Handle any other errors gracefully
        sys.exit(0)


if __name__ == "__main__":
    main()
