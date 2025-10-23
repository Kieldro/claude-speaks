#!/usr/bin/env python3
"""
TTS Daemon - Always-running background process that plays audio on signal.
Eliminates hook glitching by removing all subprocess spawning from hooks.

Usage:
    # Start daemon (runs in background)
    python3 tts_daemon.py

    # Or run in foreground for debugging
    python3 tts_daemon.py --foreground
"""
import os
import sys
import time
import random
import subprocess
import hashlib
from pathlib import Path
from datetime import datetime

# Add utils to path for message imports
sys.path.insert(0, str(Path(__file__).parent / "utils"))
from messages import get_completion_messages

SIGNAL_DIR = Path.home() / ".claude" / "tts_signals"
NOTIFY_SIGNAL = SIGNAL_DIR / "notify"
STOP_SIGNAL = SIGNAL_DIR / "stop"
PID_FILE = Path.home() / ".claude" / "tts_daemon.pid"

# Get voice ID from environment or use default
VOICE_ID = os.getenv('ELEVENLABS_VOICE_ID', 'goT3UYdM9bhm0n2lmKQx')
CACHE_DIR = Path(__file__).parent / "utils" / "tts" / "cache" / VOICE_ID


def get_engineer_name():
    """Get engineer name from environment"""
    name = os.getenv('ENGINEER_NAME', '').strip()
    if not name:
        name = os.getenv('USER', '').strip()
    return name


def play_audio(audio_file):
    """Play audio file using afplay (macOS)"""
    try:
        subprocess.run(
            ['afplay', str(audio_file)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10
        )
        return True
    except:
        return False


def handle_notify_signal():
    """Handle notification signal - play 'your agent needs input' message"""
    # 30% chance to personalize
    engineer_name = get_engineer_name()
    personalized = engineer_name and random.random() < 0.3

    if personalized:
        message = f"{engineer_name}, your agent needs your input"
    else:
        message = "Your agent needs your input"

    # Get cached audio file
    message_hash = hashlib.md5(message.encode()).hexdigest()
    audio_file = CACHE_DIR / f"{message_hash}.mp3"

    if audio_file.exists():
        play_audio(audio_file)
    else:
        print(f"[{datetime.now()}] Warning: Audio not cached for: {message}", file=sys.stderr)


def handle_stop_signal():
    """Handle stop signal - play random completion message"""
    messages = get_completion_messages()
    message = random.choice(messages)

    # Get cached audio file
    message_hash = hashlib.md5(message.encode()).hexdigest()
    audio_file = CACHE_DIR / f"{message_hash}.mp3"

    if audio_file.exists():
        play_audio(audio_file)
    else:
        print(f"[{datetime.now()}] Warning: Audio not cached for: {message}", file=sys.stderr)


def check_signals():
    """Check for signal files and handle them"""
    try:
        # Check notify signal
        if NOTIFY_SIGNAL.exists():
            NOTIFY_SIGNAL.unlink()  # Remove signal file
            handle_notify_signal()

        # Check stop signal
        if STOP_SIGNAL.exists():
            STOP_SIGNAL.unlink()  # Remove signal file
            handle_stop_signal()

    except Exception as e:
        print(f"[{datetime.now()}] Error handling signals: {e}", file=sys.stderr)


def write_pid():
    """Write daemon PID to file"""
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))


def cleanup_pid():
    """Remove PID file"""
    try:
        PID_FILE.unlink()
    except:
        pass


def is_running():
    """Check if daemon is already running"""
    if not PID_FILE.exists():
        return False

    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())

        # Check if process exists
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, ValueError):
        # PID file exists but process is dead
        cleanup_pid()
        return False


def daemonize():
    """Fork process to run in background"""
    try:
        pid = os.fork()
        if pid > 0:
            # Parent process - exit
            print(f"TTS Daemon started with PID {pid}")
            sys.exit(0)
    except OSError as e:
        print(f"Fork failed: {e}", file=sys.stderr)
        sys.exit(1)

    # Child process continues
    os.setsid()
    os.chdir('/')

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()
    with open('/dev/null', 'r') as f:
        os.dup2(f.fileno(), sys.stdin.fileno())
    with open('/dev/null', 'a+') as f:
        os.dup2(f.fileno(), sys.stdout.fileno())
        os.dup2(f.fileno(), sys.stderr.fileno())


def main():
    """Main daemon loop"""
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--foreground', action='store_true', help='Run in foreground (for debugging)')
    args = parser.parse_args()

    # Check if already running
    if is_running():
        print("TTS Daemon is already running")
        sys.exit(1)

    # Create signal directory
    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)

    # Daemonize unless in foreground mode
    if not args.foreground:
        daemonize()

    # Write PID file
    write_pid()

    try:
        print(f"[{datetime.now()}] TTS Daemon started", file=sys.stderr)

        # Main loop - check for signals every 100ms
        while True:
            check_signals()
            time.sleep(0.1)

    except KeyboardInterrupt:
        print(f"[{datetime.now()}] TTS Daemon stopping", file=sys.stderr)
    finally:
        cleanup_pid()


if __name__ == '__main__':
    main()
