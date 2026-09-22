#!/usr/bin/env python3
"""NL-01: album-of-the-day drip picker for the long-play course.

Reads weeks/CURRENT and the delivery marker
~/workspace/goals/album-recommender-music-digest/hidden_files/digest-delivered.json,
parses the five album sections (in file order) from weeks/week-NN.md, and
prints today's spotlight pick as JSON.

M3: the pick JSON also carries a "guided_cue" block
({timed, track_n, track_title, starts_at, liner}) from
engine/guided_cues.json — a real track boundary from the Spotify tracklist
cache paired with the week's curated "Listen for" cue, plus a one-line
liner drop verbatim from the week file. guided_cue is null when cues are
not yet built for the week.

Rotation: the five albums appear in file order; the album at index
(week_number - 1) % 5 is skipped that week (so the anchor — known ground —
sits out week 1, and every album gets a drip over any 5-week span). The
remaining four map Tue -> Fri in order.

Silent cases (prints {"silent": "<reason>"} and exits 0): no week delivered
yet, week file missing/unparseable, or not a Tue-Fri run. The drip never
alters the week's picks — read-only.

Usage:
    python3 bin/drip_pick.py            # print today's pick (or silent reason)
    python3 bin/drip_pick.py --mark-sent  # record today's pick in the watermark
"""
import datetime
import json
import os
import re
import sys
from zoneinfo import ZoneInfo

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CURRENT_PATH = os.path.join(REPO, "weeks", "CURRENT")
DELIVERED = os.path.expanduser(
    "~/workspace/goals/album-recommender-music-digest/hidden_files/"
    "digest-delivered.json"
)
DRIP_SENT = os.path.expanduser(
    "~/workspace/goals/album-recommender-music-digest/hidden_files/"
    "drip-sent.json"
)
PT = ZoneInfo("America/Los_Angeles")
# Tue..Fri -> position in the 4-album drip order
DRIP_DAYS = {1: 0, 2: 1, 3: 2, 4: 3}  # datetime.weekday(): Tue=1 .. Fri=4

SECTION_RE = re.compile(
    r"^##\s+(Anchor|Adventurous|Wild card)\s+[—–-]\s+(.+?)\s+[—–-]\s+\*(.+?)\*\s*(\(\d{4}\))?",
    re.IGNORECASE,
)
LISTEN_FOR_RE = re.compile(r"\*\*Listen for:\*\*\s*(.+)", re.IGNORECASE)


def silent(reason):
    print(json.dumps({"silent": reason}))
    return 0


def attach_guided_cue(pick):
    """M3: attach the day's guided-listening cue from engine/guided_cues.json.

    Adds {"guided_cue": {timed: {...}, liner: ...}} or {"guided_cue": None}
    when cues are not yet built for the week. Never fabricates a cue.
    """
    try:
        with open(os.path.join(REPO, "engine", "guided_cues.json")) as f:
            cues = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pick["guided_cue"] = None
        return pick
    week_cues = cues.get(str(pick.get("week")), {})
    key = "%s|%s" % (re.sub(r"[^a-z0-9]+", "-", pick["artist"].strip().lower()).strip("-"),
                     re.sub(r"[^a-z0-9]+", "-", pick["album"].strip().lower()).strip("-"))
    entry = week_cues.get(key)
    if not entry:
        pick["guided_cue"] = None
        return pick
    timed = entry.get("timed") or {}
    pick["guided_cue"] = {
        "timed": timed.get("cue"),
        "track_n": timed.get("track_n"),
        "track_title": timed.get("track_title"),
        "starts_at": timed.get("starts_at"),
        "liner": entry.get("liner"),
    }
    return pick


def read_delivered():
    try:
        with open(DELIVERED) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def parse_week_file(path):
    """Return the five album sections in file order.

    Each entry: {"slot", "artist", "album", "year", "listen_for"}.
    """
    try:
        with open(path) as f:
            text = f.read()
    except FileNotFoundError:
        return None
    albums = []
    current = None
    in_cue = False
    for line in text.splitlines():
        stripped = line.strip()
        m = SECTION_RE.match(stripped)
        if m:
            if current:
                albums.append(current)
            slot, artist, album, year = m.groups()
            current = {
                "slot": slot.strip().lower().replace(" ", "_"),
                "artist": artist.strip(),
                "album": album.strip(),
                "year": (year or "").strip("()"),
                "listen_for": "",
            }
            in_cue = False
            continue
        if current is None:
            continue
        m2 = LISTEN_FOR_RE.search(line)
        if m2:
            # cue may wrap across lines; accumulate until a blank line
            current["listen_for"] = m2.group(1).strip()
            in_cue = True
            continue
        if in_cue:
            if stripped == "":
                in_cue = False
            else:
                current["listen_for"] += " " + stripped
    if current:
        albums.append(current)
    return albums if len(albums) == 5 else None


def main():
    mark_sent = "--mark-sent" in sys.argv
    today = datetime.datetime.now(PT).date()
    delivered = read_delivered()
    if not delivered:
        return silent("no week delivered yet; staying silent until the first Monday digest")
    week = max(delivered)
    week_file = os.path.join(REPO, "weeks", "week-%02d.md" % week)
    albums = parse_week_file(week_file)
    if albums is None:
        return silent("week file %s missing or unparseable" % week_file)
    if today.weekday() not in DRIP_DAYS:
        return silent("not a drip day (Tue-Fri only)")
    try:
        with open(DRIP_SENT) as f:
            sent = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        sent = {}
    day_key = today.isoformat()
    if day_key in sent and not mark_sent:
        return silent("already spotlighted %s today" % sent[day_key].get("album"))

    skip = (week - 1) % 5
    drip_order = [a for i, a in enumerate(albums) if i != skip]
    pick = drip_order[DRIP_DAYS[today.weekday()]]
    pick = dict(pick)
    pick["week"] = week
    pick = attach_guided_cue(pick)

    if mark_sent:
        sent[day_key] = {"album": pick["album"], "artist": pick["artist"],
                         "week": week}
        # keep ~90 days of history
        for k in sorted(sent)[:-90]:
            del sent[k]
        os.makedirs(os.path.dirname(DRIP_SENT), exist_ok=True)
        with open(DRIP_SENT, "w") as f:
            json.dump(sent, f, indent=1)
        print(json.dumps({"marked_sent": day_key, "album": pick["album"]}))
        return 0

    print(json.dumps(pick, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
