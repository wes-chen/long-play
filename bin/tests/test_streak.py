#!/usr/bin/env python3
"""Regression tests for streak.py celebration logic (issue #22).

Pinning the documented contract — "Celebrations fire ONLY for new records
(>= 3 weeks) or milestones (4/8/12/16/20/24)":
- a first-ever 3-week streak celebrates as a new record;
- a 4-week first record fires as a milestone;
- tying an old best (at 3 or above) stays silent.

Run: python3 bin/tests/test_streak.py  (stdlib only)
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import streak


def run_check(weeks_map, state):
    saved = {}
    streak.week_reactions = lambda: weeks_map
    streak.load_state = lambda: dict(state)
    streak.save_state = lambda s: saved.update(s)

    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        streak.check()
    finally:
        sys.stdout = old
    return json.loads(buf.getvalue()), saved


FULL = ["played", "loved", "played", "played", "loved"]

FRESH = {"streak": 0, "best": 0, "last_full_week": None,
         "enabled": True, "ignored": 0, "celebrated_week": None}


def test_first_3_week_record_celebrates():
    weeks = {1: FULL, 2: FULL, 3: FULL}
    out, saved = run_check(weeks, FRESH)
    assert out["celebrate"] is True, out
    assert "New record" in out["message"], out
    assert saved["celebrated_week"] == 3, saved
    assert saved["best"] == 3, saved


def test_first_4_week_record_fires_as_milestone():
    weeks = {1: FULL, 2: FULL, 3: FULL, 4: FULL}
    out, _ = run_check(weeks, FRESH)
    assert out["celebrate"] is True, out
    assert "Streak ritual" in out["message"], out


def test_tie_of_old_best_stays_silent():
    weeks = {1: FULL, 2: FULL, 3: FULL, 4: FULL, 5: FULL,
             10: FULL, 11: FULL, 12: FULL}
    state = dict(FRESH, streak=5, best=5, last_full_week=5, celebrated_week=5)
    out, _ = run_check(weeks, state)
    assert out["celebrate"] is False, out


def test_tie_at_3_stays_silent():
    weeks = {1: FULL, 2: FULL, 3: FULL, 9: FULL, 10: FULL, 11: FULL}
    state = dict(FRESH, streak=3, best=3, last_full_week=3, celebrated_week=3)
    out, _ = run_check(weeks, state)
    assert out["celebrate"] is False, out


if __name__ == "__main__":
    for t in (test_first_3_week_record_celebrates,
              test_first_4_week_record_fires_as_milestone,
              test_tie_of_old_best_stays_silent,
              test_tie_at_3_stays_silent):
        t()
        print("ok", t.__name__)
    print("streak regression tests: 4/4 passed")
