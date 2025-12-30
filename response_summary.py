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
import signal
import fcntl
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


def sanitize_text(text: str, max_length: int = 50000) -> str:
    """
    Sanitize text input for subprocess calls to prevent command injection.

    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length

    Returns:
        Sanitized text safe for subprocess calls
    """
    if not text or not isinstance(text, str):
        return ""

    # Remove null bytes and limit length
    text = text.replace('\0', '').strip()

    # Truncate if too long
    if len(text) > max_length:
        text = text[:max_length]

    return text


# Debug logging configuration
DEBUG_ENABLED = os.getenv('RESPONSE_SUMMARY_DEBUG', 'false').lower() in ('true', '1', 'yes')
DEBUG_LOG = Path('/tmp/response_summary_debug.log')

def debug_log(message: str, data: dict = None):
    """Log debug information if debugging is enabled."""
    if not DEBUG_ENABLED:
        return

    try:
        # Create log file with restrictive permissions on first write
        if not DEBUG_LOG.exists():
            DEBUG_LOG.touch(mode=0o600)  # Owner read/write only

        with open(DEBUG_LOG, 'a') as f:
            timestamp = datetime.now().isoformat()
            f.write(f"[{timestamp}] {message}\n")
            if data:
                for key, value in data.items():
                    # Truncate large values to prevent log bloat
                    if isinstance(value, str) and len(value) > 500:
                        value = value[:500] + "... (truncated)"
                    f.write(f"  {key}: {value}\n")
            f.write("\n")
    except Exception:
        pass  # Fail silently on logging errors


def get_tts_script_path():
    """
    Get the TTS script path for summaries.
    Priority: OpenAI > ElevenLabs > system voice
    """
    script_dir = Path(__file__).parent
    tts_dir = script_dir / "utils" / "tts"

    # Check for OpenAI API key (fastest and cheapest)
    if os.getenv('OPENAI_API_KEY'):
        openai_script = tts_dir / "openai_tts.py"
        if openai_script.exists():
            return str(openai_script)

    # Fallback to ElevenLabs (highest quality)
    if os.getenv('ELEVENLABS_API_KEY'):
        elevenlabs_script = tts_dir / "elevenlabs_tts.py"
        if elevenlabs_script.exists():
            return str(elevenlabs_script)

    # Fallback to system voice (free, no API key required)
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
    debug_log("=== SUMMARIZE AND ANNOUNCE STARTED ===", {
        "transcript_path": transcript_path,
        "cwd": os.getcwd()
    })

    # Play instant notification sound (non-blocking) to indicate hook started
    try:
        debug_log("Playing start notification")
        subprocess.Popen(
            ['paplay', '/usr/share/sounds/freedesktop/stereo/message-new-instant.oga'],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        debug_log("Start notification spawned")
    except Exception as e:
        debug_log("Start notification failed", {"error": str(e)})

    metadata = {
        "tts_triggered": False,
        "summary": None,
        "summary_method": None,
        "response_found": False,
        "error": None
    }

    try:
        # Extract Claude's latest response from transcript
        debug_log("Extracting response from transcript")
        response_text = get_combined_response(transcript_path)
        debug_log("Response extraction complete", {
            "response_length": len(response_text) if response_text else 0,
            "response_preview": response_text[:100] if response_text else "None"
        })

        if not response_text:
            debug_log("ERROR: No response found in transcript")
            metadata["error"] = "No response found in transcript"
            return metadata

        metadata["response_found"] = True
        debug_log("Response found successfully")

        # Summarize the response
        llm_dir = Path(__file__).parent / "utils" / "llm"
        summarizer_script = llm_dir / "summarizer.py"

        debug_log("Checking for summarizer script", {
            "llm_dir": str(llm_dir),
            "summarizer_script": str(summarizer_script),
            "exists": summarizer_script.exists()
        })

        if summarizer_script.exists():
            try:
                # Sanitize input before passing to subprocess
                sanitized_response = sanitize_text(response_text)

                debug_log("Calling LLM summarizer", {
                    "timeout": 10,
                    "response_preview": response_text[:100]
                })
                # Call summarizer with 10 second timeout (execute directly to use uv shebang)
                result = subprocess.run(
                    [str(summarizer_script), sanitized_response],
                    capture_output=True,
                    text=True,
                    timeout=10
                )

                debug_log("LLM summarizer completed", {
                    "returncode": result.returncode,
                    "stdout": result.stdout[:200],
                    "stderr": result.stderr[:200]
                })

                if result.returncode == 0 and result.stdout.strip():
                    summary = result.stdout.strip()
                    metadata["summary"] = summary
                    metadata["summary_method"] = "llm"
                    debug_log("Using LLM summary", {"summary": summary})
                else:
                    # Fallback: use first 10 words
                    words = response_text.split()[:10]
                    summary = ' '.join(words)
                    metadata["summary"] = summary
                    metadata["summary_method"] = "simple_fallback"
                    debug_log("Using simple fallback (LLM failed)", {"summary": summary})

            except subprocess.TimeoutExpired as e:
                # LLM timeout - use simple fallback
                words = response_text.split()[:10]
                summary = ' '.join(words)
                metadata["summary"] = summary
                metadata["summary_method"] = "timeout_fallback"
                debug_log("Using timeout fallback", {"summary": summary})
        else:
            # No summarizer - use simple fallback
            words = response_text.split()[:10]
            summary = ' '.join(words)
            metadata["summary"] = summary
            metadata["summary_method"] = "no_summarizer"
            debug_log("No summarizer script found, using fallback", {"summary": summary})

        # Speak the summary via TTS (detached process survives hook exit)
        tts_script = get_tts_script_path()

        debug_log("Getting TTS script", {
            "tts_script": str(tts_script) if tts_script else "None",
            "summary": summary,
            "TTS_VOLUME": os.getenv('TTS_VOLUME', 'not set')
        })

        if tts_script and summary:
            # Run TTS synchronously - system voice is fast enough
            try:
                # Sanitize summary before passing to subprocess
                sanitized_summary = sanitize_text(summary, max_length=500)

                debug_log("Running TTS synchronously", {
                    "executable": sys.executable,
                    "script": tts_script,
                    "summary": summary
                })

                # Build minimal environment with only necessary variables
                safe_env = {
                    'PATH': os.environ.get('PATH', ''),
                    'HOME': os.environ.get('HOME', ''),
                    'TTS_VOLUME': os.getenv('TTS_VOLUME', '0'),
                    # Audio environment variables needed for PulseAudio/PipeWire
                    'XDG_RUNTIME_DIR': os.environ.get('XDG_RUNTIME_DIR', ''),
                    'DBUS_SESSION_BUS_ADDRESS': os.environ.get('DBUS_SESSION_BUS_ADDRESS', ''),
                }

                # Add API keys only if needed for specific TTS script
                tts_script_str = str(tts_script)
                if 'elevenlabs' in tts_script_str:
                    safe_env['ELEVENLABS_API_KEY'] = os.getenv('ELEVENLABS_API_KEY', '')
                    safe_env['ELEVENLABS_VOICE_ID'] = os.getenv('ELEVENLABS_VOICE_ID', '')
                elif 'openai' in tts_script_str:
                    safe_env['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', '')
                    safe_env['OPENAI_TTS_DEBUG'] = os.getenv('OPENAI_TTS_DEBUG', 'false')

                # Use Popen with process group to ensure child processes (mpg123) are killed on timeout
                process = subprocess.Popen(
                    [tts_script, sanitized_summary],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    env=safe_env,
                    start_new_session=True  # Create new process group
                )

                try:
                    stdout, stderr = process.communicate(timeout=15)
                    metadata["tts_triggered"] = True
                    metadata["tts_returncode"] = process.returncode
                    debug_log("TTS completed", {
                        "returncode": process.returncode,
                        "stdout": stdout.decode(errors='replace') if stdout else "",
                        "stderr": stderr.decode(errors='replace') if stderr else ""
                    })
                except subprocess.TimeoutExpired:
                    # Kill entire process group to ensure mpg123 is terminated
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                        debug_log("Killed TTS process group due to timeout")
                    except:
                        process.kill()
                    process.wait()
                    metadata["tts_triggered"] = False
                    metadata["tts_error"] = "Timeout after 15s"
                    debug_log("ERROR: TTS timeout")
            except Exception as e:
                metadata["tts_triggered"] = False
                metadata["tts_error"] = str(e)
                debug_log("ERROR: TTS failed", {"error": str(e), "type": type(e).__name__})
        else:
            debug_log("Skipping TTS", {
                "tts_script": "missing" if not tts_script else "present",
                "summary": "missing" if not summary else "present"
            })

    except Exception as e:
        metadata["error"] = f"{type(e).__name__}: {str(e)}"
        debug_log("ERROR in summarize_and_announce", {
            "error": str(e),
            "type": type(e).__name__
        })

    debug_log("=== SUMMARIZE AND ANNOUNCE COMPLETE ===", metadata)
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
    debug_log("### RESPONSE SUMMARY HOOK MAIN STARTED ###")

    try:
        # Read JSON input from stdin
        debug_log("Reading JSON input from stdin")
        input_data = json.loads(sys.stdin.read())
        debug_log("Input data received", {
            "keys": list(input_data.keys()),
            "transcript_path": input_data.get('transcript_path'),
            "session_id": input_data.get('session_id')
        })

        # Get transcript path from input
        transcript_path = input_data.get('transcript_path')

        if not transcript_path:
            debug_log("No transcript path provided, exiting")
            sys.exit(0)  # No transcript path provided

        # Check if response summary is enabled (opt-in via env var)
        enabled = os.getenv('CLAUDE_RESPONSE_SUMMARY_ENABLED', 'false').lower() in ('true', '1', 'yes')
        debug_log("Feature enabled check", {
            "enabled": enabled,
            "env_var": os.getenv('CLAUDE_RESPONSE_SUMMARY_ENABLED', 'not set')
        })

        if not enabled:
            debug_log("Feature disabled, exiting")
            sys.exit(0)  # Feature disabled

        # Acquire exclusive lock to prevent concurrent executions across multiple Claude Code sessions
        lock_file = Path("/tmp/claude_response_summary.lock")
        try:
            lock_fd = open(lock_file, 'w')
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            debug_log("Lock acquired")
        except (IOError, OSError):
            debug_log("Another instance is running, exiting gracefully")
            sys.exit(0)  # Another instance is already playing audio

        try:
            # Summarize and announce the response
            debug_log("Calling summarize_and_announce")
            metadata = summarize_and_announce(transcript_path)
        finally:
            # Release lock
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
                lock_fd.close()
                debug_log("Lock released")
            except:
                pass

        # Debug logging
        script_dir = Path(__file__).parent
        log_dir = script_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "response_summary.jsonl"

        input_data['timestamp'] = datetime.now().isoformat()
        input_data['metadata'] = metadata
        append_log_entry(log_path, input_data)

        debug_log("### RESPONSE SUMMARY HOOK MAIN COMPLETE ###")
        sys.exit(0)

    except json.JSONDecodeError as e:
        # Log JSON errors
        debug_log("ERROR: JSON decode failed", {"error": str(e)})
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
        debug_log("ERROR: Unhandled exception in main", {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": traceback.format_exc()
        })
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
