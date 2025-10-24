# Claude Code Hooks

Custom notification and completion hooks for Claude Code with Text-to-Speech (TTS) support and LLM-generated messages.

## Features

- Audio notifications when Claude needs input
- Pre-cached MP3 files for 4 ElevenLabs voices (Rachel, Edward, Laura, George)
- 20+ completion messages with optional LLM generation (5% frequency)
- Multiple TTS fallbacks: ElevenLabs → OpenAI → system voice
- 2-second LLM timeout with cached fallback
- Optional session identifiers using NATO phonetic alphabet

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
        "command": "python3 ~/.claude/hooks/notification.py"
      }]
    }],
    "Stop": [{
      "matcher": "",
      "hooks": [{
        "type": "command",
        "command": "python3 ~/.claude/hooks/stop.py"
      }]
    }]
  }
}
```

### 4. Test it!

```bash
python3 ~/repos/claude-speaks/utils/tts/system_voice_tts.py "Hello from Claude"
```

The hooks will use pre-cached MP3 files if available, falling back to system voice otherwise. Pre-cached files are included for 4 ElevenLabs voices with 20+ messages.

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

# Optional: Enable session identifiers in completion messages
# CLAUDE_SESSION_ID_ENABLED=true  # Adds "Alpha 3: Task complete!" style prefixes
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
- 70%: "Your agent needs your input" (generic)
- 30%: "YourName, your agent needs your input" (personalized, if ENGINEER_NAME set)

### Stop Hook

Plays audio when tasks complete:
- 100%: Random cached message from pre-generated set
- Optional: Session identifiers (e.g., "Alpha 3: Task complete!") with CLAUDE_SESSION_ID_ENABLED=true

Note: LLM generation was removed in performance optimization to prevent hook delays that could trigger infinite loops.

### TTS Priority

1. ElevenLabs (if ELEVENLABS_API_KEY set) - cacheable
2. OpenAI (if OPENAI_API_KEY set) - not cacheable
3. System voice (spd-say/espeak/say) - fallback

### LLM Integration (Disabled)

LLM-generated completion messages have been disabled for performance:
- Previously caused 2+ second hook delays
- Could trigger Claude Code infinite loop bug
- All completion messages now use pre-cached set (20+ messages)

## File Structure

```
claude-hooks/
├── notification.py          # Notification hook (when Claude needs input)
├── stop.py                  # Stop hook (when tasks complete)
├── utils/
│   ├── messages.py                 # Shared message definitions
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

### Re-enable LLM Generation (Not Recommended)

LLM generation is disabled for performance. To re-enable (may cause infinite loops):

1. Change `stop.py` line 215 from `select_completion_message_fast` to `select_completion_message`
2. Adjust frequency at line 174: `if random.random() < 0.05:`

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

- Total messages: 22 (1 notification generic + 1 personalized + 20 completion)
- Cache size: ~420 KB
- Speed: ~580ms faster than API calls

## Performance

**Hook Execution Time:**
- Hooks complete in ~166ms (fire-and-forget design)
- TTS and audio playback happen in background process
- File I/O logging disabled to prevent blocking
- LLM generation removed (was causing 2+ second delays)

**Infinite Loop Mitigation:**
- Previous versions could trigger infinite loops due to slow hook execution
- Current implementation uses non-blocking subprocess spawning
- Hooks exit immediately after spawning TTS process
- Issue: https://github.com/anthropics/claude-code/issues/10205

## Troubleshooting

**No audio playing:**
- Check audio players installed: `mpg123`, `ffplay`, or `afplay` (macOS)
- Test TTS: `python3 ~/.claude/hooks/utils/tts/cached_tts.py "Test message"`

**Want different completion messages:**
- Edit `utils/messages.py` to add/remove messages
- Run `python3 utils/tts/generate_cache.py` to regenerate cache

**Hooks not triggering:**
- Verify `~/.claude/settings.json` configuration
- Check symlinks: `ls -la ~/.claude/hooks/`
- Check hooks are executable: `chmod +x ~/.claude/hooks/*.py`

## Cost Analysis

**Runtime Costs:**
- All messages use pre-cached MP3 files: Free
- No API calls during normal operation: Free

**One-time Setup Costs (optional):**
- Generating cache with ElevenLabs: ~$0.18 per 1000 characters
- Pre-cached voices included in repo (no setup cost)

## Contributing

Feel free to fork and customize for your needs!

## License

MIT
