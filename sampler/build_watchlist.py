#!/usr/bin/env python3
"""Build the sampler watchlist: track URI -> album mapping for watched weeks.

Resolves each album via spotify-api search, fetches its track listing via
experience, and writes watchlist.json into the private sampler state dir.

Usage:
    python3 build_watchlist.py 1   # build/refresh watchlist for week 1
"""
import json
import os
import re
import subprocess
import sys

LOG_DIR = os.path.expanduser(
    "~/workspace/goals/album-recommender-music-digest/hidden_files/sampler"
)
WATCHLIST = os.path.join(LOG_DIR, "watchlist.json")
WEEKS_JSON = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "engine", "weeks.json")

# week -> [(album, artist, slot)]
# ADV-LP-01: the machine-readable 24-week plan lives in engine/weeks.json
# (generated from syllabus.md by bin/syllabus_to_weeks.py). The hardcoded
# dict below is the Week 1 fallback only.
WEEKS = {
    1: [
        ("The Dark Side of the Moon", "Pink Floyd", "anchor"),
        ("Animals", "Pink Floyd", "adventurous"),
        ("A Light for Attracting Attention", "The Smile", "adventurous"),
        ("Beautiful Rewind", "Four Tet", "adventurous"),
        ("Tago Mago", "Can", "wild card"),
    ],
}


def load_weeks():
    try:
        with open(WEEKS_JSON) as f:
            data = json.load(f)
        weeks = {}
        for w in data.get("weeks", []):
            entries = [(w["anchor"]["album"], w["anchor"]["artist"], "anchor")]
            entries += [(a["album"], a["artist"], "adventurous")
                        for a in w["adventurous"]]
            entries.append((w["wild_card"]["album"], w["wild_card"]["artist"],
                            "wild card"))
            weeks[w["n"]] = entries
        return weeks
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return WEEKS


def sh(*args):
    out = subprocess.run(args, capture_output=True, text=True, timeout=30)
    return json.loads(out.stdout)


def norm_title(s):
    s = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", s or "").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", s)).strip()


def find_album(album, artist):
    data = sh("spotify-api", "search", "--query", f"{album} by {artist}",
              "--search-type", "ALBUMS")
    cands = []
    for s in data.get("sections", []):
        cands.extend(s.get("items", []))
    artist_l = artist.lower()
    artist_match = [c for c in cands
                    if artist_l in str(c.get("subtitle", "")).lower()]
    # ADV-LP-04: match the *album*, not just the artist — a saved album by
    # the same artist (e.g. Wall Of Eyes) is a different record.
    want = norm_title(album)
    title_match = [c for c in artist_match
                   if norm_title(c.get("title")).startswith(want)]
    pool = title_match or artist_match
    # Prefer the edition already in Wesley's library ("SAVED" trait): its
    # track URIs are what his plays will carry, so watch hits attribute.
    for c in pool:
        if "SAVED" in (c.get("traits") or []):
            return c["spotify_uri"], c.get("title"), True
    if pool:
        return pool[0]["spotify_uri"], pool[0].get("title"), False
    return None, None, False


def album_tracks(album_uri):
    data = sh("spotify-api", "experience", "--id", album_uri)
    tracks = []
    for s in data.get("sections", []):
        for it in s.get("items", []):
            uri = it.get("spotify_uri", "")
            if uri.startswith("spotify:track:"):
                tracks.append((uri, it.get("title")))
    return tracks


def main():
    week = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    entries = load_weeks().get(week)
    if not entries:
        print(f"no album list for week {week}")
        return 1
    os.makedirs(LOG_DIR, exist_ok=True)
    try:
        with open(WATCHLIST) as f:
            wl = json.load(f)
    except FileNotFoundError:
        wl = {"tracks": {}, "albums": {}}

    # ADV-LP-04: clear stale weeks — track URIs from older weeks keep
    # matching forever and poison watch-hit attribution. Only the current
    # week's entries may remain.
    wl["tracks"] = {u: e for u, e in wl.get("tracks", {}).items()
                    if e.get("week") == week}
    wl["albums"] = {u: e for u, e in wl.get("albums", {}).items()
                    if e.get("week") == week}

    resolved_uris = set()
    for album, artist, slot in entries:
        album_uri, resolved, saved = find_album(album, artist)
        if not album_uri:
            print(f"NOT FOUND: {album} by {artist}")
            continue
        tracks = album_tracks(album_uri)
        wl["albums"][album_uri] = {
            "album": resolved or album, "artist": artist,
            "week": week, "slot": slot, "track_count": len(tracks),
            "edition_from_library": saved,
        }
        for t_uri, t_title in tracks:
            wl["tracks"][t_uri] = {
                "album": resolved or album, "artist": artist,
                "week": week, "slot": slot, "album_uri": album_uri,
                # ADV-LP-04: track title stored for the name-normalized
                # fallback match in poll.py (edition URI mismatches).
                "track": t_title,
            }
        tag = " [library edition]" if saved else ""
        print(f"week {week} [{slot}]: {resolved or album} — {len(tracks)} tracks{tag}")
        resolved_uris.add(album_uri)

    # Prune anything this run did not resolve (e.g. a same-artist wrong
    # album from an older build) — only the current week's albums may match.
    wl["albums"] = {u: e for u, e in wl["albums"].items() if u in resolved_uris}
    wl["tracks"] = {u: e for u, e in wl["tracks"].items()
                    if e.get("album_uri") in resolved_uris or e.get("week") != week}
    wl["week"] = week
    wl["week"] = week
    with open(WATCHLIST, "w") as f:
        json.dump(wl, f, indent=1)
    print(f"wrote {WATCHLIST}: {len(wl['tracks'])} tracks, {len(wl['albums'])} albums")
    return 0


if __name__ == "__main__":
    sys.exit(main())
