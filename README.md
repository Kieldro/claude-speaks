# Claude Code Hooks

Custom notification and completion hooks for Claude Code with Text-to-Speech (TTS) support and LLM-generated messages.

## Features

- 🔔 **Smart Notifications**: Audio alerts when Claude needs your input
- 🎵 **Pre-cached Voices**: 4 voices with 20+ messages ready to use (no API keys needed!)
- 🎉 **Completion Messages**: Cached messages + optional LLM-generated unique messages
- 🤖 **LLM Integration**: Optional unique messages via OpenAI/Anthropic/Ollama
- ⚡ **Fast Fallback**: 2-second timeout, guaranteed cached fallback
- 🗣️ **Multi-voice Support**: Rachel, Edward, Laura, George - switch anytime

## Requirements

- Python 3.11 or higher
- macOS, Linux, or Windows WSL
- [uv](https://docs.astral.sh/uv/) - Fast Python package installer (scripts auto-install dependencies)
- Audio player: `afplay` (macOS), `mpg123`, or `ffplay` (Linux)

## Installation

### 1. Install dependencies (if needed)

```bash
# Install uv (Python package manager)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Clone and set up symlinks

```bash
# Clone repository
git clone https://github.com/Kieldro/claude-speaks.git ~/repos/claude-speaks

# Backup existing hooks (optional)
mv ~/.claude/hooks ~/.claude/hooks-backup

# Create symlinks
mkdir -p ~/.claude/hooks
ln -s ~/repos/claude-speaks/notification.py ~/.claude/hooks/notification.py
ln -s ~/repos/claude-speaks/stop.py ~/.claude/hooks/stop.py
ln -s ~/repos/claude-speaks/utils ~/.claude/hooks/utils
```

### 3. Configure Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "hooks": {
    "Notification": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 ~/.claude/hooks/notification.py --notify"
      }]
    }],
    "Stop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 ~/.claude/hooks/stop.py --notify"
      }]
    }]
  }
}
```

### 4. Test it!

```bash
python3 ~/repos/claude-speaks/utils/tts/system_voice_tts.py "Hello from Claude"
```

**Basic setup complete!** The hooks work immediately with:
- **4 pre-cached voices** (Rachel, Edward, Laura, George) - no API keys needed
- **20+ completion messages** already cached as MP3 files
- **System voice fallback** for any uncached messages

### 5. Optional: Add API keys for custom voices or new messages

Only needed if you want to generate cache for different voices or add new messages.

Add to `~/.env`:

```bash
# Required for LLM-generated completion messages (optional)
OPENAI_API_KEY=sk-...

# Optional: For ElevenLabs TTS (higher quality voices)
ELEVENLABS_API_KEY=...

# Optional: Choose ElevenLabs voice (requires ELEVENLABS_API_KEY)
# Available voices:
# ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Rachel - Professional female (default)
# ELEVENLABS_VOICE_ID=goT3UYdM9bhm0n2lmKQx  # Edward - British, Dark, Low
# ELEVENLABS_VOICE_ID=FGY2WhTYpPnrIDTdsKH5  # Laura - Sunny
# ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb  # George - Hari Seldon-like

# Optional: Customize your name in notifications
# ENGINEER_NAME=YourName  # Falls back to $USER if not set
```

### 6. Optional: Generate cache for new voices

If you want to use a different voice or add new messages:

```bash
# Set your preferred voice in ~/.env first
# ELEVENLABS_VOICE_ID=<voice_id>

python3 ~/repos/claude-speaks/utils/tts/generate_cache.py
```

This generates cache files for your selected voice.

## How It Works

### Notification Hook

Plays audio when Claude needs your input:
- **70%**: "Your agent needs your input" (generic)
- **30%**: "YourName, your agent needs your input" (personalized)

### Stop Hook

Plays audio when tasks complete:
- **95%**: Random cached message (instant, free)
- **5%**: LLM-generated unique message (~$0.001, requires API key)

If LLM takes >2 seconds, automatically falls back to cached message.

### TTS Priority

1. **ElevenLabs** (if `ELEVENLABS_API_KEY` set) - High quality, cacheable
2. **OpenAI** (if `OPENAI_API_KEY` set) - Good quality, not cacheable
3. **System voice** (spd-say/espeak) - Free fallback

### LLM Priority (for completion messages)

1. **OpenAI** (if `OPENAI_API_KEY` set)
2. **Anthropic** (if `ANTHROPIC_API_KEY` set)
3. **Ollama** (local LLM)
4. **Cached messages** (guaranteed fallback)

## File Structure

```
claude-hooks/
├── notification.py          # Notification hook (when Claude needs input)
├── stop.py                  # Stop hook (when tasks complete)
├── utils/
│   ├── tts/
│   │   ├── cached_tts.py           # TTS caching wrapper
│   │   ├── elevenlabs_tts.py       # ElevenLabs TTS
│   │   ├── openai_tts.py           # OpenAI TTS
│   │   ├── system_voice_tts.py     # System voice fallback
│   │   ├── generate_cache.py       # Pre-generate all cached audio
│   │   ├── check_and_play_cache.py # Test cached messages
│   │   ├── benchmark_cache.py      # Benchmark cache vs API
│   │   ├── cache/                  # Cached MP3 files (not in git)
│   │   └── CACHE_README.md         # Cache documentation
│   └── llm/
│       ├── oai.py                  # OpenAI LLM integration
│       ├── anth.py                 # Anthropic LLM integration
│       └── ollama.py               # Ollama LLM integration
├── .gitignore
└── README.md
```

## Configuration

### Adjust LLM Frequency

Edit `stop.py` line 26:

```python
LLM_TIMEOUT = 2  # Seconds before fallback to cached
```

Edit `stop.py` line 160:

```python
if random.random() < 0.05:  # Change 0.05 to adjust percentage
```

### Adjust Notification Personalization

Edit `notification.py` line 72:

```python
if engineer_name and random.random() < 0.3:  # Change 0.3 to adjust percentage
```

### Add More Completion Messages

Edit `stop.py` `get_completion_messages()` function and regenerate cache:

```bash
python3 ~/.claude/hooks/utils/tts/generate_cache.py
```

## Utilities

### Generate/Regenerate Cache

```bash
python3 ~/.claude/hooks/utils/tts/generate_cache.py
```

### Test All Cached Messages

```bash
python3 ~/.claude/hooks/utils/tts/check_and_play_cache.py
```

### Benchmark Cache Performance

```bash
python3 ~/.claude/hooks/utils/tts/benchmark_cache.py
```

## Cache Statistics

- **Total messages**: 22 (1 notification generic + 1 personalized + 20 completion)
- **Cache size**: ~420 KB
- **API savings**: ~$0.0025 per cached message
- **Speed improvement**: ~580ms faster (cache vs API)

## Troubleshooting

**No audio playing:**
- Check audio players installed: `mpg123`, `ffplay`, or `afplay` (macOS)
- Test TTS: `python3 ~/.claude/hooks/utils/tts/cached_tts.py "Test message"`

**LLM messages not working:**
- Verify API key: `echo $OPENAI_API_KEY`
- Check API key in `~/.env` (hooks read from here, not `~/.bashrc`)
- Test directly: `~/.claude/hooks/utils/llm/oai.py --completion`

**Hooks not triggering:**
- Verify `~/.claude/settings.json` configuration
- Check symlinks: `ls -la ~/.claude/hooks/`
- Check hooks are executable: `chmod +x ~/.claude/hooks/*.py`

## Cost Analysis

**TTS Costs:**
- ElevenLabs: ~$0.18 per 1000 characters
- OpenAI: ~$0.015 per message
- System voice: Free
- Cached playback: Free (no API calls)

**LLM Costs (5% frequency):**
- OpenAI GPT-4o-mini: ~$0.001 per completion message
- Average cost per 100 completions: ~$0.05

## Contributing

Feel free to fork and customize for your needs!

## License

MIT
