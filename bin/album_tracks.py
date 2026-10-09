#!/usr/bin/env python3
"""Resolve a syllabus album to its Spotify tracklist and cache it.

Usage: python3 bin/album_tracks.py "<artist>" "<album>"
Writes engine/tracklists/<slug>.json:
  {artist, album, spotify_uri, spotify_url, tracks: [{n, title, duration_ms,
   starts_at_ms, starts_at}], fetched_at}

Track titles keep Spotify's suffixes ("- 2011 Remastered") for matching;
a cleaned title is also stored. All timing data is real (Spotify), never
invented — intra-track "listen at 2:14" moments are NOT generated here;
those need manual curation.

Album identity is verified, not assumed: the resolver only accepts a
search result whose artist AND album title both match the request (a
same-artist different-album result is refused rather than cached), and
re-checks the fetched experience's album title before writing the cache.
When nothing matches it fails loudly instead of writing a mislabeled
cache — a wrong tracklist poisons guided cues, durations, and watchlist
mapping downstream.
"""
import json
import os
import re
import subprocess
import sys
from difflib import SequenceMatcher

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, "engine", "tracklists")

# Minimum SequenceMatcher ratio (on normalized titles) to accept a
# search result whose title is neither equal to nor a super/substring
# of the requested album name. Exact, substring ("Deluxe" editions,
# remaster suffixes), and close-fuzzy titles pass; a different album
# by the same artist does not.
TITLE_MATCH_THRESHOLD = 0.82

CLEAN_RE = re.compile(r"\s*[-–—]\s*(\d{4}\s+)?remaster(ed)?$", re.IGNORECASE)


def norm(s):
    return re.sub(r"[^a-z0-9]+", "-", s.strip().lower()).strip("-")


def slug(artist, album):
    return f"{norm(artist)}--{norm(album)}"


def clean_title(t):
    return CLEAN_RE.sub("", t).strip()


def titles_match(requested, found):
    """True when a Spotify result title plausibly names the requested album.

    Compares normalized titles (lowercased, punctuation stripped). Accepts
    exact matches, super/substring matches (covers "Deluxe"/remaster
    suffixes on either side), and close fuzzy matches. Rejects a different
    album title outright.
    """
    r, f = norm(requested), norm(found)
    if not r or not f:
        return False
    if r == f or r in f or f in r:
        return True
    return SequenceMatcher(None, r, f).ratio() >= TITLE_MATCH_THRESHOLD


def sh(*args):
    return subprocess.run(args, capture_output=True, text=True, timeout=60)


def resolve(artist, album):
    """Return (spotify_uri, spotify_url, tracks) for the best album match."""
    r = sh("spotify-api", "search", "--query", f"{artist} {album}",
           "--search-type", "ALBUMS")
    if r.returncode != 0:
        return None, f"search failed: {r.stderr.strip()[:200]}"
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        return None, "search returned non-JSON"
    items = []
    for section in data.get("sections", []):
        items.extend(section.get("items", []))
    if not items:
        return None, "no album results"
    a_low = artist.lower()
    pick = None
    for it in items:
        if a_low not in (it.get("subtitle") or "").lower():
            continue
        if titles_match(album, it.get("title") or ""):
            pick = it
            break
    if pick is None:
        top = ", ".join(repr(it.get("title")) for it in items[:5])
        return None, (f"no album title match for {album!r} by {artist!r} "
                      f"among {len(items)} results (top: {top})")
    uri = pick.get("spotify_uri")
    if not uri:
        return None, "no spotify uri in result"
    r2 = sh("spotify-api", "experience", "--id", uri)
    if r2.returncode != 0:
        return None, f"experience failed: {r2.stderr.strip()[:200]}"
    try:
        exp = json.loads(r2.stdout)
    except json.JSONDecodeError:
        return None, "experience returned non-JSON"
    exp_title = exp.get("title") or ""
    if exp_title and not titles_match(album, exp_title):
        return None, (f"experience album title {exp_title!r} does not match "
                      f"requested {album!r}; refusing to cache")
    tracks = []
    n = 0
    for section in exp.get("sections", []):
        for it in section.get("items", []):
            title = it.get("title") or ""
            if not title or "duration_ms" not in it:
                continue
            n += 1
            tracks.append({
                "n": n,
                "title": title,
                "clean_title": clean_title(title),
                "duration_ms": it.get("duration_ms") or 0,
                "spotify_uri": it.get("spotify_uri"),
                "spotify_url": it.get("spotify_url"),
            })
    if not tracks:
        return None, "no tracks in experience"
    return (uri, pick.get("spotify_url"), tracks), None


def fmt_ms(ms):
    s = ms // 1000
    return f"{s // 60}:{s % 60:02d}"


def main():
    if len(sys.argv) != 3:
        print('usage: album_tracks.py "<artist>" "<album>"')
        sys.exit(2)
    artist, album = sys.argv[1], sys.argv[2]
    path = os.path.join(CACHE, slug(artist, album) + ".json")
    if os.path.exists(path):
        with open(path) as f:
            cached = json.load(f)
        print(json.dumps({"cached": path, "tracks": len(cached["tracks"])}))
        return
    result, err = resolve(artist, album)
    if err:
        print(json.dumps({"error": err, "artist": artist, "album": album}))
        sys.exit(1)
    uri, url, tracks = result
    cursor = 0
    for t in tracks:
        t["starts_at_ms"] = cursor
        t["starts_at"] = fmt_ms(cursor)
        cursor += t["duration_ms"]
    payload = {
        "artist": artist, "album": album,
        "spotify_uri": uri, "spotify_url": url,
        "tracks": tracks,
        "fetched_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
    }
    os.makedirs(CACHE, exist_ok=True)
    with open(path, "w") as f:
        json.dump(payload, f, indent=1)
    print(json.dumps({"cached": path, "tracks": len(tracks), "uri": uri}))


if __name__ == "__main__":
    main()
