#!/usr/bin/env python3
"""Build the sampler watchlist: track URI -> album mapping for watched weeks.

Resolves each album via spotify-api search, fetches its track listing via
experience, and writes watchlist.json into the private sampler state dir.

Usage:
    python3 build_watchlist.py 1   # build/refresh watchlist for week 1
"""
import json
import os
import subprocess
import sys

LOG_DIR = os.path.expanduser(
    "~/workspace/goals/album-recommender-music-digest/hidden_files/sampler"
)
WATCHLIST = os.path.join(LOG_DIR, "watchlist.json")

# week -> [(album, artist, slot)]
WEEKS = {
    1: [
        ("The Dark Side of the Moon", "Pink Floyd", "anchor"),
        ("Animals", "Pink Floyd", "adventurous"),
        ("A Light for Attracting Attention", "The Smile", "adventurous"),
        ("Beautiful Rewind", "Four Tet", "adventurous"),
        ("Tago Mago", "Can", "wild card"),
    ],
}


def sh(*args):
    out = subprocess.run(args, capture_output=True, text=True, timeout=30)
    return json.loads(out.stdout)


def find_album(album, artist):
    data = sh("spotify-api", "search", "--query", f"{album} by {artist}",
              "--search-type", "ALBUMS")
    cands = []
    for s in data.get("sections", []):
        cands.extend(s.get("items", []))
    artist_l = artist.lower()
    for c in cands:
        if artist_l in str(c.get("subtitle", "")).lower():
            return c["spotify_uri"], c.get("title")
    if cands:  # fallback: top result
        return cands[0]["spotify_uri"], cands[0].get("title")
    return None, None


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
    entries = WEEKS.get(week)
    if not entries:
        print(f"no album list for week {week}")
        return 1
    os.makedirs(LOG_DIR, exist_ok=True)
    try:
        with open(WATCHLIST) as f:
            wl = json.load(f)
    except FileNotFoundError:
        wl = {"tracks": {}, "albums": {}}

    for album, artist, slot in entries:
        album_uri, resolved = find_album(album, artist)
        if not album_uri:
            print(f"NOT FOUND: {album} by {artist}")
            continue
        tracks = album_tracks(album_uri)
        wl["albums"][album_uri] = {
            "album": resolved or album, "artist": artist,
            "week": week, "slot": slot, "track_count": len(tracks),
        }
        for t_uri, t_title in tracks:
            wl["tracks"][t_uri] = {
                "album": resolved or album, "artist": artist,
                "week": week, "slot": slot,
            }
        print(f"week {week} [{slot}]: {resolved or album} — {len(tracks)} tracks")
    wl["week"] = week
    with open(WATCHLIST, "w") as f:
        json.dump(wl, f, indent=1)
    print(f"wrote {WATCHLIST}: {len(wl['tracks'])} tracks, {len(wl['albums'])} albums")
    return 0


if __name__ == "__main__":
    sys.exit(main())
