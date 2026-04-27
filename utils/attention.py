"""Detect if user is actively watching this tmux pane on macOS.

Used to skip TTS audio when the user can already see the terminal.
"""

import os
import platform
import subprocess


def user_is_watching() -> bool:
    """Return True if this tmux pane is the focused one in a frontmost terminal.

    Returns False on non-macOS, on errors, or if outside tmux.
    """
    if platform.system() != 'Darwin':
        return False
    try:
        # 1. Terminal must be the frontmost app (fast: lsappinfo ~70ms)
        front_asn = subprocess.run(
            ['lsappinfo', 'front'],
            capture_output=True, text=True, timeout=1
        ).stdout.strip()
        name_out = subprocess.run(
            ['lsappinfo', 'info', '-only', 'name', front_asn],
            capture_output=True, text=True, timeout=1
        ).stdout
        is_ghostty = 'Ghostty' in name_out
        if 'iTerm2' not in name_out and 'Terminal' not in name_out and not is_ghostty:
            return False

        tmux_pane = os.environ.get('TMUX_PANE', '')
        if not tmux_pane:
            return False

        # 2. This pane must be the active pane in the active window of its session
        flags = subprocess.run(
            ['tmux', 'display', '-p', '-t', tmux_pane,
             '#{window_active}#{pane_active}'],
            capture_output=True, text=True, timeout=1
        ).stdout.strip()
        if flags != '11':
            return False

        # Ghostty has no AppleScript tab-tty introspection, so skip step 3.
        # Trade-off: if multiple Ghostty tabs each run their own tmux session,
        # all panes claim "watching" when any Ghostty window is frontmost.
        if is_ghostty:
            return True

        # 3. The iTerm2 tab in front must be attached to THIS tmux session.
        # Each iTerm2 tab runs its own tmux client — we need the visible one.
        visible_tty = subprocess.run(
            ['osascript', '-e',
             'tell application "iTerm2" to tell current window to tell current tab to tell current session to get tty'],
            capture_output=True, text=True, timeout=2
        ).stdout.strip()
        if not visible_tty:
            return False

        session = subprocess.run(
            ['tmux', 'display', '-p', '-t', tmux_pane, '#{session_name}'],
            capture_output=True, text=True, timeout=1
        ).stdout.strip()
        clients = subprocess.run(
            ['tmux', 'list-clients', '-t', session, '-F', '#{client_tty}'],
            capture_output=True, text=True, timeout=1
        ).stdout.splitlines()
        return visible_tty in clients
    except Exception:
        return False
