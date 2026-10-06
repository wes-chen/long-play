#!/usr/bin/env python3
"""Regression tests for M9 context-aware drip ordering (issue #19).

The drip re-ranks the week's 4-album spotlight order by the listener's
recent context tags (trailing 7 days): a "focused" streak surfaces the
most demanding album first; a "commute"/"background"/"late-night" streak
surfaces the least demanding first. Demand = album minutes (tracklist
cache) * genre demand factor.

Contract:
- streak needs >= 3 tags in the trailing 7 days with one context holding
  >= 60% share; otherwise file order is kept.
- stale (> 7d) tags are ignored; a missing/unreadable tag log fails
  closed to file order.
- the week's album SET never changes — only the day mapping.
- the applied streak is recorded in the pick JSON as "context_fit".

Run: python3 bin/tests/test_drip_context.py  (stdlib only)
"""
import datetime
import io
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import drip_pick

# week 1: skip index (1-1)%5 = 0, so drip order is file indices 1..4.
WEEK_MD = """# Week 1

## Anchor — Radiohead — *OK Computer* (1997)
**Listen for:** the famous cue text.

## Adventurous — The Beatles — *Abbey Road* (1969)
**Listen for:** another famous cue.

## Adventurous — Kendrick Lamar — *To Pimp a Butterfly* (2015)
**Listen for:** a third famous cue.

## Adventurous — SZA — *SOS* (2022)
**Listen for:** a fourth famous cue.

## Wild card — Swans — *To Be Kind* (2014)
**Listen for:** a fifth famous cue.
"""

ALBUMS = [
    # (artist, album, genre, minutes)
    ("The Beatles", "Abbey Road", "rock-classic", 47),
    ("Kendrick Lamar", "To Pimp a Butterfly", "hip-hop", 78),
    ("SZA", "SOS", "confessional-rnb", 68),
    ("Swans", "To Be Kind", "noise-rock", 121),
]
# expected demand: abbey 47.0, tpab 78.0, sos 54.4, tbk 181.5
TUE = datetime.date(2026, 10, 6)   # Tuesday


def slug(artist, album):
    return "%s--%s" % (drip_pick._norm(artist), drip_pick._norm(album))


def make_repo(tmp, tags):
    weeks = os.path.join(tmp, "weeks")
    os.makedirs(weeks)
    with open(os.path.join(weeks, "week-01.md"), "w") as f:
        f.write(WEEK_MD)
    delivered = os.path.join(tmp, "digest-delivered.json")
    with open(delivered, "w") as f:
        json.dump([1], f)
    sent = os.path.join(tmp, "drip-sent.json")
    with open(sent, "w") as f:
        json.dump({}, f)
    predictions = os.path.join(tmp, "predictions.json")
    with open(predictions, "w") as f:
        json.dump({"weeks": {"1": {"blind": False}}}, f)
    # tracklist caches with real durations
    tracklists = os.path.join(tmp, "engine", "tracklists")
    os.makedirs(tracklists)
    tagmap = {}
    for artist, album, genre, minutes in ALBUMS:
        tracks = [{"n": 1, "title": "t", "duration_ms": int(minutes * 60000)}]
        with open(os.path.join(tracklists, slug(artist, album) + ".json"),
                  "w") as f:
            json.dump({"artist": artist, "album": album, "tracks": tracks},
                      f)
        key = "%s|%s" % (drip_pick._tag_norm(artist),
                         drip_pick._tag_norm(album))
        tagmap[key] = {"genre": genre}
    album_tags = os.path.join(tmp, "engine", "album_tags.json")
    with open(album_tags, "w") as f:
        json.dump(tagmap, f)
    tagfile = os.path.join(tmp, "context-tags.jsonl")
    if tags is not None:
        with open(tagfile, "w") as f:
            for ctx, days_ago in tags:
                ts = (datetime.datetime.now(datetime.timezone.utc)
                      - datetime.timedelta(days=days_ago)).isoformat()
                f.write(json.dumps({"ts": ts, "week": 1, "artist": "x",
                                    "album": "y", "genre": "z",
                                    "context": ctx,
                                    "reaction": "played"}) + "\n")
    drip_pick.REPO = tmp
    drip_pick.DELIVERED = delivered
    drip_pick.DRIP_SENT = sent
    drip_pick.PREDICTIONS = predictions
    drip_pick.CONTEXT_TAGS = tagfile
    drip_pick.TRACKLISTS = tracklists
    drip_pick.ALBUM_TAGS_PATH = album_tags


def run_pick():
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        assert drip_pick.main(today=TUE) == 0
    finally:
        sys.stdout = old
    return json.loads(buf.getvalue())


def test_focused_streak_surfaces_demanding_first():
    make_repo(tempfile.mkdtemp(),
              [("focused", 1), ("focused", 2), ("focused", 3),
               ("commute", 1)])
    pick = run_pick()
    assert pick["album"] == "To Be Kind", pick          # 181.5 demand
    assert pick["context_fit"]["streak"] == "focused", pick
    assert pick["context_fit"]["reordered"] is True, pick
    assert pick["context_fit"]["tags"] == 4, pick


def test_commute_streak_surfaces_shortest_first():
    make_repo(tempfile.mkdtemp(),
              [("commute", 1), ("commute", 2), ("commute", 3)])
    pick = run_pick()
    assert pick["album"] == "Abbey Road", pick          # 47.0 demand
    assert pick["context_fit"]["streak"] == "commute", pick
    assert pick["context_fit"]["reordered"] is True, pick


def test_mixed_tags_keep_file_order():
    make_repo(tempfile.mkdtemp(),
              [("focused", 1), ("commute", 1), ("background", 2),
               ("late-night", 3)])
    pick = run_pick()
    assert pick["album"] == "Abbey Road", pick  # file order: index 1 first
    assert pick["context_fit"]["streak"] is None, pick
    assert pick["context_fit"]["reordered"] is False, pick


def test_too_few_tags_keep_file_order():
    make_repo(tempfile.mkdtemp(), [("focused", 1), ("focused", 2)])
    pick = run_pick()
    assert pick["album"] == "Abbey Road", pick
    assert pick["context_fit"]["streak"] is None, pick
    assert pick["context_fit"]["tags"] == 2, pick


def test_stale_tags_ignored():
    make_repo(tempfile.mkdtemp(),
              [("focused", 8), ("focused", 9), ("focused", 10)])
    pick = run_pick()
    assert pick["album"] == "Abbey Road", pick
    assert pick["context_fit"]["streak"] is None, pick
    assert pick["context_fit"]["tags"] == 0, pick


def test_missing_tag_log_fails_closed():
    make_repo(tempfile.mkdtemp(), None)
    drip_pick.CONTEXT_TAGS = os.path.join(tempfile.mkdtemp(), "nope.jsonl")
    pick = run_pick()
    assert pick["album"] == "Abbey Road", pick
    assert pick["context_fit"] == {"streak": None, "tags": 0,
                                   "reordered": False}, pick


def test_week_set_unchanged_across_days():
    # all four spotlight albums are the same set, just re-mapped days
    make_repo(tempfile.mkdtemp(),
              [("focused", 1), ("focused", 2), ("focused", 3)])
    seen = set()
    for wd in (1, 2, 3, 4):  # Tue..Fri
        day = datetime.date(2026, 10, 5 + wd)
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            assert drip_pick.main(today=day) == 0
        finally:
            sys.stdout = old
        seen.add(json.loads(buf.getvalue())["album"])
    assert seen == {"Abbey Road", "To Pimp a Butterfly", "SOS",
                    "To Be Kind"}, seen


if __name__ == "__main__":
    tests = (test_focused_streak_surfaces_demanding_first,
             test_commute_streak_surfaces_shortest_first,
             test_mixed_tags_keep_file_order,
             test_too_few_tags_keep_file_order,
             test_stale_tags_ignored,
             test_missing_tag_log_fails_closed,
             test_week_set_unchanged_across_days)
    for t in tests:
        t()
        print("ok", t.__name__)
    print(f"drip context regression tests: {len(tests)}/{len(tests)} passed")
