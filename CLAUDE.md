# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Claude Code hooks with TTS notifications and LLM-generated completion messages. See README.md for user-facing documentation.

## Development Commands

### Testing
```bash
# Test specific TTS backends
python3 utils/tts/cached_tts.py "Test message"
python3 utils/tts/elevenlabs_tts.py "Test message"
python3 utils/tts/openai_tts.py "Test message"
python3 utils/tts/system_voice_tts.py "Test message"

# Test LLM backends
python3 utils/llm/oai.py --completion        # OpenAI completion message
python3 utils/llm/oai.py --agent-name        # Generate agent name
python3 utils/llm/anth.py --completion       # Anthropic completion
python3 utils/llm/ollama.py --completion     # Ollama completion

# Cache operations
python3 utils/tts/generate_cache.py          # Regenerate all cached audio
python3 utils/tts/check_and_play_cache.py    # Play all cached messages
python3 utils/tts/benchmark_cache.py         # Benchmark cache vs API
```

### Hook Testing
```bash
# Simulate hook triggers by passing JSON via stdin
echo '{"message": "test"}' | python3 notification.py --notify
echo '{"session_id": "123", "stop_hook_active": true}' | python3 stop.py --notify
echo '{"session_id": "123", "transcript_path": "/path/to/transcript.jsonl"}' | python3 stop.py --chat
```

## Architecture

### Script Execution Model
All scripts use `#!/usr/bin/env -S uv run --script` with inline dependencies (PEP 723):
```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["python-dotenv", "openai"]
# ///
```
This eliminates need for requirements.txt or virtual environments.

### Hook Entry Points
- **notification.py**: Claude Code `Notification` hook → `announce_notification()` → `get_tts_script_path()`
- **stop.py**: Claude Code `Stop` hook → `announce_completion()` → `get_llm_completion_message()` → `get_tts_script_path()`

### Priority Chains
Both hooks use identical `get_tts_script_path()` function:
1. `cached_tts.py` (checks MD5 cache, fallback to API)
2. `elevenlabs_tts.py` (if `ELEVENLABS_API_KEY`)
3. `openai_tts.py` (if `OPENAI_API_KEY`)
4. `system_voice_tts.py` (say/spd-say/espeak)

LLM chain in `stop.py`:
1. `oai.py` (if `OPENAI_API_KEY`, uses gpt-4o-mini)
2. `anth.py` (if `ANTHROPIC_API_KEY`)
3. `ollama.py` (local LLM)
4. Random from `get_completion_messages()` (guaranteed fallback)

### Cache Implementation
- **Location:** `utils/tts/cache/{md5(text)}.mp3`
- **Only ElevenLabs is cacheable** (returns MP3 binary; OpenAI streams)
- **Cache workflow:** `cached_tts.py` → check cache → if miss, call `generate_and_cache_audio()` → save MP3 → play
- **Pre-generation:** `generate_cache.py` iterates all known messages and pre-caches them

## Key Configuration Points

### Tunable Percentages
```python
# notification.py:72 - Personalization frequency
if engineer_name and random.random() < 0.3:  # 30% personalized

# stop.py:164 - LLM generation frequency
if random.random() < 0.05:  # 5% LLM, 95% cached
```

### Tunable Constants
```python
# stop.py:26 - LLM timeout before fallback
LLM_TIMEOUT = 2  # seconds

# All scripts use 10s timeout for TTS/subprocess calls
timeout=10
```

### Message Customization
**To add new completion messages:**
1. Edit `stop.py` function `get_completion_messages()` (line 29-52)
2. Run `python3 utils/tts/generate_cache.py` to pre-cache new messages
3. Cached messages returned when LLM fails/times out

### Voice Selection
ElevenLabs voices (set `ELEVENLABS_VOICE_ID` in `~/.env`):
- `21m00Tcm4TlvDq8ikWAM` - Rachel (default, professional female)
- `goT3UYdM9bhm0n2lmKQx` - Edward (British, dark, low)
- `ZF6FPAbjXT4488VcRRnw` - Amelia (British)

See `cached_tts.py:107` for voice configuration.

## Important Behaviors

### notification.py
- Skips TTS if message is exactly `"Claude is waiting for your input"` (line 128)
- Reads `ENGINEER_NAME` env var, falls back to `USER` (line 67-69)
- All notifications logged to `logs/notification.json` as JSON array

### stop.py
- With `--chat` flag: converts transcript `.jsonl` to `logs/chat.json` array (line 226-246)
- LLM calls use `subprocess.run()` with `timeout=LLM_TIMEOUT` (line 110-150)
- All completions logged to `logs/stop.json` as JSON array

### cached_tts.py
- Audio playback priority: `afplay` (macOS) → `mpg123` (Linux) → `ffplay` (fallback)
- If cache miss and no `ELEVENLABS_API_KEY`, falls back to non-cached TTS
- Function `generate_and_cache_audio()` (line 90) handles ElevenLabs API calls

## Error Handling Philosophy

All scripts fail silently for production use:
- Wrap all operations in try/except with `pass`
- Use `capture_output=True` to suppress subprocess output
- Exit with `sys.exit(0)` even on errors (hooks should never block Claude Code)
- Only `system_voice_tts.py` prints errors (for debugging when called directly)
