#!/usr/bin/env python3
"""L5: CTX session model — derive album duration profiles from tracklists.

Duration is the one CTX axis we can compute without guessing: sum of
track duration_ms from engine/tracklists/*.json, binned into the tiers in
reference/ctx-session-model.md. Energy stays manual (album_tags.json),
because Spotify's audio-features endpoint is gone.

Usage:
    python3 bin/ctx_profiles.py            # every syllabus album
    python3 bin/ctx_profiles.py --week 1   # one week's five albums

Prints JSON: [{"artist", "album", "slot", "minutes", "duration_tier",
"energy" (from album_tags.json, null when untagged), "tracklist": bool}].
Unresolved albums appear with "minutes": null so gaps are visible, not
silent.
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKLIST_DIR = os.path.join(REPO, "engine", "tracklists")
WEEKS_JSON = os.path.join(REPO, "engine", "weeks.json")
TAGS_JSON = os.path.join(REPO, "engine", "album_tags.json")


def norm(s):
    return re.sub(r"[^a-z0-9]+", "-", s.strip().lower()).strip("-")


def slug(artist, album):
    return f"{norm(artist)}--{norm(album)}"


def duration_tier(minutes):
    if minutes is None:
        return None
    if minutes < 40:
        return "short"
    if minutes < 60:
        return "medium"
    if minutes < 80:
        return "long"
    return "epic"


def load_tracklist(artist, album):
    """Exact slug match, then fuzzy containment match on album name."""
    path = os.path.join(TRACKLIST_DIR, slug(artist, album) + ".json")
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    na = norm(album)
    for fname in sorted(os.listdir(TRACKLIST_DIR)):
        if not fname.endswith(".json"):
            continue
        if not fname.startswith(norm(artist).split("-")[0] + "-"):
            continue
        try:
            with open(os.path.join(TRACKLIST_DIR, fname)) as f:
                tl = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if na in norm(tl.get("album", "")) or norm(tl.get("album", "")) in na:
            return tl
    return None


def minutes_of(tl):
    tracks = tl.get("tracks") or []
    total = sum(t.get("duration_ms", 0) for t in tracks)
    return round(total / 60000, 1) if total else None


def main():
    week_filter = None
    for a in sys.argv[1:]:
        if a == "--week" or a.startswith("--week="):
            week_filter = a.split("=", 1)[1] if "=" in a else sys.argv[
                sys.argv.index(a) + 1]
        elif week_filter is None and a.isdigit():
            week_filter = a
    week_filter = int(week_filter) if week_filter else None

    try:
        with open(TAGS_JSON) as f:
            tags = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        tags = {}

    with open(WEEKS_JSON) as f:
        weeks = json.load(f)["weeks"]

    out = []
    for w in weeks:
        if week_filter and w.get("n") != week_filter:
            continue
        picks = [("anchor", w["anchor"])]
        picks += [("adventurous", a) for a in w.get("adventurous", [])]
        picks.append(("wild_card", w["wild_card"]))
        for slot, p in picks:
            tl = load_tracklist(p["artist"], p["album"])
            mins = minutes_of(tl) if tl else None
            tag = tags.get(f"{p['artist'].lower()}|{p['album'].lower()}", {})
            out.append({
                "artist": p["artist"],
                "album": p["album"],
                "week": w.get("n"),
                "slot": slot,
                "minutes": mins,
                "duration_tier": duration_tier(mins),
                "energy": tag.get("energy"),
                "tracklist": tl is not None,
            })
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
