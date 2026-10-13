#!/usr/bin/env python3
"""Regression tests: build_watchlist.py must fail closed on total failure.

A transient resolver failure once resolved 0/5 albums during a week
rollover. The old code had already cleared the previous week's entries
before resolving, so the on-disk watchlist was left empty — the sampler
ran the whole week with zero watch-hit attribution — and the build still
exited 0, so the rollover advanced anyway.

Rule under test:
- a build that resolves zero albums exits nonzero and leaves the
  existing watchlist file byte-identical;
- a successful build replaces the file with only the new week's entries
  (stale weeks still cleared, ADV-LP-04);
- a partial build succeeds, covering only the albums it resolved.

Run: python3 bin/tests/test_build_watchlist.py  (stdlib only)
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "sampler"))

import build_watchlist

FAKE_WEEKS = {
    99: [
        ("First Album", "First Artist", "anchor"),
        ("Second Album", "Second Artist", "wild card"),
    ],
}

OLD_WATCHLIST = {
    "tracks": {
        "spotify:track:old000000000000000000001": {
            "album": "Old Album", "artist": "Old Artist", "week": 98,
            "slot": "anchor", "album_uri": "spotify:album:old000000000000000001",
            "track": "Old Track",
        },
    },
    "albums": {
        "spotify:album:old000000000000000001": {
            "album": "Old Album", "artist": "Old Artist", "week": 98,
            "slot": "anchor", "track_count": 1, "edition_from_library": False,
        },
    },
    "week": 98,
}


def _stage():
    tmp = tempfile.mkdtemp(prefix="build-watchlist-")
    path = os.path.join(tmp, "watchlist.json")
    with open(path, "w") as f:
        json.dump(OLD_WATCHLIST, f)
    return tmp, path


def _run(week, path, find_album, album_tracks):
    build_watchlist.WATCHLIST = path
    build_watchlist.load_weeks = lambda: FAKE_WEEKS
    build_watchlist.find_album = find_album
    build_watchlist.album_tracks = album_tracks
    old = sys.argv
    sys.argv = ["build_watchlist.py", str(week)]
    try:
        return build_watchlist.main()
    finally:
        sys.argv = old


def _resolve_all(album, artist):
    uri = "spotify:album:" + ("aaa" if "First" in album else "bbb")
    return uri, album, False


def _tracks(uri):
    return [("spotify:track:" + uri[-3:] + "00000000000000000001",
             "Track One")]


def check_total_failure_leaves_old_watchlist():
    _, path = _stage()
    before = open(path).read()
    rc = _run(99, path, lambda a, b: (None, None, False), _tracks)
    assert rc != 0, rc
    assert open(path).read() == before, "failed build rewrote the watchlist"
    print("ok - check_total_failure_leaves_old_watchlist")


def check_success_replaces_with_new_week_only():
    _, path = _stage()
    rc = _run(99, path, _resolve_all, _tracks)
    assert rc == 0, rc
    wl = json.load(open(path))
    assert wl["week"] == 99, wl.get("week")
    assert len(wl["albums"]) == 2, wl["albums"]
    assert all(e["week"] == 99 for e in wl["albums"].values())
    assert all(e["week"] == 99 for e in wl["tracks"].values())
    assert "spotify:track:old000000000000000000001" not in wl["tracks"]
    print("ok - check_success_replaces_with_new_week_only")


def check_partial_build_covers_resolved_only():
    _, path = _stage()

    def _partial(album, artist):
        if "First" in album:
            return "spotify:album:aaa", album, False
        return None, None, False

    rc = _run(99, path, _partial, _tracks)
    assert rc == 0, rc
    wl = json.load(open(path))
    assert wl["week"] == 99
    assert list(wl["albums"]) == ["spotify:album:aaa"], wl["albums"]
    assert all(e["album"] == "First Album" for e in wl["tracks"].values())
    print("ok - check_partial_build_covers_resolved_only")


def main():
    for check in (check_total_failure_leaves_old_watchlist,
                  check_success_replaces_with_new_week_only,
                  check_partial_build_covers_resolved_only):
        check()
    return 0


if __name__ == "__main__":
    sys.exit(main())
