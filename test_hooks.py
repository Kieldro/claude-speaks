#!/usr/bin/env python3
"""
Comprehensive test suite for notification.py and stop.py hooks.
Tests hook behavior, timing, error handling, and prevents regressions.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def run_test(name, test_func):
    """Run a single test and print results"""
    try:
        start = time.time()
        test_func()
        duration = time.time() - start
        print(f"{GREEN}✓{RESET} {name} ({duration*1000:.1f}ms)")
        return True
    except AssertionError as e:
        print(f"{RED}✗{RESET} {name}")
        print(f"  {RED}{str(e)}{RESET}")
        return False
    except Exception as e:
        print(f"{RED}✗{RESET} {name}")
        print(f"  {RED}Unexpected error: {type(e).__name__}: {str(e)}{RESET}")
        return False


def test_notification_without_notify():
    """Test notification.py without --notify flag (should be fast, no TTS)"""
    input_data = {"message": "test"}
    result = subprocess.run(
        ["python3", "notification.py"],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=5
    )
    assert result.returncode == 0, f"Exit code {result.returncode}, stderr: {result.stderr}"

    # Check log was written
    log_file = Path("logs/notification.json")
    assert log_file.exists(), "Log file was not created"

    # Verify no TTS was triggered
    with open(log_file) as f:
        log_data = json.load(f)
    assert len(log_data) > 0, "Log data is empty"
    assert 'tts_metadata' not in log_data[-1], "TTS should not be triggered without --notify"


def test_notification_with_notify():
    """Test notification.py with --notify flag (triggers TTS in background)"""
    input_data = {"message": "test notification"}
    start = time.time()
    result = subprocess.run(
        ["python3", "notification.py", "--notify"],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=5
    )
    duration = time.time() - start

    assert result.returncode == 0, f"Exit code {result.returncode}, stderr: {result.stderr}"
    assert duration < 0.5, f"Hook should return immediately (<0.5s), took {duration:.3f}s"

    # Check log contains TTS metadata
    log_file = Path("logs/notification.json")
    with open(log_file) as f:
        log_data = json.load(f)

    last_entry = log_data[-1]
    assert 'tts_metadata' in last_entry, "TTS metadata missing"
    assert 'tts_triggered' in last_entry['tts_metadata'], "tts_triggered field missing"
    assert last_entry['tts_metadata']['subprocess_returncode'] == "fire-and-forget", "Should be fire-and-forget"


def test_notification_timing():
    """Test that notification.py completes quickly without --notify"""
    input_data = {"message": "timing test"}
    start = time.time()
    result = subprocess.run(
        ["python3", "notification.py"],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=5
    )
    duration = time.time() - start

    assert result.returncode == 0, f"Exit code {result.returncode}"
    assert duration < 0.5, f"Hook took too long: {duration:.3f}s (should be <0.5s without TTS)"

    # Check timing log
    timing_log = Path("logs/notification_timing.json")
    if timing_log.exists():
        with open(timing_log) as f:
            timing_data = json.load(f)
        last_timing = timing_data[-1]
        assert 'timings_ms' in last_timing, "Timing data missing"
        assert last_timing['timings_ms']['total'] < 500, "Total time too high"


def test_stop_without_notify():
    """Test stop.py without --notify flag (should be fast, no TTS)"""
    input_data = {"session_id": "test-123", "stop_hook_active": True}
    result = subprocess.run(
        ["python3", "stop.py"],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=5
    )
    assert result.returncode == 0, f"Exit code {result.returncode}, stderr: {result.stderr}"

    # Check log was written
    log_file = Path("logs/stop.json")
    assert log_file.exists(), "Log file was not created"

    # Verify no TTS was triggered
    with open(log_file) as f:
        log_data = json.load(f)
    assert len(log_data) > 0, "Log data is empty"
    assert 'tts_metadata' not in log_data[-1], "TTS should not be triggered without --notify"


def test_stop_with_notify():
    """Test stop.py with --notify flag (triggers TTS in background)"""
    input_data = {"session_id": "test-456", "stop_hook_active": True}
    start = time.time()
    result = subprocess.run(
        ["python3", "stop.py", "--notify"],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=5
    )
    duration = time.time() - start

    assert result.returncode == 0, f"Exit code {result.returncode}, stderr: {result.stderr}"
    assert duration < 0.5, f"Hook should return immediately (<0.5s), took {duration:.3f}s"

    # Check log contains TTS metadata
    log_file = Path("logs/stop.json")
    with open(log_file) as f:
        log_data = json.load(f)

    last_entry = log_data[-1]
    assert 'tts_metadata' in last_entry, "TTS metadata missing"
    assert 'tts_triggered' in last_entry['tts_metadata'], "tts_triggered field missing"
    assert 'message' in last_entry['tts_metadata'], "message field missing"
    assert last_entry['tts_metadata']['subprocess_returncode'] == "fire-and-forget", "Should be fire-and-forget"


def test_stop_timing():
    """Test that stop.py completes quickly without --notify"""
    input_data = {"session_id": "timing-test", "stop_hook_active": True}
    start = time.time()
    result = subprocess.run(
        ["python3", "stop.py"],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=5
    )
    duration = time.time() - start

    assert result.returncode == 0, f"Exit code {result.returncode}"
    assert duration < 0.5, f"Hook took too long: {duration:.3f}s (should be <0.5s without TTS)"

    # Check timing log
    timing_log = Path("logs/stop_timing.json")
    if timing_log.exists():
        with open(timing_log) as f:
            timing_data = json.load(f)
        last_timing = timing_data[-1]
        assert 'timings_ms' in last_timing, "Timing data missing"
        assert last_timing['timings_ms']['total'] < 500, "Total time too high"


def test_notification_malformed_json():
    """Test notification.py handles malformed JSON gracefully"""
    result = subprocess.run(
        ["python3", "notification.py"],
        input="not valid json",
        capture_output=True,
        text=True,
        timeout=5
    )
    # Should exit 0 (fail silently)
    assert result.returncode == 0, "Should handle malformed JSON gracefully"


def test_stop_malformed_json():
    """Test stop.py handles malformed JSON gracefully"""
    result = subprocess.run(
        ["python3", "stop.py"],
        input="not valid json",
        capture_output=True,
        text=True,
        timeout=5
    )
    # Should exit 0 (fail silently)
    assert result.returncode == 0, "Should handle malformed JSON gracefully"


def test_error_logging():
    """Test that errors are properly logged to error log files"""
    # This will likely generate an error if TTS fails
    input_data = {"message": "error test"}
    subprocess.run(
        ["python3", "notification.py", "--notify"],
        input=json.dumps(input_data),
        capture_output=True,
        text=True,
        timeout=15
    )

    # Check if error log exists (it might not if TTS worked)
    error_log = Path("logs/notification_errors.json")
    if error_log.exists():
        with open(error_log) as f:
            error_data = json.load(f)
        assert isinstance(error_data, list), "Error log should be a list"
        if len(error_data) > 0:
            last_error = error_data[-1]
            assert 'timestamp' in last_error, "Error entry missing timestamp"
            assert 'error' in last_error, "Error entry missing error field"


def test_concurrent_hooks():
    """Test multiple hooks running concurrently don't interfere"""
    processes = []
    for i in range(5):
        input_data = {"message": f"concurrent test {i}"}
        p = subprocess.Popen(
            ["python3", "notification.py"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        p.stdin.write(json.dumps(input_data))
        p.stdin.close()
        processes.append(p)

    # Wait for all to complete
    for p in processes:
        return_code = p.wait(timeout=5)
        assert return_code == 0, f"Process failed with code {return_code}"


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("Running Hook Test Suite")
    print("="*60 + "\n")

    tests = [
        ("Notification without --notify", test_notification_without_notify),
        ("Notification with --notify", test_notification_with_notify),
        ("Notification timing", test_notification_timing),
        ("Stop without --notify", test_stop_without_notify),
        ("Stop with --notify", test_stop_with_notify),
        ("Stop timing", test_stop_timing),
        ("Notification handles malformed JSON", test_notification_malformed_json),
        ("Stop handles malformed JSON", test_stop_malformed_json),
        ("Error logging", test_error_logging),
        ("Concurrent hooks", test_concurrent_hooks),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        if run_test(name, test_func):
            passed += 1
        else:
            failed += 1

    print("\n" + "="*60)
    print(f"Results: {GREEN}{passed} passed{RESET}, {RED}{failed} failed{RESET}")
    print("="*60 + "\n")

    if failed > 0:
        sys.exit(1)
    else:
        print(f"{GREEN}All tests passed!{RESET}\n")
        sys.exit(0)


if __name__ == "__main__":
    main()
