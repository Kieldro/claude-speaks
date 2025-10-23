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
echo '{"message": "test"}' | python3 notification_fast.py
echo '{"session_id": "123", "stop_hook_active": true}' | python3 stop_fast.py

# Run test suite
python3 test_hooks.py
```

## Architecture

### Daemon-Based System
To prevent Claude Code glitching, hooks use a **signal-based daemon architecture**:

1. **Fast Hooks** (`notification_fast.py`, `stop_fast.py`) - Ultra-fast (<70ms), just touch signal files
2. **TTS Daemon** (`tts_daemon.py`) - Always-running process that watches for signals and plays audio
3. **Zero subprocess spawning** from hooks - prevents Claude Code from detecting child processes

### Scripts
- `notification_fast.py` - Signals daemon when Claude needs input (replaces `notification.py`)
- `stop_fast.py` - Signals daemon when task completes (replaces `stop.py`)
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
- Hooks execute in <70ms (just touch signal files)
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
- If glitches occur, ensure you're using `notification_fast.py` and `stop_fast.py` (not the old versions)

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
