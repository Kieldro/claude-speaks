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
    # Check for OpenAI API key (highest priority - fastest and cheapest)
    if os.getenv('OPENAI_API_KEY'):
        openai_script = tts_dir / "openai_tts.py"
        if openai_script.exists():
            return str(openai_script)

    # Check for ElevenLabs API key (second priority - higher quality but more expensive)
    if os.getenv('ELEVENLABS_API_KEY'):
        elevenlabs_script = tts_dir / "elevenlabs_tts.py"
        if elevenlabs_script.exists():
            return str(elevenlabs_script)

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


def get_session_identifier(session_id):
    """Generate a short phonetic identifier from session ID.

    Args:
        session_id: Claude Code session ID

    Returns:
        str: Short phonetic identifier (e.g., "Alpha three")
    """
    if not session_id or session_id == "test":
        return None

    # NATO phonetic alphabet (single syllable preferred)
    phonetics = [
        "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot",
        "Golf", "Hotel", "India", "Juliet", "Kilo", "Lima",
        "Mike", "November", "Oscar", "Papa", "Quebec", "Romeo",
        "Sierra", "Tango", "Uniform", "Victor", "Whiskey", "X-ray",
        "Yankee", "Zulu"
    ]

    # Use hash of session_id for consistent mapping
    import hashlib
    hash_val = int(hashlib.md5(session_id.encode()).hexdigest()[:8], 16)

    # Get phonetic and number (0-9)
    phonetic = phonetics[hash_val % len(phonetics)]
    number = (hash_val // len(phonetics)) % 10

    return f"{phonetic} {number}"


def select_completion_message_fast(session_id=None, include_session_id=False):
    """Select a completion message instantly (always uses cached messages).

    For performance, always uses cached messages. LLM generation would block the hook.

    Args:
        session_id: Optional Claude Code session ID for identification
        include_session_id: If True, prepend session identifier to message

    Returns:
        tuple: (message: str, llm_generated: bool, backend: str)
    """
    messages = get_completion_messages()
    message = random.choice(messages)

    # Add session identifier if enabled and available
    if include_session_id and session_id:
        identifier = get_session_identifier(session_id)
        if identifier:
            message = f"{identifier}: {message}"

    return message, False, None


def announce_completion(session_id=None, include_session_id=False):
    """Announce completion using TTS with completion message.

    Fire-and-forget: Spawns TTS process in background and returns immediately.

    Args:
        session_id: Optional Claude Code session ID for identification
        include_session_id: If True, prepend session identifier to message

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

        # Select message (always cached for speed)
        message, llm_generated, llm_backend = select_completion_message_fast(session_id, include_session_id)

        metadata["message"] = message
        metadata["llm_generated"] = llm_generated
        metadata["llm_backend"] = llm_backend
        metadata["tts_triggered"] = True

        # Fire-and-forget: spawn TTS in background, don't wait for completion
        subprocess.Popen(
            [sys.executable, tts_script, message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True  # Detach from parent process
        )

    except (subprocess.SubprocessError, FileNotFoundError, Exception) as e:
        metadata["error"] = f"TTS spawn error: {type(e).__name__}"

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

        # Extract session_id if available
        session_id = input_data.get('session_id')

        # Check environment variable to enable session identifiers
        include_session_id = os.getenv('CLAUDE_SESSION_ID_ENABLED', 'false').lower() in ('true', '1', 'yes')

        # Announce completion via TTS with optional session identifier
        metadata = announce_completion(session_id, include_session_id)

        # Debug logging
        script_dir = Path(__file__).parent
        log_dir = script_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "stop.jsonl"

        input_data['timestamp'] = datetime.now().isoformat()
        input_data['metadata'] = metadata
        append_log_entry(log_path, input_data)

        sys.exit(0)

    except json.JSONDecodeError as e:
        # Log JSON errors
        try:
            script_dir = Path(__file__).parent
            log_dir = script_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "stop.jsonl"
            append_log_entry(log_path, {"error": "JSONDecodeError", "details": str(e), "timestamp": datetime.now().isoformat()})
        except:
            pass
        sys.exit(0)
    except Exception as e:
        # Log all other errors
        try:
            script_dir = Path(__file__).parent
            log_dir = script_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "stop.jsonl"
            append_log_entry(log_path, {"error": type(e).__name__, "details": str(e), "timestamp": datetime.now().isoformat()})
        except:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
