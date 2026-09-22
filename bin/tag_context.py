#!/usr/bin/env python3
"""M9: one-tap listening-context tags.

When Wesley tags a reaction with where he listened
(commute / focused / background / late-night), the tag is appended to the
private context-tags log. Tags feed the M2 taste vector as per-context
genre modifiers (e.g. ambient scores higher in late-night).

State: ~/workspace/goals/album-recommender-music-digest/hidden_files/context-tags.jsonl
  {"ts","week","artist","album","genre","context","reaction"}

Usage: python3 bin/tag_context.py <week> "<artist>" "<album>" <context> <reaction>
  context: commute | focused | background | late-night
  reaction: played | skipped | loved | bounced off
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOAL = os.path.expanduser("~/workspace/goals/album-recommender-music-digest")
OUT = os.path.join(GOAL, "hidden_files", "context-tags.jsonl")
VALID = {"commute", "focused", "background", "late-night"}
VALID_R = {"played", "skipped", "loved", "bounced off"}


def norm(s):
    return " ".join(s.strip().lower().split())


def main():
    if len(sys.argv) != 6:
        print('usage: tag_context.py <week> "<artist>" "<album>" <context> <reaction>')
        sys.exit(2)
    week, artist, album, context, reaction = sys.argv[1:6]
    context, reaction = context.lower(), reaction.lower()
    if context not in VALID:
        print(f"bad context; want one of {sorted(VALID)}")
        sys.exit(2)
    if reaction not in VALID_R:
        print(f"bad reaction; want one of {sorted(VALID_R)}")
        sys.exit(2)
    genre = None
    try:
        with open(os.path.join(REPO, "engine", "album_tags.json")) as f:
            tags = json.load(f)
        genre = tags.get(f"{norm(artist)}|{norm(album)}", {}).get("genre")
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "week": int(week),
             "artist": artist, "album": album, "genre": genre,
             "context": context, "reaction": reaction}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(json.dumps({"tagged": entry}, indent=1))


if __name__ == "__main__":
    main()
