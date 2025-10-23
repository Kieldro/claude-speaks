#!/bin/bash
# TTS Daemon control script

DAEMON_SCRIPT="$HOME/repos/claude-speaks/tts_daemon.py"
PID_FILE="$HOME/.claude/tts_daemon.pid"

case "$1" in
    start)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "TTS Daemon is already running (PID: $PID)"
                exit 1
            fi
        fi
        echo "Starting TTS Daemon..."
        python3 "$DAEMON_SCRIPT" &
        sleep 0.5
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            echo "TTS Daemon started (PID: $PID)"
        else
            echo "Failed to start TTS Daemon"
            exit 1
        fi
        ;;

    stop)
        if [ ! -f "$PID_FILE" ]; then
            echo "TTS Daemon is not running"
            exit 1
        fi
        PID=$(cat "$PID_FILE")
        echo "Stopping TTS Daemon (PID: $PID)..."
        kill "$PID" 2>/dev/null
        sleep 0.5
        if kill -0 "$PID" 2>/dev/null; then
            echo "Daemon did not stop, using SIGKILL..."
            kill -9 "$PID" 2>/dev/null
        fi
        rm -f "$PID_FILE"
        echo "TTS Daemon stopped"
        ;;

    restart)
        $0 stop
        sleep 1
        $0 start
        ;;

    status)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "TTS Daemon is running (PID: $PID)"
                exit 0
            else
                echo "TTS Daemon PID file exists but process is dead"
                exit 1
            fi
        else
            echo "TTS Daemon is not running"
            exit 1
        fi
        ;;

    *)
        echo "Usage: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
