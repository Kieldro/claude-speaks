# Developer Guide

## Quick Reference

### TTS Daemon Management
```bash
# Start daemon (required for hooks to play audio)
./tts_daemon_control.sh start

# Check daemon status
./tts_daemon_control.sh status

# Stop daemon
./tts_daemon_control.sh stop

# Restart daemon
./tts_daemon_control.sh restart
```

### Testing TTS
```bash
python3 utils/tts/cached_tts.py "Test"
python3 utils/tts/system_voice_tts.py "Test"
python3 utils/tts/generate_cache.py
```

### Testing Hooks
```bash
# Manual testing (daemon must be running)
echo '{"message": "test"}' | python3 notification.py
echo '{"session_id": "123", "stop_hook_active": true}' | python3 stop.py

# Run test suite
python3 test_hooks.py
```

## Architecture

### Daemon-Based System
To prevent Claude Code glitching, hooks use a **signal-based daemon architecture**:

1. **Fast Hooks** (`notification.py`, `stop.py`) - Ultra-fast (<1ms), just touch signal files
2. **TTS Daemon** (`tts_daemon.py`) - Always-running process that watches for signals and plays audio
3. **Zero subprocess spawning** from hooks - prevents Claude Code from detecting child processes

### Scripts
- `notification.py` - Ultra-fast hook that signals daemon when Claude needs input (just touches signal file)
- `stop.py` - Ultra-fast hook that signals daemon when task completes (just touches signal file)
- `tts_daemon.py` - Background daemon that plays TTS on signal
- `tts_daemon_control.sh` - Start/stop/restart daemon
- `utils/messages.py` - Shared message definitions
- `utils/tts/cached_tts.py` - Cache-aware TTS wrapper
- `utils/tts/generate_cache.py` - Pre-generate cache for all messages

### Diagnostic Tools
- `test_hooks.py` - Comprehensive test suite for hook functionality

### Cache Structure
```
utils/tts/cache/
├── 21m00Tcm4TlvDq8ikWAM/  # Rachel voice
│   └── {md5_hash}.mp3
├── goT3UYdM9bhm0n2lmKQx/  # Edward voice
│   └── {md5_hash}.mp3
└── ...
```

### Key Behaviors
- Hooks execute in <1ms (just touch signal files)
- No subprocess spawning from hooks (prevents glitching)
- Daemon watches signals every 100ms
- All audio playback handled by daemon
- 30% chance of personalized notification
- Voice ID from `$ELEVENLABS_VOICE_ID` environment variable

### Troubleshooting

**Daemon not running:**
```bash
./tts_daemon_control.sh status  # Check if daemon is running
./tts_daemon_control.sh start   # Start if not running
```

**No audio playing:**
1. Check daemon status: `./tts_daemon_control.sh status`
2. Verify cache exists: `ls -la utils/tts/cache/goT3UYdM9bhm0n2lmKQx/`
3. Regenerate cache: `python3 utils/tts/generate_cache.py`

**Claude Code still glitching:**
- The daemon approach eliminates glitching by avoiding subprocess spawning
- If glitches occur, verify hooks are configured in `~/.claude/settings.json`:
  ```json
  "hooks": {
    "Notification": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/notification.py --notify"}]}],
    "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/stop.py --notify"}]}]
  }
  ```
- Ensure symlinks exist: `ls -la ~/.claude/hooks/` should show `notification.py` and `stop.py` pointing to the repo

## Adding Messages

Edit `utils/messages.py`, then regenerate cache:
```bash
python3 utils/tts/generate_cache.py
```

## Voice Management

Voices in README.md. To add a new voice:
1. Set `ELEVENLABS_VOICE_ID` in `~/.env`
2. Run `python3 utils/tts/generate_cache.py`
3. New folder created: `utils/tts/cache/{voice_id}/`
