#!/usr/bin/env python3
"""
Ultra-fast stop hook (<1ms) - signals daemon via file touch.
No subprocess spawning, no blocking, no file I/O beyond signal file.
"""
import sys
from pathlib import Path

def main():
    try:
        # Consume stdin (required by hook protocol)
        sys.stdin.read()

        # Touch signal file to notify daemon
        signal_dir = Path.home() / ".claude" / "tts_signals"
        signal_dir.mkdir(parents=True, exist_ok=True)
        (signal_dir / "stop").touch()

    except:
        pass  # Fail silently

    sys.exit(0)

if __name__ == '__main__':
    main()
