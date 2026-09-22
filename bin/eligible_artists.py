#!/usr/bin/env python3
"""NL-02: syllabus-artist universe for the concert proximity alert.

Prints the unique artists from engine/weeks.json for DELIVERED weeks only —
never future, unreleased weeks (no spoilers). The weekly cron worker
web-searches this list for Bay Area tour announcements.

Reads the delivery marker
~/workspace/goals/album-recommender-music-digest/hidden_files/digest-delivered.json.
Prints JSON: {"silent": reason} when nothing is delivered yet, otherwise
{"artists": [{"artist", "weeks": [...], "albums": [...]}]} in first-appearance
order.

Usage: python3 bin/eligible_artists.py
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEEKS_JSON = os.path.join(REPO, "engine", "weeks.json")
DELIVERED = os.path.expanduser(
    "~/workspace/goals/album-recommender-music-digest/hidden_files/"
    "digest-delivered.json"
)


def main():
    try:
        with open(DELIVERED) as f:
            delivered = sorted(set(json.load(f)))
    except (FileNotFoundError, json.JSONDecodeError):
        delivered = []
    if not delivered:
        print(json.dumps({"silent": "no week delivered yet"}))
        return 0
    with open(WEEKS_JSON) as f:
        weeks = json.load(f)["weeks"]
    seen = {}
    for w in weeks:
        n = w.get("n")
        if n not in delivered:
            continue  # future weeks stay out — no spoilers
        for slot in ("anchor", "adventurous", "wild_card"):
            entries = w.get(slot)
            if isinstance(entries, dict):
                entries = [entries]
            for e in entries or []:
                artist = (e.get("artist") or "").strip()
                album = (e.get("album") or "").strip()
                if not artist:
                    continue
                seen.setdefault(artist, {"weeks": [], "albums": []})
                if n not in seen[artist]["weeks"]:
                    seen[artist]["weeks"].append(n)
                if album and album not in seen[artist]["albums"]:
                    seen[artist]["albums"].append(album)
    artists = [{"artist": a, "weeks": v["weeks"], "albums": v["albums"]}
               for a, v in seen.items()]
    print(json.dumps({"artists": artists}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
