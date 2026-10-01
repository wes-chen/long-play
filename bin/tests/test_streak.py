#!/usr/bin/env python3
"""Regression tests for streak.py.

Issue #22 contract — "Celebrations fire ONLY for new records (>= 3 weeks)
or milestones (4/8/12/16/20/24)":
- a first-ever 3-week streak celebrates as a new record;
- a 4-week first record fires as a milestone;
- tying an old best (at 3 or above) stays silent.

Issue #27 — full-listen counts distinct albums, not log rows. week_reactions
entries are (album_key, reaction) tuples:
- five rows covering only four distinct albums is NOT a full-listen week;
- a second-chance re-listen row merged into its album does not inflate the
  distinct-album count (and cannot substitute for an unreacted album);
- at least 3 of the DISTINCT albums must be played/loved.

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


def rows(*reactions):
    """Five distinct albums A1..A5 with the given reactions."""
    return [(f"a{i}|artist{i}", r) for i, r in enumerate(reactions, 1)]


FULL = rows("played", "loved", "played", "played", "loved")

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


# --- issue #27: distinct albums, not rows ---

def test_five_rows_four_albums_not_full():
    dup = rows("played", "loved", "played", "played") \
        + [("a1|artist1", "loved")]  # duplicate of A1
    assert streak.is_full_listen(dup) is False


def test_second_chance_row_cannot_complete_week():
    # 4 digest albums reacted + a second-chance re-listen of A1: still 4 albums
    re_listen = rows("played", "played", "played", "skipped") \
        + [("a1|artist1", "loved")]
    assert streak.is_full_listen(re_listen) is False


def test_only_two_played_loved_not_full():
    thin = rows("played", "played", "skipped", "skipped", "bounced off")
    assert streak.is_full_listen(thin) is False


def test_exactly_five_distinct_three_played_full():
    assert streak.is_full_listen(FULL) is True


def test_bounce_then_loved_counts_as_loved_once():
    entries = rows("played", "played", "played", "skipped", "skipped")[:-1] \
        + [("a5|artist5", "bounced off"), ("a5|artist5", "loved")]
    n, pl = streak.album_stats(entries)
    assert (n, pl) == (5, 4)
    assert streak.is_full_listen(entries) is True


def test_seven_rows_five_albums_still_counts_distinct():
    entries = FULL + [("a2|artist2", "played"), ("a3|artist3", "skipped")]
    n, pl = streak.album_stats(entries)
    assert (n, pl) == (5, 5)  # a3's played row already made it played/loved
    assert streak.is_full_listen(entries) is True


if __name__ == "__main__":
    tests = (test_first_3_week_record_celebrates,
             test_first_4_week_record_fires_as_milestone,
             test_tie_of_old_best_stays_silent,
             test_tie_at_3_stays_silent,
             test_five_rows_four_albums_not_full,
             test_second_chance_row_cannot_complete_week,
             test_only_two_played_loved_not_full,
             test_exactly_five_distinct_three_played_full,
             test_bounce_then_loved_counts_as_loved_once,
             test_seven_rows_five_albums_still_counts_distinct)
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"streak regression tests: {len(tests)}/{len(tests)} passed")
