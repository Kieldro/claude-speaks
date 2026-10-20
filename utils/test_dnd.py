#!/usr/bin/env python3
"""Tests for dnd.py"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

from dnd import APPLE_EPOCH, dnd_active

EVENINGS = {
    "class": "DNDModeConfigurationScheduleTrigger",
    "enabledSetting": 2,
    "timePeriodStartTimeHour": 17, "timePeriodStartTimeMinute": 0,
    "timePeriodEndTimeHour": 8, "timePeriodEndTimeMinute": 0,
    "timePeriodWeekdays": 127,
}


def _apple(dt: datetime) -> float:
    return dt.timestamp() - APPLE_EPOCH


def _db(assertions=None, invalidations=None, triggers=None) -> Path:
    db = Path(tempfile.mkdtemp())
    store = {}
    if assertions:
        store["storeAssertionRecords"] = assertions
    if invalidations:
        store["storeInvalidationRecords"] = invalidations
    (db / "Assertions.json").write_text(json.dumps({"data": [store]}))
    modes = {"com.apple.donotdisturb.mode.default": {"triggers": {"triggers": triggers or []}}}
    (db / "ModeConfigurations.json").write_text(json.dumps({"data": [{"modeConfigurations": modes}]}))
    return db


def test_off_with_no_assertion_outside_schedule():
    assert not dnd_active(_db(triggers=[EVENINGS]), datetime(2026, 10, 20, 14, 0))


def test_on_when_toggled_manually():
    record = {"assertionDetails": {"assertionDetailsModeIdentifier": "com.apple.donotdisturb.mode.default"}}
    assert dnd_active(_db(assertions=[record]), datetime(2026, 10, 20, 14, 0))


def test_on_inside_overnight_schedule_evening_and_morning():
    db = _db(triggers=[EVENINGS])
    assert dnd_active(db, datetime(2026, 10, 20, 17, 0))
    assert dnd_active(db, datetime(2026, 10, 21, 7, 59))
    assert not dnd_active(db, datetime(2026, 10, 21, 8, 0))


def test_disabled_schedule_is_ignored():
    assert not dnd_active(_db(triggers=[{**EVENINGS, "enabledSetting": 1}]), datetime(2026, 10, 20, 18, 0))


def test_turned_off_during_schedule_stays_off_until_next_window():
    off = {"invalidationDate": _apple(datetime(2026, 10, 20, 18, 30))}
    db = _db(invalidations=[off], triggers=[EVENINGS])
    assert not dnd_active(db, datetime(2026, 10, 20, 19, 0))
    assert not dnd_active(db, datetime(2026, 10, 21, 7, 0))
    assert dnd_active(db, datetime(2026, 10, 21, 17, 1))


def test_turned_off_before_window_does_not_cancel_it():
    off = {"invalidationDetails": {"invalidationDateTimestamp": _apple(datetime(2026, 10, 20, 11, 0))}}
    assert dnd_active(_db(invalidations=[off], triggers=[EVENINGS]), datetime(2026, 10, 20, 17, 30))


def test_weekday_mask_skips_unscheduled_days():
    weekdays_only = {**EVENINGS, "timePeriodWeekdays": 0b0111110}  # Mon..Fri, Sunday is bit 0
    db = _db(triggers=[weekdays_only])
    assert dnd_active(db, datetime(2026, 10, 23, 18, 0))  # Friday
    assert not dnd_active(db, datetime(2026, 10, 24, 18, 0))  # Saturday


def test_missing_files_mean_off():
    assert not dnd_active(Path(tempfile.mkdtemp()), datetime(2026, 10, 20, 18, 0))
