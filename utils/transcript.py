#!/usr/bin/env python3
"""
Utility for reading and extracting Claude responses from conversation transcripts.
"""

import json
from pathlib import Path
from typing import List, Optional


def get_latest_assistant_responses(transcript_path: str, limit: int = 5) -> List[str]:
    """
    Extract the latest assistant text responses from a conversation transcript.

    Args:
        transcript_path: Path to the JSONL transcript file
        limit: Maximum number of recent responses to return

    Returns:
        List of text responses from assistant (newest first)
    """
    transcript_file = Path(transcript_path)
    if not transcript_file.exists():
        return []

    responses = []

    try:
        # Read transcript in reverse to get latest messages first
        with open(transcript_file, 'r') as f:
            lines = f.readlines()

        # Process lines in reverse order
        for line in reversed(lines):
            if len(responses) >= limit:
                break

            try:
                entry = json.loads(line.strip())

                # Look for assistant messages with text content
                if entry.get('type') == 'assistant' and 'message' in entry:
                    message = entry['message']
                    if message.get('role') == 'assistant' and 'content' in message:
                        # Extract text blocks from content
                        for content_block in message['content']:
                            if isinstance(content_block, dict) and content_block.get('type') == 'text':
                                text = content_block.get('text', '').strip()
                                if text:
                                    responses.append(text)
                                    break  # Only take first text block per message

            except json.JSONDecodeError:
                continue  # Skip malformed lines

    except Exception:
        return []

    return responses


def get_combined_response(transcript_path: str, max_chars: Optional[int] = None) -> Optional[str]:
    """
    Get the latest assistant responses combined into a single text.

    Args:
        transcript_path: Path to the JSONL transcript file
        max_chars: Maximum characters to return (None = no limit)

    Returns:
        Combined response text or None if no responses found
    """
    responses = get_latest_assistant_responses(transcript_path, limit=3)

    if not responses:
        return None

    # Combine responses (newest first, so reverse to get chronological order)
    combined = '\n\n'.join(reversed(responses))

    # Truncate if max_chars specified
    if max_chars and len(combined) > max_chars:
        combined = combined[:max_chars] + '...'

    return combined


if __name__ == '__main__':
    # Simple test
    import sys
    if len(sys.argv) > 1:
        transcript = sys.argv[1]
        responses = get_latest_assistant_responses(transcript)
        print(f"Found {len(responses)} responses:")
        for i, resp in enumerate(responses, 1):
            print(f"\n--- Response {i} ---")
            print(resp[:200] + '...' if len(resp) > 200 else resp)
