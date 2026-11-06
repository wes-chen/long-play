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

_REAL_FIND_ALBUM = build_watchlist.find_album

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


def check_artist_match_is_word_boundary_not_substring():
    """A substring-only artist must not win the album resolve.

    Regression test for the album_tracks.py incident class: "Ride"
    substring-matches "Jaded Juice Riders", so a stranger's album would
    be cached under the requested artist's watchlist entry and poison
    watch-hit attribution. The token-exact match skips it and picks
    the real artist's edition; a hyphenated lookalike ("Fly-By Ride")
    is rejected too, since a hyphen is a word boundary but not an
    artist boundary. With only lookalike artists present, or with the
    right artist but a different album title, the resolve fails loudly
    instead of misattributing — the old title fallback returned the
    first same-artist record regardless of title.
    """
    payload = {"sections": [{"items": [
        {"title": "Nowhere", "subtitle": "Jaded Juice Riders",
         "spotify_uri": "spotify:album:wrong000000000000000001"},
        {"title": "Nowhere", "subtitle": "Fly-By Ride",
         "spotify_uri": "spotify:album:wrong000000000000000002"},
        {"title": "Nowhere", "subtitle": "Ride, Someone Else",
         "spotify_uri": "spotify:album:ride000000000000000001"},
    ]}]}
    # This check exercises the search matcher, so run it with pins
    # disabled: the real pinned_albums.json pins Nowhere to its verified
    # URI, which would shadow the mocked search payloads below.
    tmp = tempfile.mkdtemp(prefix="build-watchlist-pins-")
    empty_pins = os.path.join(tmp, "pinned_albums.json")
    with open(empty_pins, "w") as f:
        json.dump({"pins": []}, f)
    real_pinned = build_watchlist.PINNED_FILE
    build_watchlist.PINNED_FILE = empty_pins
    build_watchlist.sh = lambda *a: payload
    build_watchlist.find_album = _REAL_FIND_ALBUM
    uri, title, saved = build_watchlist.find_album("Nowhere", "Ride")
    assert uri == "spotify:album:ride000000000000000001", uri
    assert title == "Nowhere", title
    payload_only_substring = {"sections": [{"items": [
        {"title": "Nowhere", "subtitle": "Jaded Juice Riders",
         "spotify_uri": "spotify:album:wrong000000000000000001"},
    ]}]}
    build_watchlist.sh = lambda *a: payload_only_substring
    assert build_watchlist.find_album("Nowhere", "Ride") == (None, None, False)
    payload_wrong_title = {"sections": [{"items": [
        {"title": "Other Album", "subtitle": "Ride",
         "spotify_uri": "spotify:album:ride000000000000000002"},
    ]}]}
    build_watchlist.sh = lambda *a: payload_wrong_title
    assert build_watchlist.find_album("Nowhere", "Ride") == (None, None, False)
    build_watchlist.PINNED_FILE = real_pinned
    print("ok - check_artist_match_is_word_boundary_not_substring")


def check_search_is_artist_scoped_with_bare_title_query():
    """The search call must pass --artist and a bare-title query.

    The old "{album} by {artist}" query text misdirects the backend:
    for Loveless it returns the band's other records and never the
    album itself, while the bare title plus --artist returns it first.
    """
    seen = {}

    def _capture(*args):
        seen["argv"] = args
        return {"sections": [{"items": [
            {"title": "Loveless", "subtitle": "my bloody valentine",
             "spotify_uri": "spotify:album:loveless000000000000001"},
        ]}]}

    build_watchlist.sh = _capture
    build_watchlist.find_album = _REAL_FIND_ALBUM
    uri, title, saved = build_watchlist.find_album(
        "Loveless", "My Bloody Valentine")
    assert uri == "spotify:album:loveless000000000000001", uri
    argv = seen["argv"]
    assert argv[0:2] == ("spotify-api", "search"), argv
    assert "--artist" in argv, argv
    assert argv[argv.index("--artist") + 1] == "My Bloody Valentine", argv
    assert argv[argv.index("--query") + 1] == "Loveless", argv
    assert " by " not in argv[argv.index("--query") + 1], argv
    print("ok - check_search_is_artist_scoped_with_bare_title_query")


def check_pinned_album_resolves_without_search():
    """A pinned album resolves from pinned_albums.json without any search.

    Regression case: Ride's Nowhere — no album or artist-scoped query
    surfaces it, so without the pin it fails loudly every rollover and
    the sampler stays blind to it for the whole week.
    """
    tmp = tempfile.mkdtemp(prefix="build-watchlist-pins-")
    pins_path = os.path.join(tmp, "pinned_albums.json")
    with open(pins_path, "w") as f:
        json.dump({"pins": [{
            "album": "NOWHERE", "artist": "Ride",
            "spotify_uri": "spotify:album:nowhere000000000000001",
        }]}, f)
    real_pinned = build_watchlist.PINNED_FILE
    build_watchlist.PINNED_FILE = pins_path
    build_watchlist.find_album = _REAL_FIND_ALBUM

    def _must_not_search(*args):
        raise AssertionError("pinned resolve must not call search")

    build_watchlist.sh = _must_not_search
    try:
        uri, title, saved = build_watchlist.find_album("Nowhere", "Ride")
        assert uri == "spotify:album:nowhere000000000000001", uri
        assert title == "Nowhere", title
        assert saved is False, saved
        # A non-pinned album still goes through search.
        build_watchlist.sh = lambda *a: {"sections": [{"items": [
            {"title": "Souvlaki", "subtitle": "Slowdive",
             "spotify_uri": "spotify:album:souvlaki00000000000001"},
        ]}]}
        uri, _, _ = build_watchlist.find_album("Souvlaki", "Slowdive")
        assert uri == "spotify:album:souvlaki00000000000001", uri
    finally:
        build_watchlist.PINNED_FILE = real_pinned
    print("ok - check_pinned_album_resolves_without_search")


def check_pin_key_is_normalized():
    """Pin lookup is title- and case-insensitive, like the matcher."""
    tmp = tempfile.mkdtemp(prefix="build-watchlist-pins-")
    pins_path = os.path.join(tmp, "pinned_albums.json")
    with open(pins_path, "w") as f:
        json.dump({"pins": [{
            "album": "Nowhere (Expanded)", "artist": "  RIDE ",
            "spotify_uri": "spotify:album:nowhere000000000000001",
        }]}, f)
    real_pinned = build_watchlist.PINNED_FILE
    build_watchlist.PINNED_FILE = pins_path
    build_watchlist.find_album = _REAL_FIND_ALBUM
    build_watchlist.sh = lambda *a: (_ for _ in ()).throw(
        AssertionError("pinned resolve must not call search"))
    try:
        uri, _, _ = build_watchlist.find_album("Nowhere", "Ride")
        assert uri == "spotify:album:nowhere000000000000001", uri
    finally:
        build_watchlist.PINNED_FILE = real_pinned
    print("ok - check_pin_key_is_normalized")


def main():
    for check in (check_total_failure_leaves_old_watchlist,
                  check_success_replaces_with_new_week_only,
                  check_partial_build_covers_resolved_only,
                  check_artist_match_is_word_boundary_not_substring,
                  check_search_is_artist_scoped_with_bare_title_query,
                  check_pinned_album_resolves_without_search,
                  check_pin_key_is_normalized):
        check()
    return 0


if __name__ == "__main__":
    sys.exit(main())
