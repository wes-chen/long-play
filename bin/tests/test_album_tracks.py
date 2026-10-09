#!/usr/bin/env python3
"""Regression tests: bin/album_tracks.py must verify album identity.

On 2026-10-05 the resolver cached Section.80's tracklist under the
To Pimp A Butterfly slug: resolve() picked the first search result whose
subtitle contained the artist, falling back to items[0], and never checked
the album title. A mislabeled cache poisons guided cues, duration profiles,
and watchlist mapping downstream.

Rule under test:
- resolve() only accepts a result whose artist AND album title match;
  a same-artist different-album result is refused, never cached;
- the fetched experience's album title is re-verified before the cache
  is written; mismatch fails loudly instead of caching;
- a cache hit never touches the network.

Run: python3 bin/tests/test_album_tracks.py  (stdlib only)
"""
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import album_tracks


def _item(title, subtitle, uri):
    return {"title": title, "subtitle": subtitle, "spotify_uri": uri,
            "spotify_url": "https://open.spotify.com/album/x",
            "is_explicit": False}


def _search(*items):
    return json.dumps({"ok": True, "sections": [{"items": list(items)}]})


def _exp(title, track="Track One"):
    return {"ok": True, "title": title,
            "sections": [{"items": [{"title": track, "duration_ms": 180000,
                                     "spotify_uri": "spotify:track:1",
                                     "spotify_url": "u1"}]}]}


class _R:
    def __init__(self, stdout="", returncode=0, stderr=""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def _mock(search_json, exp):
    def fake(*args):
        if "search" in args:
            return _R(stdout=search_json)
        if "experience" in args:
            return _R(stdout=json.dumps(exp))
        raise AssertionError("unexpected command: %r" % (args,))
    return fake


def _patch_sh(fn):
    real = album_tracks.sh
    album_tracks.sh = fn
    return real


def check_picks_title_match_not_first_artist_match():
    # The Oct-5 incident: Section.80 ranks first for the TPAB query.
    # The resolver must skip it and take the title-matching result.
    items = _search(
        _item("Section.80", "Kendrick Lamar", "spotify:album:section80"),
        _item("To Pimp A Butterfly", "Kendrick Lamar", "spotify:album:tpab"),
    )
    real = _patch_sh(_mock(items, _exp("To Pimp A Butterfly")))
    try:
        (uri, url, tracks), err = album_tracks.resolve(
            "Kendrick Lamar", "To Pimp A Butterfly")
    finally:
        album_tracks.sh = real
    assert err is None, err
    assert uri == "spotify:album:tpab", uri
    assert len(tracks) == 1
    print("ok - check_picks_title_match_not_first_artist_match")


def check_no_title_match_fails_loudly_and_writes_nothing():
    items = _search(
        _item("To Pimp A Butterfly", "Kendrick Lamar", "spotify:album:tpab"),
        _item("DAMN.", "Kendrick Lamar", "spotify:album:damn"),
    )
    tmp = tempfile.mkdtemp()
    real_cache, real_sh = album_tracks.CACHE, _patch_sh(
        _mock(items, _exp("To Pimp A Butterfly")))
    album_tracks.CACHE = tmp
    old_argv = sys.argv
    sys.argv = ["album_tracks.py", "Kendrick Lamar", "Section.80"]
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            try:
                album_tracks.main()
            except SystemExit as e:
                assert e.code == 1, e.code
            else:
                raise AssertionError("main() did not exit(1)")
        out = json.loads(buf.getvalue())
        assert "no album title match" in out["error"], out
        assert os.listdir(tmp) == [], os.listdir(tmp)
    finally:
        album_tracks.CACHE = real_cache
        album_tracks.sh = real_sh
        sys.argv = old_argv
    print("ok - check_no_title_match_fails_loudly_and_writes_nothing")


def check_deluxe_suffix_accepted():
    # "Deluxe" editions are the same album; substring rule must accept them.
    items = _search(
        _item("good kid, m.A.A.d city (Deluxe)", "Kendrick Lamar",
              "spotify:album:gkmc-deluxe"),
    )
    real = _patch_sh(_mock(items, _exp("good kid, m.A.A.d city (Deluxe)")))
    try:
        (uri, url, tracks), err = album_tracks.resolve(
            "Kendrick Lamar", "good kid, m.A.A.d city")
    finally:
        album_tracks.sh = real
    assert err is None, err
    assert uri == "spotify:album:gkmc-deluxe", uri
    print("ok - check_deluxe_suffix_accepted")


def check_experience_title_mismatch_refused():
    # Even if the search pick were wrong, the experience re-check catches it.
    items = _search(
        _item("Section.80", "Kendrick Lamar", "spotify:album:section80"),
    )
    # Search matches Section.80 honestly; experience returns another album.
    real = _patch_sh(_mock(items, _exp("To Pimp A Butterfly")))
    try:
        result, err = album_tracks.resolve("Kendrick Lamar", "Section.80")
    finally:
        album_tracks.sh = real
    assert result is None, result
    assert "does not match" in err, err
    print("ok - check_experience_title_mismatch_refused")


def check_cache_hit_never_calls_api():
    tmp = tempfile.mkdtemp()
    slug = album_tracks.slug("Kendrick Lamar", "To Pimp A Butterfly")
    with open(os.path.join(tmp, slug + ".json"), "w") as f:
        json.dump({"tracks": [{"n": 1, "title": "t"}]}, f)

    def boom(*args):
        raise AssertionError("network touched on cache hit: %r" % (args,))

    real_cache, real_sh = album_tracks.CACHE, _patch_sh(boom)
    album_tracks.CACHE = tmp
    old_argv = sys.argv
    sys.argv = ["album_tracks.py", "Kendrick Lamar", "To Pimp A Butterfly"]
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            album_tracks.main()
        out = json.loads(buf.getvalue())
        assert out["tracks"] == 1 and out["cached"].endswith(slug + ".json"), out
    finally:
        album_tracks.CACHE = real_cache
        album_tracks.sh = real_sh
        sys.argv = old_argv
    print("ok - check_cache_hit_never_calls_api")


def main():
    for check in (check_picks_title_match_not_first_artist_match,
                  check_no_title_match_fails_loudly_and_writes_nothing,
                  check_deluxe_suffix_accepted,
                  check_experience_title_mismatch_refused,
                  check_cache_hit_never_calls_api):
        check()
    return 0


if __name__ == "__main__":
    sys.exit(main())
