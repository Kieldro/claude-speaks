#!/usr/bin/env python3
"""
Utility for reading and extracting Claude responses from conversation transcripts.
"""

import json
import time
from pathlib import Path
from typing import Optional


def _find_current_turn_start(lines: list) -> int:
    """
    Find the index of the last real user message (not a tool_result).
    This marks the start of the current conversation turn.

    Returns:
        Index into lines, or 0 if not found.
    """
    for i in range(len(lines) - 1, -1, -1):
        try:
            entry = json.loads(lines[i].strip())
            if entry.get('type') != 'user' or 'message' not in entry:
                continue
            message = entry['message']
            if message.get('role') != 'user':
                continue
            content = message.get('content', [])
            is_tool_result = any(
                isinstance(b, dict) and b.get('type') == 'tool_result'
                for b in content
            )
            if not is_tool_result:
                return i
        except (json.JSONDecodeError, KeyError):
            continue
    return 0


def _extract_text_from_turn(lines: list, turn_start: int) -> Optional[str]:
    """
    Extract the latest assistant text response from the current turn.

    Args:
        lines: All transcript lines
        turn_start: Index of the current turn's user message

    Returns:
        The latest assistant text response in this turn, or None.
    """
    for i in range(len(lines) - 1, turn_start, -1):
        try:
            entry = json.loads(lines[i].strip())
            if entry.get('type') != 'assistant' or 'message' not in entry:
                continue
            message = entry['message']
            if message.get('role') != 'assistant' or 'content' not in message:
                continue
            for block in message['content']:
                if isinstance(block, dict) and block.get('type') == 'text':
                    text = block.get('text', '').strip()
                    if text:
                        return text
        except (json.JSONDecodeError, KeyError):
            continue
    return None


def get_combined_response(transcript_path: str, max_chars: Optional[int] = None,
                          max_retries: int = 3, retry_delay: float = 0.15) -> Optional[str]:
    """
    Get the latest assistant response from the current turn.

    Only returns responses from after the last real user message to avoid
    returning stale responses from previous turns. Retries briefly if the
    transcript hasn't been flushed yet.

    Args:
        transcript_path: Path to the JSONL transcript file
        max_chars: Maximum characters to return (None = no limit)
        max_retries: Times to retry if current turn has no text response yet
        retry_delay: Seconds to wait between retries

    Returns:
        Latest response text or None if no responses found
    """
    transcript_file = Path(transcript_path)
    if not transcript_file.exists():
        return None

    for attempt in range(max_retries + 1):
        try:
            with open(transcript_file, 'r') as f:
                lines = f.readlines()
        except Exception:
            return None

        turn_start = _find_current_turn_start(lines)
        text = _extract_text_from_turn(lines, turn_start)

        if text:
            if max_chars and len(text) > max_chars:
                text = text[:max_chars] + '...'
            return text

        if attempt < max_retries:
            time.sleep(retry_delay)

    return None


def get_model(transcript_path: str) -> Optional[str]:
    """Extract the model name from the latest assistant message in the transcript.

    Returns:
        Model string (e.g., "claude-opus-4-6", "claude-sonnet-4-6") or None.
    """
    transcript_file = Path(transcript_path)
    if not transcript_file.exists():
        return None

    try:
        with open(transcript_file, 'r') as f:
            lines = f.readlines()
    except Exception:
        return None

    for i in range(len(lines) - 1, -1, -1):
        try:
            entry = json.loads(lines[i].strip())
            if entry.get('type') == 'assistant':
                return entry.get('message', {}).get('model')
        except (json.JSONDecodeError, KeyError):
            continue
    return None


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        text = get_combined_response(sys.argv[1])
        if text:
            print(text[:500] + '...' if len(text) > 500 else text)
        else:
            print("No response found in current turn")
