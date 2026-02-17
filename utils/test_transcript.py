#!/usr/bin/env python3
"""Tests for transcript.py"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from transcript import (
    _find_current_turn_start,
    _extract_text_from_turn,
    get_combined_response,
)


def _make_entry(type_: str, role: str = "", content_types: list = None, text: str = ""):
    """Build a transcript JSONL entry."""
    entry = {"type": type_}
    if role:
        content = []
        for ct in (content_types or []):
            if ct == "text":
                content.append({"type": "text", "text": text})
            elif ct == "tool_use":
                content.append({"type": "tool_use", "id": "x", "name": "Bash", "input": {}})
            elif ct == "tool_result":
                content.append({"type": "tool_result", "tool_use_id": "x", "content": ""})
        entry["message"] = {"role": role, "content": content}
    return json.dumps(entry)


def _write_transcript(lines: list) -> str:
    """Write lines to a temp JSONL file, return path."""
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for line in lines:
        f.write(line + "\n")
    f.close()
    return f.name


# --- _find_current_turn_start ---

def test_find_turn_start_simple():
    lines = [
        _make_entry("user", "user", ["text"], "hello") + "\n",
        _make_entry("assistant", "assistant", ["text"], "hi") + "\n",
    ]
    assert _find_current_turn_start(lines) == 0


def test_find_turn_start_skips_tool_results():
    lines = [
        _make_entry("user", "user", ["text"], "do something") + "\n",
        _make_entry("assistant", "assistant", ["tool_use"]) + "\n",
        _make_entry("user", "user", ["tool_result"]) + "\n",
        _make_entry("assistant", "assistant", ["text"], "done") + "\n",
    ]
    assert _find_current_turn_start(lines) == 0


def test_find_turn_start_multi_turn():
    lines = [
        _make_entry("user", "user", ["text"], "first question") + "\n",
        _make_entry("assistant", "assistant", ["text"], "first answer") + "\n",
        _make_entry("user", "user", ["text"], "second question") + "\n",
        _make_entry("assistant", "assistant", ["tool_use"]) + "\n",
        _make_entry("user", "user", ["tool_result"]) + "\n",
        _make_entry("assistant", "assistant", ["text"], "second answer") + "\n",
    ]
    assert _find_current_turn_start(lines) == 2


def test_find_turn_start_no_user_message():
    lines = [
        _make_entry("assistant", "assistant", ["text"], "hello") + "\n",
    ]
    assert _find_current_turn_start(lines) == 0


# --- _extract_text_from_turn ---

def test_extract_text_simple():
    lines = [
        _make_entry("user", "user", ["text"], "hi") + "\n",
        _make_entry("assistant", "assistant", ["text"], "hello back") + "\n",
    ]
    assert _extract_text_from_turn(lines, 0) == "hello back"


def test_extract_text_skips_tool_use_only():
    lines = [
        _make_entry("user", "user", ["text"], "do it") + "\n",
        _make_entry("assistant", "assistant", ["tool_use"]) + "\n",
        _make_entry("user", "user", ["tool_result"]) + "\n",
        _make_entry("assistant", "assistant", ["text"], "done!") + "\n",
    ]
    assert _extract_text_from_turn(lines, 0) == "done!"


def test_extract_text_returns_none_when_no_text():
    """Simulates the race condition: turn has tool calls but no final text yet."""
    lines = [
        _make_entry("user", "user", ["text"], "do it") + "\n",
        _make_entry("assistant", "assistant", ["tool_use"]) + "\n",
        _make_entry("user", "user", ["tool_result"]) + "\n",
        _make_entry("assistant", "assistant", ["tool_use"]) + "\n",
    ]
    assert _extract_text_from_turn(lines, 0) is None


def test_extract_text_does_not_cross_turn_boundary():
    """The core bug fix: must not return previous turn's response."""
    lines = [
        _make_entry("user", "user", ["text"], "first") + "\n",
        _make_entry("assistant", "assistant", ["text"], "WRONG - previous turn") + "\n",
        _make_entry("user", "user", ["text"], "second") + "\n",  # turn_start = 2
        _make_entry("assistant", "assistant", ["tool_use"]) + "\n",
    ]
    assert _extract_text_from_turn(lines, 2) is None


# --- get_combined_response ---

def test_combined_response_normal():
    path = _write_transcript([
        _make_entry("user", "user", ["text"], "hi"),
        _make_entry("assistant", "assistant", ["text"], "hello"),
    ])
    assert get_combined_response(path) == "hello"
    Path(path).unlink()


def test_combined_response_with_tool_calls():
    path = _write_transcript([
        _make_entry("user", "user", ["text"], "do work"),
        _make_entry("assistant", "assistant", ["tool_use"]),
        _make_entry("user", "user", ["tool_result"]),
        _make_entry("assistant", "assistant", ["tool_use"]),
        _make_entry("user", "user", ["tool_result"]),
        _make_entry("assistant", "assistant", ["text"], "all done"),
    ])
    assert get_combined_response(path) == "all done"
    Path(path).unlink()


def test_combined_response_race_condition_returns_none():
    """Without retries, if final text isn't written yet, returns None (not previous turn)."""
    path = _write_transcript([
        _make_entry("user", "user", ["text"], "first"),
        _make_entry("assistant", "assistant", ["text"], "STALE"),
        _make_entry("user", "user", ["text"], "second"),
        _make_entry("assistant", "assistant", ["tool_use"]),
        _make_entry("user", "user", ["tool_result"]),
    ])
    result = get_combined_response(path, max_retries=0)
    assert result is None  # NOT "STALE"
    Path(path).unlink()


def test_combined_response_retries_on_race_condition():
    """Simulates transcript being flushed during retry."""
    path = _write_transcript([
        _make_entry("user", "user", ["text"], "do it"),
        _make_entry("assistant", "assistant", ["tool_use"]),
    ])

    original_open = open
    call_count = [0]

    def patched_open(filepath, *args, **kwargs):
        f = original_open(filepath, *args, **kwargs)
        if str(filepath) == path and 'r' in (args[0] if args else kwargs.get('mode', 'r')):
            call_count[0] += 1
            if call_count[0] >= 2:
                # Simulate the transcript being updated with the final response
                original_open(path, 'a').write(
                    _make_entry("assistant", "assistant", ["text"], "finally done") + "\n"
                )
        return f

    import builtins
    with patch.object(builtins, 'open', side_effect=patched_open):
        result = get_combined_response(path, max_retries=3, retry_delay=0.01)

    assert result == "finally done"
    Path(path).unlink()


def test_combined_response_max_chars():
    path = _write_transcript([
        _make_entry("user", "user", ["text"], "hi"),
        _make_entry("assistant", "assistant", ["text"], "a" * 200),
    ])
    result = get_combined_response(path, max_chars=50)
    assert result == "a" * 50 + "..."
    Path(path).unlink()


def test_combined_response_missing_file():
    assert get_combined_response("/nonexistent/file.jsonl") is None


def test_combined_response_multi_turn():
    """Multi-turn: returns only the current turn's response."""
    path = _write_transcript([
        _make_entry("user", "user", ["text"], "q1"),
        _make_entry("assistant", "assistant", ["text"], "a1"),
        _make_entry("system"),
        _make_entry("user", "user", ["text"], "q2"),
        _make_entry("assistant", "assistant", ["text"], "a2"),
    ])
    assert get_combined_response(path) == "a2"
    Path(path).unlink()


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
