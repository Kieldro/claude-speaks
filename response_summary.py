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
from pathlib import Path
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.env')
except ImportError:
    pass  # dotenv is optional

# Import utilities
sys.path.insert(0, str(Path(__file__).parent / "utils"))
from transcript import get_combined_response


def get_tts_script_path():
    """
    Get the cached TTS script path.
    Uses cached audio files when available to save API costs and reduce latency.
    """
    script_dir = Path(__file__).parent
    tts_dir = script_dir / "utils" / "tts"

    # Use cached TTS wrapper (supports all TTS backends with caching)
    cached_tts_script = tts_dir / "cached_tts.py"
    if cached_tts_script.exists():
        return str(cached_tts_script)

    # Fallback to non-cached scripts if cached_tts doesn't exist
    if os.getenv('ELEVENLABS_API_KEY'):
        elevenlabs_script = tts_dir / "elevenlabs_tts.py"
        if elevenlabs_script.exists():
            return str(elevenlabs_script)

    if os.getenv('OPENAI_API_KEY'):
        openai_script = tts_dir / "openai_tts.py"
        if openai_script.exists():
            return str(openai_script)

    # Fall back to system voice (no API key required)
    system_voice_script = tts_dir / "system_voice_tts.py"
    if system_voice_script.exists():
        return str(system_voice_script)

    return None


def summarize_and_announce(transcript_path: str):
    """
    Extract, summarize, and announce Claude's response via TTS.

    Args:
        transcript_path: Path to conversation transcript

    Returns:
        dict: Metadata about the operation
    """
    metadata = {
        "tts_triggered": False,
        "summary": None,
        "summary_method": None,
        "response_found": False,
        "error": None
    }

    try:
        # Extract Claude's latest response from transcript
        response_text = get_combined_response(transcript_path)

        if not response_text:
            metadata["error"] = "No response found in transcript"
            return metadata

        metadata["response_found"] = True

        # Summarize the response
        llm_dir = Path(__file__).parent / "utils" / "llm"
        summarizer_script = llm_dir / "summarizer.py"

        if summarizer_script.exists():
            try:
                # Call summarizer with 5 second timeout (execute directly to use uv shebang)
                result = subprocess.run(
                    [str(summarizer_script), response_text],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0 and result.stdout.strip():
                    summary = result.stdout.strip()
                    metadata["summary"] = summary
                    metadata["summary_method"] = "llm"
                else:
                    # Fallback: use first 10 words
                    words = response_text.split()[:10]
                    summary = ' '.join(words)
                    metadata["summary"] = summary
                    metadata["summary_method"] = "simple_fallback"

            except subprocess.TimeoutExpired:
                # LLM timeout - use simple fallback
                words = response_text.split()[:10]
                summary = ' '.join(words)
                metadata["summary"] = summary
                metadata["summary_method"] = "timeout_fallback"
        else:
            # No summarizer - use simple fallback
            words = response_text.split()[:10]
            summary = ' '.join(words)
            metadata["summary"] = summary
            metadata["summary_method"] = "no_summarizer"

        # Speak the summary via TTS
        tts_script = get_tts_script_path()
        if tts_script and summary:
            # Fire-and-forget: spawn TTS in background
            subprocess.Popen(
                [sys.executable, tts_script, summary],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent process
            )
            metadata["tts_triggered"] = True

    except Exception as e:
        metadata["error"] = f"{type(e).__name__}: {str(e)}"

    return metadata


def append_log_entry(log_path: Path, data: dict):
    """Append a JSON log entry to the log file."""
    try:
        with open(log_path, 'a') as f:
            json.dump(data, f)
            f.write('\n')
    except Exception:
        pass  # Fail silently on logging errors


def main():
    try:
        # Read JSON input from stdin
        input_data = json.loads(sys.stdin.read())

        # Get transcript path from input
        transcript_path = input_data.get('transcript_path')

        if not transcript_path:
            sys.exit(0)  # No transcript path provided

        # Check if response summary is enabled (opt-in via env var)
        enabled = os.getenv('CLAUDE_RESPONSE_SUMMARY_ENABLED', 'false').lower() in ('true', '1', 'yes')

        if not enabled:
            sys.exit(0)  # Feature disabled

        # Summarize and announce the response
        metadata = summarize_and_announce(transcript_path)

        # Debug logging
        script_dir = Path(__file__).parent
        log_dir = script_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "response_summary.jsonl"

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
            log_path = log_dir / "response_summary.jsonl"
            append_log_entry(log_path, {
                "error": "JSONDecodeError",
                "details": str(e),
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass
        sys.exit(0)

    except Exception as e:
        # Log all other errors
        try:
            script_dir = Path(__file__).parent
            log_dir = script_dir / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / "response_summary.jsonl"
            append_log_entry(log_path, {
                "error": type(e).__name__,
                "details": str(e),
                "timestamp": datetime.now().isoformat()
            })
        except:
            pass
        sys.exit(0)


if __name__ == "__main__":
    main()
