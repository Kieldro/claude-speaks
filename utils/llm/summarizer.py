#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "requests",
#     "openai",
#     "anthropic",
#     "python-dotenv",
# ]
# ///

import os
import re
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path.home() / '.env')
except ImportError:
    pass

# Shared summarization config
SUMMARY_MAX_TOKENS = 25
SUMMARY_PROMPT = """Condense this AI assistant response into ONE sentence under 8 words. State the key fact or action — not "I did X", just "X". Speak as the assistant. Examples: "Ultrawide 12MP, main 200MP." or "Fixed auth bug via token refresh." Output ONLY the sentence.

<text>
{text}
</text>"""


# Abbreviations to expand for spoken TTS output.
# Keys are matched as whole words (case-insensitive). If a key ends with
# a digit pattern like "(\d+)", it captures trailing numbers so that e.g.
# "5mg" becomes "5 milligrams".
ABBREVIATIONS = {
    # Units of weight / mass
    "oz": "ounces",
    "lbs": "pounds",
    "lb": "pounds",
    "kg": "kilograms",
    "mg": "milligrams",
    "mcg": "micrograms",
    # Units of volume
    "ml": "milliliters",
    "fl": "fluid",
    "tsp": "teaspoon",
    "tbsp": "tablespoon",
    "gal": "gallons",
    # Units of length / distance
    "ft": "feet",
    "cm": "centimeters",
    "mm": "millimeters",
    "km": "kilometers",
    "mi": "miles",
    # Units of time
    "ms": "milliseconds",
    "mins": "minutes",
    "hrs": "hours",
    "hr": "hour",
    "sec": "seconds",
    # Health / fitness
    "bpm": "beats per minute",
    "BF": "body fat",
    "BMI": "body mass index",
    "BMR": "basal metabolic rate",
    "HR": "heart rate",
    "BP": "blood pressure",
    "cal": "calories",
    "kcal": "kilocalories",
    # Tech
    "API": "A P I",
    "APIs": "A P I s",
    "URL": "U R L",
    "URLs": "U R L s",
    "DB": "database",
    "CPU": "C P U",
    "GPU": "G P U",
    "RAM": "ram",
    "PR": "pull request",
    "PRs": "pull requests",
    "CI": "C I",
    "CD": "C D",
    "CLI": "C L I",
    "SDK": "S D K",
    "UI": "U I",
    "UX": "U X",
    "OS": "O S",
    "env": "environment",
    "config": "configuration",
    "configs": "configurations",
    "repo": "repository",
    "repos": "repositories",
    "deps": "dependencies",
    "dep": "dependency",
    "auth": "authentication",
    "impl": "implementation",
    "perf": "performance",
    "mem": "memory",
    "avg": "average",
    "approx": "approximately",
    "info": "information",
    "temp": "temperature",
    "max": "maximum",
    "min": "minimum",
    "num": "number",
    "pct": "percent",
    "vs": "versus",
    "w/": "with",
    "w/o": "without",
    "govt": "government",
    "amt": "amount",
    "qty": "quantity",
    "freq": "frequency",
    "est": "estimated",
    "std": "standard",
    "dev": "deviation",
    "diff": "difference",
    "src": "source",
    "dst": "destination",
    "req": "request",
    "res": "response",
    "err": "error",
    "msg": "message",
    "msgs": "messages",
    "addr": "address",
    "desc": "description",
    "prev": "previous",
    "curr": "current",
    "orig": "original",
    "ver": "version",
    "pkg": "package",
    "pkgs": "packages",
    "dir": "directory",
    "dirs": "directories",
    "ref": "reference",
    "refs": "references",
    "func": "function",
    "funcs": "functions",
    "param": "parameter",
    "params": "parameters",
    "arg": "argument",
    "args": "arguments",
    "var": "variable",
    "vars": "variables",
    "attr": "attribute",
    "attrs": "attributes",
    "prop": "property",
    "props": "properties",
    "elem": "element",
    "elems": "elements",
    "idx": "index",
    "len": "length",
    "val": "value",
    "vals": "values",
    "char": "character",
    "chars": "characters",
    "str": "string",
    "int": "integer",
    "bool": "boolean",
    "obj": "object",
    "objs": "objects",
    "exec": "execution",
    "alloc": "allocation",
    "dealloc": "deallocation",
    "init": "initialization",
    "deinit": "deinitialization",
    "iter": "iteration",
    "async": "asynchronous",
    "sync": "synchronous",
}

# Build a single compiled regex: match abbreviations as whole words.
# Sort by length descending so longer matches win (e.g. "w/o" before "w/").
_ABBREV_PATTERN = re.compile(
    r'\b(' + '|'.join(
        re.escape(k) for k in sorted(ABBREVIATIONS, key=len, reverse=True)
    ) + r')(?=\s|[.,;:!?\'\"/\-]|$)',
    re.IGNORECASE
)

# Separate pattern for number+unit combinations like "5oz", "10kg", "3lbs"
# Includes units too ambiguous as standalone words (e.g. "g") that are
# unambiguous when preceded by a number ("200g" → "200 grams").
_UNIT_ABBREVS = {k: v for k, v in ABBREVIATIONS.items()
                 if v in (
                     "ounces", "pounds", "kilograms", "milligrams", "micrograms",
                     "milliliters", "gallons", "feet", "centimeters",
                     "millimeters", "kilometers", "miles", "milliseconds",
                     "minutes", "hours", "hour", "seconds", "calories",
                     "kilocalories", "beats per minute", "percent",
                 )}
_UNIT_ABBREVS["g"] = "grams"

_NUM_UNIT_PATTERN = re.compile(
    r'(\d+)\s*(' + '|'.join(
        re.escape(k) for k in sorted(_UNIT_ABBREVS, key=len, reverse=True)
    ) + r')(?=\s|[.,;:!?\'\"/\-]|$)',
    re.IGNORECASE
)


def expand_abbreviations(text: str) -> str:
    """Expand abbreviations to full words for natural-sounding TTS."""
    if not text:
        return text

    def _num_unit_repl(m):
        number = m.group(1)
        unit = m.group(2)
        expanded = (_UNIT_ABBREVS.get(unit) or _UNIT_ABBREVS.get(unit.lower())
                    or ABBREVIATIONS.get(unit) or ABBREVIATIONS.get(unit.lower(), unit))
        return f"{number} {expanded}"

    # First expand number+unit combos (e.g. "5oz" → "5 ounces")
    text = _NUM_UNIT_PATTERN.sub(_num_unit_repl, text)

    def _word_repl(m):
        word = m.group(1)
        # Look up case-insensitive
        expanded = ABBREVIATIONS.get(word) or ABBREVIATIONS.get(word.lower())
        if not expanded:
            return word
        # Preserve capitalization of first letter
        if word[0].isupper() and not expanded[0].isupper():
            return expanded[0].upper() + expanded[1:]
        return expanded

    text = _ABBREV_PATTERN.sub(_word_repl, text)

    return text


def summarize_with_groq(text: str, timeout: int = 5) -> str:
    """Summarize text using Groq (fastest cloud inference, ~0.5s)."""
    try:
        from openai import OpenAI

        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            return None

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.groq.com/openai/v1",
            timeout=timeout
        )

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Fast model
            messages=[{"role": "user", "content": SUMMARY_PROMPT.format(text=text)}],
            max_tokens=SUMMARY_MAX_TOKENS,
            temperature=0.3,
        )

        summary = response.choices[0].message.content.strip()
        # Remove quotes if present
        summary = summary.strip('"').strip("'")
        return summary

    except Exception:
        return None


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
            messages=[{"role": "user", "content": SUMMARY_PROMPT.format(text=text)}],
            max_tokens=SUMMARY_MAX_TOKENS,
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
            max_tokens=SUMMARY_MAX_TOKENS,
            temperature=0.3,
            messages=[{"role": "user", "content": SUMMARY_PROMPT.format(text=text)}]
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


def summarize_response(text: str, timeout: int = 8) -> tuple[str, str]:
    """
    Summarize Claude's response in one concise sentence, in Claude Code's voice.

    Tries LLMs in order: Anthropic -> OpenAI -> Groq -> Simple truncation

    Args:
        text: The response text to summarize
        timeout: Timeout in seconds for LLM calls

    Returns:
        Tuple of (summary, provider) where provider is the name of the model used
    """
    if not text or not text.strip():
        return "Task complete", "default"

    # Short responses don't need summarization - use as-is
    words = text.split()
    if len(words) <= 12:
        return expand_abbreviations(text.strip()), "passthrough"

    # Try Anthropic first (good quality, ~0.8s warm)
    summary = summarize_with_anthropic(text, timeout)
    if summary:
        return expand_abbreviations(summary), "anthropic/claude-3-5-haiku"

    # Try OpenAI as fallback
    summary = summarize_with_openai(text, timeout)
    if summary:
        return expand_abbreviations(summary), "openai/gpt-4o-mini"

    # Try Groq last (fast but lower quality)
    summary = summarize_with_groq(text, timeout=5)
    if summary:
        return expand_abbreviations(summary), "groq/llama-3.1-8b"

    # Simple truncation fallback
    return expand_abbreviations(simple_summarize(text)), "truncation"


def main():
    """Test the summarizer from command line."""
    if len(sys.argv) > 1:
        text = " ".join(sys.argv[1:])
        summary, provider = summarize_response(text)
        print(summary)
        print(provider)
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
        summary, provider = summarize_response(sample)
        print(f"\nSummary: {summary}")
        print(f"Provider: {provider}")


if __name__ == "__main__":
    main()
