"""
End-to-end test of the Stop hook path.

For each Claude model, we:
  1. Build a fixture transcript under tests/fixtures/.
  2. Pipe a Stop-hook-shaped JSON payload into ~/.claude/hooks/response_summary.py.
  3. Wait for the detached TTS subprocess to write its debug log.
  4. Assert the right TTS script ran, with the right voice, and exited 0.

Skipped cleanly if no API keys are available.
"""
import json
import os
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK_PATH = Path.home() / ".claude" / "hooks" / "response_summary.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

OPUS_ID = "Gfpl8Yo74Is0W6cPUWWT"
SONNET_ID = "EXAVITQu4vr4xnSDxMaL"

# (model_id, expected_tts_log, expected_voice_marker_in_log)
CASES = [
    ("claude-opus-4-6", "/tmp/elevenlabs_tts_debug.log", f"voice_id={OPUS_ID}"),
    ("claude-sonnet-4-6", "/tmp/elevenlabs_tts_debug.log", f"voice_id={SONNET_ID}"),
    ("claude-haiku-4-5-20251001", "/tmp/openai_tts_debug.log", "voice=sage"),
]


def _have_summarizer_key():
    """Summarizer needs at least one of these to produce a real summary."""
    # Load ~/.env so the test sees the same env the hook does.
    env_file = Path.home() / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if "=" not in line or line.startswith("#"):
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v.strip("\"'"))
    return any(os.environ.get(k) for k in (
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GROQ_API_KEY",
    ))


def _have_tts_key():
    return bool(os.environ.get("ELEVENLABS_API_KEY") or os.environ.get("OPENAI_API_KEY"))


pytestmark = pytest.mark.skipif(
    not (HOOK_PATH.exists() and _have_summarizer_key() and _have_tts_key()),
    reason="No API keys / hook symlink missing — skipping E2E.",
)


def _build_fixture(model: str) -> Path:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    safe_name = model.replace("/", "_").replace(".", "_")
    path = FIXTURES / f"transcript_{safe_name}.jsonl"
    entries = [
        {"type": "user", "message": {"role": "user", "content": "Summarize the previous work."}},
        {"type": "assistant", "message": {
            "role": "assistant",
            "model": model,
            "content": [{
                "type": "text",
                "text": (
                    "I added a regression test suite covering the TTS fallback chain, "
                    "the voice selector, and hook environment propagation. All tests pass."
                ),
            }],
        }},
    ]
    with open(path, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")
    return path


def _clear_logs():
    for log in (
        "/tmp/elevenlabs_tts_debug.log",
        "/tmp/openai_tts_debug.log",
        "/tmp/edge_tts_debug.log",
        "/tmp/response_summary_debug.log",
    ):
        try:
            Path(log).unlink()
        except FileNotFoundError:
            pass


def _wait_for_log(log_path: str, marker: str, timeout: float = 30.0) -> str:
    """Poll the log until it appears and contains the expected marker."""
    deadline = time.time() + timeout
    log = Path(log_path)
    while time.time() < deadline:
        if log.exists():
            text = log.read_text()
            if marker in text:
                return text
        time.sleep(0.25)
    return log.read_text() if log.exists() else ""


@pytest.mark.parametrize("model,expected_log,voice_marker", CASES)
def test_e2e_hook_runs_correct_tts_with_correct_voice(model, expected_log, voice_marker, tmp_path):
    import subprocess as sp

    transcript = _build_fixture(model)
    _clear_logs()

    payload = json.dumps({
        "session_id": "e2e-test",
        "transcript_path": str(transcript),
        "cwd": str(REPO_ROOT),
    })

    env = os.environ.copy()
    env["CLAUDE_RESPONSE_SUMMARY_ENABLED"] = "true"
    env["RESPONSE_SUMMARY_DEBUG"] = "true"

    result = sp.run(
        ["python3", str(HOOK_PATH)],
        input=payload,
        env=env,
        capture_output=True,
        text=True,
        timeout=45,
    )

    assert result.returncode == 0, (
        f"Hook itself exited non-zero. stdout={result.stdout!r} stderr={result.stderr!r}"
    )

    # The TTS subprocess is detached, so wait for its debug log.
    log_text = _wait_for_log(expected_log, voice_marker, timeout=30.0)
    assert voice_marker in log_text, (
        f"Expected {voice_marker!r} in {expected_log}, got:\n{log_text[-2000:]}"
    )

    # The hook spawned the TTS in a new session — it might still be running.
    # Tail the response_summary debug log to confirm the right script was picked.
    rs_log = Path("/tmp/response_summary_debug.log")
    if rs_log.exists():
        rs_text = rs_log.read_text()
        expected_script = "elevenlabs_tts.py" if "elevenlabs" in expected_log else "openai_tts.py"
        assert expected_script in rs_text, (
            f"Expected {expected_script} mention in response_summary debug log:\n{rs_text[-1000:]}"
        )
