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
    Get the TTS script path for summaries.
    Uses non-cached TTS to avoid delays and ensure summaries play immediately.
    Summaries are dynamic and shouldn't be cached.
    """
    script_dir = Path(__file__).parent
    tts_dir = script_dir / "utils" / "tts"

    # Use system voice for summaries (fast, no API calls, no caching)
    # This ensures immediate playback without waiting for API responses
    system_voice_script = tts_dir / "system_voice_tts.py"
    if system_voice_script.exists():
        return str(system_voice_script)

    # Fallback to OpenAI if system voice not available
    if os.getenv('OPENAI_API_KEY'):
        openai_script = tts_dir / "openai_tts.py"
        if openai_script.exists():
            return str(openai_script)

    # Fallback to ElevenLabs
    if os.getenv('ELEVENLABS_API_KEY'):
        elevenlabs_script = tts_dir / "elevenlabs_tts.py"
        if elevenlabs_script.exists():
            return str(elevenlabs_script)

    return None


def summarize_and_announce(transcript_path: str):
    """
    Extract, summarize, and announce Claude's response via TTS.

    Args:
        transcript_path: Path to conversation transcript

    Returns:
        dict: Metadata about the operation
    """
    # Play instant notification sound (non-blocking)
    try:
        subprocess.Popen(
            ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'error', '-volume', '50', '/usr/share/sounds/Yaru/stereo/message.oga'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
    except:
        pass  # Ignore if sound fails

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

        # Debug: log paths
        with open('/tmp/response_summary_paths.txt', 'a') as f:
            f.write(f"{datetime.now()}: __file__={__file__}\n")
            f.write(f"  llm_dir={llm_dir}\n")
            f.write(f"  summarizer_script={summarizer_script}\n")
            f.write(f"  exists={summarizer_script.exists()}\n")

        if summarizer_script.exists():
            try:
                # Call summarizer with 10 second timeout (execute directly to use uv shebang)
                result = subprocess.run(
                    [str(summarizer_script), response_text],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                # Log subprocess output for debugging
                with open('/tmp/response_summary_subprocess.txt', 'a') as f:
                    f.write(f"{datetime.now()}: returncode={result.returncode}\n")
                    f.write(f"stdout: {result.stdout[:200]}\n")
                    f.write(f"stderr: {result.stderr[:200]}\n")

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
                    with open('/tmp/response_summary_subprocess.txt', 'a') as f:
                        f.write(f"Using simple_fallback\n")

            except subprocess.TimeoutExpired as e:
                # LLM timeout - use simple fallback
                words = response_text.split()[:10]
                summary = ' '.join(words)
                metadata["summary"] = summary
                metadata["summary_method"] = "timeout_fallback"
                with open('/tmp/response_summary_subprocess.txt', 'a') as f:
                    f.write(f"Timeout after 10s\n")
        else:
            # No summarizer - use simple fallback
            words = response_text.split()[:10]
            summary = ' '.join(words)
            metadata["summary"] = summary
            metadata["summary_method"] = "no_summarizer"

        # Speak the summary via TTS (detached process survives hook exit)
        tts_script = get_tts_script_path()

        # Debug logging
        with open('/tmp/response_summary_tts.txt', 'a') as f:
            f.write(f"{datetime.now()}: tts_script={tts_script}, summary={summary[:50]}\n")

        if tts_script and summary:
            # Fully detach TTS process so it survives even if hook is killed
            try:
                # Use nohup-style detachment
                with open('/tmp/response_summary_tts.txt', 'a') as f:
                    f.write(f"  Spawning: {sys.executable} {tts_script} {summary[:30]}\n")

                subprocess.Popen(
                    [sys.executable, tts_script, summary],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True  # Completely detach from parent
                )
                metadata["tts_triggered"] = True

                with open('/tmp/response_summary_tts.txt', 'a') as f:
                    f.write(f"  TTS spawned successfully\n")
            except Exception as e:
                metadata["tts_triggered"] = False
                metadata["tts_error"] = str(e)
                with open('/tmp/response_summary_tts.txt', 'a') as f:
                    f.write(f"  ERROR: {e}\n")

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
    # Log that hook was triggered
    with open('/tmp/response_summary_triggered.txt', 'a') as f:
        f.write(f"{datetime.now()}: Hook triggered\n")

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
        import traceback
        error_msg = f"ERROR: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        try:
            with open('/tmp/response_summary_error.txt', 'a') as f:
                f.write(f"{datetime.now()}: {error_msg}\n")
        except:
            pass
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
