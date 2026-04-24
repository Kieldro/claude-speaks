"""Detect if user is actively watching this tmux pane.

Used to skip TTS audio when the user can already see the terminal.
Supports macOS (iTerm2/Terminal.app) and Linux (Gnome Terminal on X11).
"""

import os
import platform
import subprocess


def _tmux_pane_is_active(tmux_pane: str) -> bool:
    """Check this pane is the active pane in the active window."""
    flags = subprocess.run(
        ['tmux', 'display', '-p', '-t', tmux_pane,
         '#{window_active}#{pane_active}'],
        capture_output=True, text=True, timeout=1
    ).stdout.strip()
    return flags == '11'


def _tmux_session_name(tmux_pane: str) -> str:
    return subprocess.run(
        ['tmux', 'display', '-p', '-t', tmux_pane, '#{session_name}'],
        capture_output=True, text=True, timeout=1
    ).stdout.strip()


def _watching_linux(tmux_pane: str) -> bool:
    """X11/Gnome Terminal: check focused window is a terminal showing this session."""
    # Get active window ID
    win_id = subprocess.run(
        ['xdotool', 'getactivewindow'],
        capture_output=True, text=True, timeout=1
    ).stdout.strip()
    if not win_id:
        return False

    # Check it's a terminal
    wm_class = subprocess.run(
        ['xprop', '-id', win_id, 'WM_CLASS'],
        capture_output=True, text=True, timeout=1
    ).stdout.lower()
    terminal_classes = ('gnome-terminal', 'terminal', 'tilix', 'alacritty', 'kitty', 'konsole')
    if not any(t in wm_class for t in terminal_classes):
        return False

    # Check this tmux pane is the active one
    if not _tmux_pane_is_active(tmux_pane):
        return False

    # Check window title matches this tmux session (Gnome Terminal sets title to session name)
    win_name = subprocess.run(
        ['xdotool', 'getactivewindow', 'getwindowname'],
        capture_output=True, text=True, timeout=1
    ).stdout.strip()
    session = _tmux_session_name(tmux_pane)
    return session in win_name


def _watching_macos(tmux_pane: str) -> bool:
    """macOS: check frontmost app is a terminal with this tmux session visible."""
    front_asn = subprocess.run(
        ['lsappinfo', 'front'],
        capture_output=True, text=True, timeout=1
    ).stdout.strip()
    name_out = subprocess.run(
        ['lsappinfo', 'info', '-only', 'name', front_asn],
        capture_output=True, text=True, timeout=1
    ).stdout
    if 'iTerm2' not in name_out and 'Terminal' not in name_out:
        return False

    if not _tmux_pane_is_active(tmux_pane):
        return False

    visible_tty = subprocess.run(
        ['osascript', '-e',
         'tell application "iTerm2" to tell current window to tell current tab to tell current session to get tty'],
        capture_output=True, text=True, timeout=2
    ).stdout.strip()
    if not visible_tty:
        return False

    session = _tmux_session_name(tmux_pane)
    clients = subprocess.run(
        ['tmux', 'list-clients', '-t', session, '-F', '#{client_tty}'],
        capture_output=True, text=True, timeout=1
    ).stdout.splitlines()
    return visible_tty in clients


def user_is_watching() -> bool:
    """Return True if this tmux pane is the focused one in a frontmost terminal."""
    try:
        tmux_pane = os.environ.get('TMUX_PANE', '')
        if not tmux_pane:
            return False

        system = platform.system()
        if system == 'Darwin':
            return _watching_macos(tmux_pane)
        elif system == 'Linux':
            return _watching_linux(tmux_pane)
        return False
    except Exception:
        return False
