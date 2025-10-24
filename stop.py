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


def try_llm_backend(script_path):
    """Try to generate completion message from a specific LLM backend.

    Args:
        script_path: Path to the LLM backend script

    Returns:
        str or None: Generated message if successful, None otherwise
    """
    try:
        result = subprocess.run(
            ["uv", "run", str(script_path), "--completion"],
            capture_output=True,
            text=True,
            timeout=LLM_TIMEOUT
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass
    return None


def get_llm_completion_message_with_backend():
    """Generate completion message using available LLM services.

    Priority order: OpenAI > Anthropic > Ollama > fallback to cached message

    Returns:
        tuple: (message: str, backend: str)
    """
    script_dir = Path(__file__).parent
    llm_dir = script_dir / "utils" / "llm"

    # Try each backend in priority order
    llm_backends = [
        ("OPENAI_API_KEY", "oai.py", "openai"),
        ("ANTHROPIC_API_KEY", "anth.py", "anthropic"),
        (None, "ollama.py", "ollama"),  # Ollama doesn't need API key
    ]

    for api_key_env, script_name, backend_name in llm_backends:
        # Skip if API key required but not present
        if api_key_env and not os.getenv(api_key_env):
            continue

        script_path = llm_dir / script_name
        if script_path.exists():
            message = try_llm_backend(script_path)
            if message:
                return message, backend_name

    # Fallback to random cached message
    messages = get_completion_messages()
    return random.choice(messages), "fallback"

def get_llm_completion_message():
    """Generate completion message (wrapper that discards backend info).

    Returns:
        str: Generated or fallback completion message
    """
    message, _ = get_llm_completion_message_with_backend()
    return message


def select_completion_message():
    """Select a completion message (5% LLM-generated, 95% cached).

    Returns:
        tuple: (message: str, llm_generated: bool, backend: str)
    """
    use_llm = random.random() < 0.05

    if use_llm:
        message, backend = get_llm_completion_message_with_backend()
        return message, True, backend
    else:
        messages = get_completion_messages()
        message = random.choice(messages)
        return message, False, None


def call_tts_script(tts_script, message):
    """Call TTS script and parse response metadata.

    Args:
        tts_script: Path to TTS script
        message: Text to speak

    Returns:
        dict: TTS metadata from script output
    """
    result = subprocess.run(
        [sys.executable, tts_script, message, "--json"],
        capture_output=True,
        text=True,
        timeout=10
    )

    if result.returncode == 0 and result.stdout.strip():
        try:
            return json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            return {"error": "Failed to parse TTS metadata"}

    return {}


def announce_completion():
    """Announce completion using TTS with completion message.

    Returns:
        dict: Metadata about the announcement (message, backend, errors, etc.)
    """
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

        # Select message (5% LLM, 95% cached)
        message, llm_generated, llm_backend = select_completion_message()

        metadata["message"] = message
        metadata["llm_generated"] = llm_generated
        metadata["llm_backend"] = llm_backend
        metadata["tts_triggered"] = True

        # Call TTS and merge response metadata
        tts_details = call_tts_script(tts_script, message)
        metadata.update(tts_details)

    except subprocess.TimeoutExpired:
        metadata["error"] = "TTS timeout"
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        metadata["error"] = f"TTS subprocess error: {type(e).__name__}"
    except Exception as e:
        metadata["error"] = f"Unexpected error: {type(e).__name__}"

    return metadata


def append_log_entry(log_path, entry):
    """Append a single log entry to .jsonl file.

    Args:
        log_path: Path to .jsonl log file
        entry: Dict to append as JSON line
    """
    with open(log_path, 'a') as f:
        json.dump(entry, f)
        f.write('\n')


def main():
    try:
        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        # Announce completion via TTS
        input_data['tts_metadata'] = announce_completion()

        # Setup log directory and append entry
        script_dir = Path(__file__).parent
        log_dir = script_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "stop.jsonl"

        input_data['timestamp'] = datetime.now().isoformat()
        append_log_entry(log_path, input_data)

        sys.exit(0)

    except json.JSONDecodeError:
        sys.exit(0)  # Fail gracefully on JSON errors
    except Exception:
        sys.exit(0)  # Fail gracefully on any errors


if __name__ == "__main__":
    main()
