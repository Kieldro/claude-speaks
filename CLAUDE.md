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
echo '{"message": "test"}' | python3 notification.py
echo '{"session_id": "abc123"}' | python3 stop.py  # Default: "Task complete!"

# With session identifiers enabled
export CLAUDE_SESSION_ID_ENABLED=true
echo '{"session_id": "abc123"}' | python3 stop.py  # "Papa 0: Job complete!"

# With response summary enabled
export CLAUDE_RESPONSE_SUMMARY_ENABLED=true
echo '{"transcript_path": "path/to/transcript.jsonl", "session_id": "abc123"}' | python3 response_summary.py
```

## Architecture

### Direct TTS Approach
Hooks call TTS scripts directly with subprocess, using smart caching for performance:

1. **Hook Scripts** (`notification.py`, `stop.py`) - Read stdin, call TTS, log to `.jsonl`
2. **TTS Caching** (`cached_tts.py`) - MD5-based cache, fallback chain (cache → ElevenLabs → OpenAI → system voice)
3. **LLM Integration** (`utils/llm/`) - Optional dynamic messages (5% frequency, 2s timeout, cached fallback)

### Scripts
- `notification.py` - Plays "your agent needs input" when Claude needs input
- `stop.py` - Plays completion message, optionally with session identifier (e.g., "Charlie 1: Task complete!")
- `response_summary.py` - Summarizes Claude's response and speaks it (opt-in via `CLAUDE_RESPONSE_SUMMARY_ENABLED`)
- `utils/messages.py` - Shared message definitions (20+ completion messages)
- `utils/transcript.py` - Extract Claude responses from conversation transcripts
- `utils/llm/summarizer.py` - LLM-based text summarization (with fallback)
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
- **Session identifiers (opt-in)**: Set `CLAUDE_SESSION_ID_ENABLED=true` in `~/.env`
  - Uses NATO phonetic alphabet + number (e.g., "Alpha 3", "Charlie 1")
  - Each session gets consistent identifier via MD5 hash (4-6 syllables total)
  - 260 unique combinations (low collision for <10 concurrent sessions)
- **Response summarization (opt-in)**: Set `CLAUDE_RESPONSE_SUMMARY_ENABLED=true` in `~/.env`
  - Extracts Claude's latest response from conversation transcript
  - Summarizes to 1 short sentence using LLM (OpenAI → Anthropic → simple fallback)
  - Speaks summary via TTS when Stop hook fires
  - 2-second LLM timeout with guaranteed fallback
- 5% chance of LLM-generated completion message (95% use cached)
- Voice ID from `$ELEVENLABS_VOICE_ID` environment variable

### Troubleshooting

**No audio playing:**
1. Verify cache exists: `ls -la utils/tts/cache/goT3UYdM9bhm0n2lmKQx/`
2. Regenerate cache: `python3 utils/tts/generate_cache.py`
3. Test TTS directly: `python3 utils/tts/cached_tts.py "Test"`

**Hooks not working:**
- Verify hooks are configured in `~/.claude/settings.json`:
  ```json
  "hooks": {
    "Notification": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/notification.py"}]}],
    "Stop": [{"matcher": "", "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/stop.py"}]}]
  }
  ```
- For response summarization, add both hooks to Stop:
  ```json
  "Stop": [{"matcher": "", "hooks": [
    {"type": "command", "command": "python3 ~/.claude/hooks/stop.py"},
    {"type": "command", "command": "python3 ~/.claude/hooks/response_summary.py"}
  ]}]
  ```
- Ensure symlinks exist: `ls -la ~/.claude/hooks/` should show hook scripts pointing to the repo

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
