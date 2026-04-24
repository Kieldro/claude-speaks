#!/usr/bin/env python3
"""Response summary hook. Uses system python3 with user-installed packages."""

import json
import os
import sys
import subprocess
import signal
import fcntl
import time
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
from voice_selector import (
    get_cartesia_voice_for_transcript,
    get_edge_voice_for_transcript,
    get_openai_voice_for_transcript,
    get_voice_id_for_transcript,
)


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


from topic import get_topic_identifier


def get_tts_script_path(prefer: str = ""):
    """
    Get the TTS script path for summaries.

    `prefer` can be 'edge', 'elevenlabs', or '' (default OpenAI > ElevenLabs > edge > system).
    Defaults to 'edge' for credit conservation when an edge voice is mapped for the model.
    """
    script_dir = Path(__file__).parent
    tts_dir = script_dir / "utils" / "tts"

    if prefer == 'cartesia' and os.getenv('CARTESIA_API_KEY'):
        cartesia_script = tts_dir / "cartesia_tts.py"
        if cartesia_script.exists():
            return str(cartesia_script)

    if prefer == 'edge':
        edge_script = tts_dir / "edge_tts_speak.py"
        if edge_script.exists():
            return str(edge_script)

    if prefer == 'elevenlabs' and os.getenv('ELEVENLABS_API_KEY'):
        elevenlabs_script = tts_dir / "elevenlabs_tts.py"
        if elevenlabs_script.exists():
            return str(elevenlabs_script)

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


def summarize_and_announce(transcript_path: str, cwd: str = None):
    """
    Extract, summarize, and announce Claude's response via TTS.

    Args:
        transcript_path: Path to conversation transcript
        cwd: Working directory of the Claude session

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
        import platform
        if platform.system() == 'Darwin':
            # macOS - use system sound
            subprocess.Popen(
                ['afplay', '/System/Library/Sounds/Ping.aiff'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            # Linux - use freedesktop sound
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
        # The Stop hook fires before the transcript is fully written.
        # Phase 1: wait for new data (file grows from initial size).
        # Phase 2: wait for writes to finish (file size stabilizes).
        transcript_file = Path(transcript_path)
        initial_size = transcript_file.stat().st_size if transcript_file.exists() else 0
        debug_log("Waiting for transcript to be written", {"initial_size": initial_size})

        # Phase 1: wait for file to grow
        grow_delays = [0.1, 0.1, 0.2, 0.3, 0.5, 0.5, 0.5, 0.5]
        for attempt, delay in enumerate(grow_delays):
            time.sleep(delay)
            current_size = transcript_file.stat().st_size if transcript_file.exists() else 0
            if current_size > initial_size:
                debug_log(f"Transcript grew after {attempt + 1} polls", {
                    "grew_by": current_size - initial_size
                })
                break
        else:
            debug_log("Transcript did not grow, reading anyway")

        # Phase 2: wait for file to stabilize (writes complete)
        last_size = transcript_file.stat().st_size if transcript_file.exists() else 0
        for _ in range(10):
            time.sleep(0.1)
            current_size = transcript_file.stat().st_size if transcript_file.exists() else 0
            if current_size == last_size:
                break
            last_size = current_size
        debug_log("Transcript stabilized", {"final_size": last_size})

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
                    lines = result.stdout.strip().splitlines()
                    summary = lines[0]
                    provider = lines[1] if len(lines) > 1 else "unknown"
                    metadata["summary"] = summary
                    metadata["summary_method"] = provider
                    debug_log("Using LLM summary", {"summary": summary, "provider": provider})
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

        # Prepend topic identifier to distinguish sessions
        topic = get_topic_identifier(cwd)
        metadata["topic"] = topic
        debug_log("Topic identifier", {"topic": topic})

        # Show macOS banner notification (title = tmux session, body = summary)
        if sys.platform == 'Darwin':
            try:
                tmux_pane = os.environ.get('TMUX_PANE', '')
                session_name = topic
                if tmux_pane:
                    r = subprocess.run(
                        ['tmux', 'display', '-p', '-t', tmux_pane, '#{session_name}'],
                        capture_output=True, text=True, timeout=1,
                    )
                    if r.returncode == 0 and r.stdout.strip():
                        session_name = r.stdout.strip()

                safe_title = session_name.replace('"', '')
                safe_body = summary.replace('"', '').replace('\\', '')
                subprocess.Popen(
                    ['osascript', '-e',
                     f'display notification "{safe_body}" with title "{safe_title}"'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except Exception as e:
                debug_log("Banner notification failed", {"error": str(e)})

        summary = f"{topic}: {summary}"

        # Speak the summary via TTS (detached process survives hook exit).
        # If a model has a dedicated ElevenLabs voice (e.g. Opus → Max),
        # force ElevenLabs so the voice actually takes effect.
        # Prefer paid ElevenLabs when a per-model voice is mapped (Starter plan).
        # Chain falls through to OpenAI → edge → system_voice on failure (e.g. quota exceeded).
        # Prefer Cartesia (fastest, cheapest) → ElevenLabs → OpenAI → edge → system
        cartesia_override = get_cartesia_voice_for_transcript(transcript_path)
        elevenlabs_override = get_voice_id_for_transcript(transcript_path)
        if cartesia_override and os.getenv('CARTESIA_API_KEY'):
            prefer = 'cartesia'
        elif elevenlabs_override:
            prefer = 'elevenlabs'
        else:
            prefer = ''
        tts_script = get_tts_script_path(prefer=prefer)

        from voice_selector import get_model_from_transcript
        detected_model = get_model_from_transcript(transcript_path) if transcript_path else None
        debug_log("Voice selection", {
            "detected_model": detected_model or "unknown",
            "elevenlabs_voice": elevenlabs_override or "none",
            "prefer": 'elevenlabs' if elevenlabs_override else 'default',
            "tts_script": str(tts_script) if tts_script else "None",
        })

        if tts_script and summary:
            # Fire-and-forget TTS - don't block the hook
            try:
                sanitized_summary = sanitize_text(summary, max_length=500)

                # Build environment with necessary variables.
                # PYTHONPATH is passed explicitly so the spawned TTS subprocess
                # can import user-installed packages (openai, edge_tts) even
                # if HOME/site-packages discovery fails in the hook context.
                # User site-packages first so newer user-installed deps
                # (pydantic, typing_extensions) override older system versions.
                import site
                python_path = ':'.join([site.getusersitepackages()] + site.getsitepackages())
                safe_env = {
                    'PATH': os.environ.get('PATH', ''),
                    'HOME': os.environ.get('HOME', ''),
                    'USER': os.environ.get('USER', ''),
                    'TMPDIR': os.environ.get('TMPDIR', '/tmp'),
                    'TTS_VOLUME': os.getenv('TTS_VOLUME', '0'),
                    'PYTHONPATH': python_path,
                    # macOS audio session
                    'TERM': os.environ.get('TERM', 'xterm-256color'),
                    # Linux audio (PulseAudio/PipeWire)
                    'XDG_RUNTIME_DIR': os.environ.get('XDG_RUNTIME_DIR', ''),
                    'DBUS_SESSION_BUS_ADDRESS': os.environ.get('DBUS_SESSION_BUS_ADDRESS', ''),
                }

                # Set API keys + per-model voice for EVERY backend so the fallback
                # chain (eleven → openai → edge → system) keeps the right voice
                # at whichever level actually plays the audio.
                safe_env['CARTESIA_API_KEY'] = os.getenv('CARTESIA_API_KEY', '')
                safe_env['ELEVENLABS_API_KEY'] = os.getenv('ELEVENLABS_API_KEY', '')
                safe_env['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', '')
                safe_env['OPENAI_TTS_DEBUG'] = os.getenv('OPENAI_TTS_DEBUG', 'false')

                cartesia_voice = get_cartesia_voice_for_transcript(transcript_path) or os.getenv('CARTESIA_VOICE_ID', '')
                eleven_voice = get_voice_id_for_transcript(transcript_path) or os.getenv('ELEVENLABS_VOICE_ID', '')
                openai_voice = get_openai_voice_for_transcript(transcript_path) or os.getenv('OPENAI_TTS_VOICE', 'nova')
                edge_voice = get_edge_voice_for_transcript(transcript_path) or os.getenv('EDGE_TTS_VOICE', 'en-US-AriaNeural')

                debug_log("Spawning TTS (fire-and-forget)", {
                    "script": tts_script,
                    "elevenlabs_voice": eleven_voice or "none",
                    "openai_voice": openai_voice,
                    "edge_voice": edge_voice,
                    "summary": summary,
                })

                if cartesia_voice:
                    safe_env['CARTESIA_VOICE_ID'] = cartesia_voice
                if eleven_voice:
                    safe_env['ELEVENLABS_VOICE_ID'] = eleven_voice
                safe_env['OPENAI_TTS_VOICE'] = openai_voice
                safe_env['EDGE_TTS_VOICE'] = edge_voice

                tts_script_str = str(tts_script)
                if 'cartesia' in tts_script_str:
                    metadata["voice_id"] = cartesia_voice
                elif 'elevenlabs' in tts_script_str:
                    metadata["voice_id"] = eleven_voice
                elif 'openai' in tts_script_str:
                    metadata["voice_id"] = openai_voice
                elif 'edge' in tts_script_str:
                    metadata["voice_id"] = edge_voice

                # Spawn TTS process and don't wait - let it run in background
                subprocess.Popen(
                    [tts_script, sanitized_summary],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=safe_env,
                    start_new_session=True  # Detach from parent
                )
                metadata["tts_triggered"] = True
                debug_log("TTS spawned successfully")

            except Exception as e:
                metadata["tts_triggered"] = False
                metadata["tts_error"] = str(e)
                debug_log("ERROR: TTS spawn failed", {"error": str(e), "type": type(e).__name__})
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

        # Global TTS kill switch
        if os.getenv('CLAUDE_TTS_ENABLED', 'true').lower() not in ('true', '1', 'yes'):
            debug_log("All TTS disabled via CLAUDE_TTS_ENABLED")
            sys.exit(0)

        # Quick disable: touch ~/.claude/no-summary to mute, rm to re-enable
        kill_file = Path.home() / '.claude' / 'no-summary'
        if kill_file.exists():
            debug_log("Disabled via kill file (~/.claude/no-summary)")
            sys.exit(0)

        # Auto-mute when microphone is active (in a call)
        import platform
        if platform.system() == 'Darwin':
            mic_check = Path(__file__).parent / 'utils' / 'mic_active'
            if mic_check.exists():
                try:
                    result = subprocess.run([str(mic_check)], capture_output=True, timeout=1)
                    if result.returncode == 0:  # mic is active
                        debug_log("Auto-muted: microphone in use")
                        sys.exit(0)
                except Exception:
                    pass

        # Check if response summary is enabled (opt-in via env var)
        enabled = os.getenv('CLAUDE_RESPONSE_SUMMARY_ENABLED', 'false').lower() in ('true', '1', 'yes')
        debug_log("Feature enabled check", {
            "enabled": enabled,
            "env_var": os.getenv('CLAUDE_RESPONSE_SUMMARY_ENABLED', 'not set')
        })

        if not enabled:
            debug_log("Feature disabled, exiting")
            sys.exit(0)  # Feature disabled

        # Skip summary if user is actively watching this terminal pane.
        # Canned completion message from stop.py is enough when watching.
        from attention import user_is_watching
        watching = user_is_watching()
        debug_log("User attention check", {"user_watching": watching})
        if watching:
            debug_log("User is watching this pane, skipping summary")
            sys.exit(0)

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
            session_cwd = input_data.get('cwd')
            debug_log("Calling summarize_and_announce", {"session_cwd": session_cwd})
            metadata = summarize_and_announce(transcript_path, cwd=session_cwd)
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
