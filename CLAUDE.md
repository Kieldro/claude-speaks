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
echo '{"message": "test"}' | python3 notification.py --notify
echo '{"session_id": "123", "stop_hook_active": true}' | python3 stop.py --notify
```

## Architecture

### Scripts
- `notification.py` - Plays TTS when Claude needs input
- `stop.py` - Plays completion message when task done
- `utils/messages.py` - Shared message definitions
- `utils/tts/cached_tts.py` - Cache-aware TTS wrapper
- `utils/tts/generate_cache.py` - Pre-generate cache for all messages

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
- All hooks fail silently (never block Claude Code)
- Logs write to `logs/notification.json` and `logs/stop.json`
- Voice ID extracted from cache path for accurate logging
- 30% chance of personalized notification
- 5% chance of LLM-generated completion message

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
