# Developer Guide

## Quick Reference

### Testing TTS
```bash
python3 utils/tts/cached_tts.py "Test"
python3 utils/tts/system_voice_tts.py "Test"
python3 utils/tts/generate_cache.py
```

### Testing Hooks
```bash
# Manual testing
echo '{"message": "test"}' | python3 notification.py --notify
echo '{"session_id": "123", "stop_hook_active": true}' | python3 stop.py --notify
```

## Architecture

### Direct TTS Approach
Hooks call TTS scripts directly with subprocess, using smart caching for performance:

1. **Hook Scripts** (`notification.py`, `stop.py`) - Read stdin, call TTS, log to `.jsonl`
2. **TTS Caching** (`cached_tts.py`) - MD5-based cache, fallback chain (cache → ElevenLabs → OpenAI → system voice)
3. **LLM Integration** (`utils/llm/`) - Optional dynamic messages (5% frequency, 2s timeout, cached fallback)

### Scripts
- `notification.py` - Plays "your agent needs input" when Claude needs input
- `stop.py` - Plays random completion message when task completes
- `utils/messages.py` - Shared message definitions (20+ completion messages)
- `utils/tts/cached_tts.py` - Cache-aware TTS wrapper
- `utils/tts/generate_cache.py` - Pre-generate cache for all messages
- `utils/tts/elevenlabs_tts.py` - ElevenLabs API client
- `utils/tts/openai_tts.py` - OpenAI TTS client
- `utils/tts/system_voice_tts.py` - Free system voice fallback

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
- Hooks use subprocess to call TTS scripts
- Logging uses efficient append-only `.jsonl` format
- 30% chance of personalized notification
- 5% chance of LLM-generated completion message (95% use cached)
- Voice ID from `$ELEVENLABS_VOICE_ID` environment variable
- 2-second LLM timeout with guaranteed cached fallback

### Troubleshooting

**No audio playing:**
1. Verify cache exists: `ls -la utils/tts/cache/goT3UYdM9bhm0n2lmKQx/`
2. Regenerate cache: `python3 utils/tts/generate_cache.py`
3. Test TTS directly: `python3 utils/tts/cached_tts.py "Test"`

**Hooks not working:**
- Verify hooks are configured in `~/.claude/settings.json`:
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
