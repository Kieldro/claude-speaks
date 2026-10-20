#!/opt/homebrew/bin/python3
"""Exit 0 while macOS Do Not Disturb (or any Focus) is on, so hooks can stay quiet.

Usage: dnd.py || afplay sound.aiff
"""

import json
import sys
from datetime import datetime, time, timedelta
from pathlib import Path

DB = Path.home() / "Library" / "DoNotDisturb" / "DB"
APPLE_EPOCH = 978307200  # 2001-01-01 UTC, the reference date of Focus timestamps


def _store(db: Path, name: str) -> dict:
    try:
        return json.loads((db / name).read_text())["data"][0]
    except (OSError, ValueError, KeyError, IndexError):
        return {}


def _timestamps(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, (int, float)) and ("Date" in key or "Timestamp" in key):
                yield value
            else:
                yield from _timestamps(value)
    elif isinstance(node, list):
        for item in node:
            yield from _timestamps(item)


def _window_start(trigger: dict, now: datetime):
    """Start of the schedule window that contains now, or None."""
    if trigger.get("class") != "DNDModeConfigurationScheduleTrigger" or trigger.get("enabledSetting") != 2:
        return None
    start = time(trigger.get("timePeriodStartTimeHour", 0), trigger.get("timePeriodStartTimeMinute", 0))
    end = time(trigger.get("timePeriodEndTimeHour", 0), trigger.get("timePeriodEndTimeMinute", 0))
    clock = now.time()
    if start <= end:
        day = now.date() if start <= clock < end else None
    elif clock >= start:
        day = now.date()
    elif clock < end:
        day = now.date() - timedelta(days=1)
    else:
        day = None
    # Weekday bits run Sunday (bit 0) to Saturday (bit 6), keyed on the day the window opened.
    if day is None or not trigger.get("timePeriodWeekdays", 127) >> (day.isoweekday() % 7) & 1:
        return None
    return datetime.combine(day, start)


def dnd_active(db: Path = DB, now: datetime = None) -> bool:
    now = now or datetime.now()
    assertions = _store(db, "Assertions.json")
    if assertions.get("storeAssertionRecords"):
        return True
    # A schedule writes no assertion, and turning it off early leaves only an invalidation record.
    last_off = max(_timestamps(assertions.get("storeInvalidationRecords", [])), default=0) + APPLE_EPOCH
    modes = _store(db, "ModeConfigurations.json").get("modeConfigurations", {})
    for mode in modes.values():
        for trigger in mode.get("triggers", {}).get("triggers", []):
            start = _window_start(trigger, now)
            if start and start.timestamp() > last_off:
                return True
    return False


if __name__ == "__main__":
    sys.exit(0 if dnd_active() else 1)
