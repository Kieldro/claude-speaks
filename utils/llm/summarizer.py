#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "openai",
#     "anthropic",
#     "python-dotenv",
# ]
# ///

import os
import sys
import random
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.env')
except ImportError:
    pass

# Import completion messages for fallback
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from messages import get_completion_messages
except ImportError:
    get_completion_messages = None


def summarize_with_openai(text: str, timeout: int = 8) -> str:
    """Summarize text using OpenAI (gpt-4o-mini)."""
    try:
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None

        client = OpenAI(api_key=api_key, timeout=timeout)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{
                "role": "user",
                "content": f"""Summarize this in 3-5 words. Focus on the main action/result only.

{text}

3-5 word summary:"""
            }],
            max_tokens=15,
            temperature=0.3,
        )

        summary = response.choices[0].message.content.strip()
        # Remove quotes if present
        summary = summary.strip('"').strip("'")
        return summary

    except Exception:
        return None


def summarize_with_anthropic(text: str, timeout: int = 2) -> str:
    """Summarize text using Anthropic (claude-haiku)."""
    try:
        from anthropic import Anthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return None

        client = Anthropic(api_key=api_key, timeout=timeout)

        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=30,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": f"""Summarize this AI assistant response in ONE short sentence (max 12 words).
Focus on what action was completed or what information was provided.
Be concise and natural-sounding for text-to-speech.

Response to summarize:
{text}

Summary:"""
            }]
        )

        summary = response.content[0].text.strip()
        # Remove quotes if present
        summary = summary.strip('"').strip("'")
        return summary

    except Exception:
        return None


def simple_summarize(text: str, max_words: int = 12) -> str:
    """Simple fallback: take first N words and add ellipsis if truncated."""
    words = text.split()
    if len(words) <= max_words:
        return text

    # Take first max_words and add ellipsis
    summary = ' '.join(words[:max_words])

    # Try to end on a complete thought (look for sentence ending)
    for i in range(max_words - 1, max(0, max_words - 4), -1):
        if words[i].rstrip().endswith(('.', '!', ':')):
            summary = ' '.join(words[:i+1])
            break

    return summary


def summarize_response(text: str, timeout: int = 8) -> str:
    """
    Summarize Claude's response in one short sentence.

    Tries LLMs in order: OpenAI -> Anthropic -> Completion messages

    Args:
        text: The response text to summarize
        timeout: Timeout in seconds for LLM calls

    Returns:
        A short summary sentence (12 words or less)
    """
    if not text or not text.strip():
        return "Task complete"

    # Try OpenAI first (user has this API key)
    summary = summarize_with_openai(text, timeout)
    if summary:
        return summary

    # Try Anthropic as fallback
    summary = summarize_with_anthropic(text, timeout)
    if summary:
        return summary

    # Final fallback: use completion messages
    if get_completion_messages:
        messages = get_completion_messages()
        return random.choice(messages)
    else:
        return "Task complete"


def main():
    """Test the summarizer from command line."""
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        summary = summarize_response(text)
        print(summary)
    else:
        # Test with sample text
        sample = """I'll add the cached sound files to .gitignore and commit the changes.

Done! I've:

1. Added `utils/tts/cache/` to `.gitignore` to exclude all cached audio files
2. Committed all changes with a note highlighting Linux-specific improvements

The commit includes:
- **Linux audio improvements**: ffplay as primary player (better PipeWire support), environment variable preservation
- Enhanced logging in `stop.py` with metadata and error tracking"""

        print("Sample text:", sample[:100] + "...")
        print("\nSummary:", summarize_response(sample))


if __name__ == "__main__":
    main()
