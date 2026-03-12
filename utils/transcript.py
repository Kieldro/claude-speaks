#!/usr/bin/env python3
"""
Utility for reading and extracting Claude responses from conversation transcripts.
"""

import json
import hashlib
from pathlib import Path
from typing import List, Optional, Union, Tuple


def get_latest_assistant_responses(transcript_path: str, limit: int = 5, return_objects: bool = False) -> List[Union[str, dict]]:
    """
    Extract the latest assistant text responses from a conversation transcript.

    Args:
        transcript_path: Path to the JSONL transcript file
        limit: Maximum number of recent responses to return
        return_objects: If True, returns dicts with {'text': str, 'id': str}, else just text strings

    Returns:
        List of responses (newest first)
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
                                    if return_objects:
                                        # Get ID or fallback to hash of text
                                        msg_id = message.get('id')
                                        if not msg_id:
                                            msg_id = hashlib.md5(text.encode()).hexdigest()
                                        responses.append({'text': text, 'id': msg_id})
                                    else:
                                        responses.append(text)
                                    break  # Only take first text block per message

            except json.JSONDecodeError:
                continue  # Skip malformed lines

    except Exception:
        return []

    return responses


def get_combined_response(transcript_path: str, max_chars: Optional[int] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Get the latest assistant response and its ID.

    Args:
        transcript_path: Path to the JSONL transcript file
        max_chars: Maximum characters to return (None = no limit)

    Returns:
        Tuple of (response_text, response_id) or (None, None) if no responses found
    """
    responses = get_latest_assistant_responses(transcript_path, limit=1, return_objects=True)

    if not responses:
        return None, None

    # Get the latest response (responses[0] because it's reversed/newest-first)
    latest = responses[0]
    text = latest['text']
    msg_id = latest['id']

    # Truncate if max_chars specified
    if max_chars and len(text) > max_chars:
        text = text[:max_chars] + '...'

    return text, msg_id


if __name__ == '__main__':
    # Simple test
    import sys
    if len(sys.argv) > 1:
        transcript = sys.argv[1]
        responses = get_latest_assistant_responses(transcript, return_objects=True)
        print(f"Found {len(responses)} responses:")
        for i, resp in enumerate(responses, 1):
            print(f"\n--- Response {i} (ID: {resp['id']}) ---")
            print(resp['text'][:200] + '...' if len(resp['text']) > 200 else resp['text'])
