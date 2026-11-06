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
PINNED_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "pinned_albums.json")

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


def artist_matches(artist, subtitle):
    """True when the requested artist is one of the result's artists.

    Token-exact on the comma-separated subtitle: "Ride" matches "Ride"
    or "Ride, Someone Else" but not "Jaded Juice Riders" or "Fly-By
    Ride", where it only appears inside another artist's name. A
    word-boundary regex is not enough here: hyphens are word
    boundaries, so it still matched "Fly-By Ride" and misattributed
    that album to Ride in the live week-6 watchlist.
    """
    tokens = [(t or "").strip().lower() for t in (subtitle or "").split(",")]
    return artist.lower() in tokens


def load_pins():
    """(normalized album, artist) -> Spotify album URI for search-invisible
    records. Missing or malformed file means no pins, never a crash:
    the search path below is the default and pins are only a fallback."""
    try:
        with open(PINNED_FILE) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    pins = {}
    for p in data.get("pins", []):
        try:
            pins[(norm_title(p["album"]), p["artist"].strip().lower())] = \
                p["spotify_uri"]
        except (KeyError, AttributeError):
            continue
    return pins


def find_album(album, artist):
    # Pinned first: a verified URI beats a search that cannot see the
    # record at all (live case: Ride's Nowhere — no album or artist-scoped
    # query surfaces it, and the artist page caps at 5 recent albums).
    pinned = load_pins().get((norm_title(album), artist.strip().lower()))
    if pinned:
        return pinned, album, False
    # Artist-scoped search with a bare-title query. The old
    # "{album} by {artist}" query text misdirects the backend: with it,
    # Loveless by My Bloody Valentine returns the band's other records
    # and never the album itself, while the bare title plus --artist
    # returns it first.
    data = sh("spotify-api", "search", "--query", album,
              "--artist", artist, "--search-type", "ALBUMS")
    cands = []
    for s in data.get("sections", []):
        cands.extend(s.get("items", []))
    artist_match = [c for c in cands
                    if artist_matches(artist, c.get("subtitle"))]
    # ADV-LP-04: match the *album*, not just the artist — a saved album by
    # the same artist (e.g. Wall Of Eyes) is a different record.
    want = norm_title(album)
    title_match = [c for c in artist_match
                   if norm_title(c.get("title")).startswith(want)]
    # No title fallback: when no title matches, returning the first
    # same-artist album silently misattributes a different record
    # (live case: "Nowhere" by Ride resolved to "Songs from the Middle
    # of Nowhere" by Fly-By Ride, and "Loveless" resolved to the
    # "you made me realise" EP). Failing loudly keeps the watchlist
    # honest; the caller reports the miss as a warning.
    pool = title_match
    # Prefer the edition already in the library ("SAVED" trait): its
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

    # Build the new watchlist in memory first and only write it once it
    # is proven good. A total resolve failure must never clobber the
    # working watchlist: the old code cleared the previous week's entries
    # up front, so one transient resolver failure (0 albums resolved) left
    # the sampler blind for the whole week — no watch hits at all, and the
    # rollover still advanced because the build exited 0.
    new_tracks = {}
    new_albums = {}
    n_missing = 0
    for album, artist, slot in entries:
        album_uri, resolved, saved = find_album(album, artist)
        if not album_uri:
            print(f"NOT FOUND: {album} by {artist}")
            n_missing += 1
            continue
        tracks = album_tracks(album_uri)
        new_albums[album_uri] = {
            "album": resolved or album, "artist": artist,
            "week": week, "slot": slot, "track_count": len(tracks),
            "edition_from_library": saved,
        }
        for t_uri, t_title in tracks:
            new_tracks[t_uri] = {
                "album": resolved or album, "artist": artist,
                "week": week, "slot": slot, "album_uri": album_uri,
                # ADV-LP-04: track title stored for the name-normalized
                # fallback match in poll.py (edition URI mismatches).
                "track": t_title,
            }
        tag = " [library edition]" if saved else ""
        print(f"week {week} [{slot}]: {resolved or album} — {len(tracks)} tracks{tag}")

    if not new_albums:
        # Fail loudly: the existing watchlist stays untouched, and the
        # caller (bin/rollover.py) refuses to advance on a nonzero exit,
        # so a dead-resolver week surfaces the same day instead of
        # silently running with zero attribution.
        print(f"watchlist build failed: resolved 0/{len(entries)} albums "
              f"for week {week}; leaving the existing watchlist untouched",
              file=sys.stderr)
        return 1
    if n_missing:
        print(f"warning: {n_missing}/{len(entries)} albums unresolved; "
              f"watchlist covers the rest", file=sys.stderr)

    wl = {"tracks": new_tracks, "albums": new_albums, "week": week}
    with open(WATCHLIST, "w") as f:
        json.dump(wl, f, indent=1)
    print(f"wrote {WATCHLIST}: {len(wl['tracks'])} tracks, {len(wl['albums'])} albums")
    return 0


if __name__ == "__main__":
    sys.exit(main())
