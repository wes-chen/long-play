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
liner drop verbatim from the week file. Attachment honors the M3
day-offset delivery schedule (liner due from day offset 1, timed cue from
day offset 3, counted from the Monday digest); parts not yet due are
null. guided_cue is null when no cue parts are due yet for the week or
cues are not built for the week.

Rotation: the five albums appear in file order; the album at index
(week_number - 1) % 5 is skipped that week (so the anchor — known ground —
sits out week 1, and every album gets a drip over any 5-week span). The
remaining four map Tue -> Fri in order.

Silent cases (prints {"silent": "<reason>"} and exits 0): no week delivered
yet, week file missing/unparseable, or not a Tue-Fri run. The drip never
alters the week's picks — read-only.

Blind weeks (#20): the predictions file may flag a week blind. On a blind
week the drip must not spoil the reveal — the pick JSON carries the A–E
file-order label (matching the digest's labeling) in artist/album, nulls
year/listen_for/guided_cue, and sets "blind": true. The drip worker renders
the label only: no artist/album names, no listen-for line, no guided cue
(the real track titles and start times stay hidden) until feedback is
logged. Redaction happens at the JSON source, so the drip cron body needs
no matching guard — the composition rules only ever see blind-safe text.

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
PREDICTIONS = os.path.expanduser(
    "~/workspace/goals/album-recommender-music-digest/hidden_files/"
    "predictions.json"
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


def _norm(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").strip().lower()).strip("-")


def attach_guided_cue(pick, today=None):
    """M3: attach the day's guided-listening cue from engine/guided_cues.json.

    Honors the M3 day-offset delivery schedule: the liner drop is due from
    day offset 1 and the timed cue from day offset 3 (offsets count from
    the Monday digest, day 0; the drip runs Tue=1 .. Fri=4). Uses
    cues_due.due_cues as the single schedule source, so the drip can never
    ship a cue part the schedule says is not due yet — the day-3 timed cue
    no longer ships on Tuesday morning.

    Adds {"guided_cue": {timed, track_n, track_title, starts_at, liner}}
    with only the due parts present (not-yet-due parts are None), or
    {"guided_cue": None} when nothing is due yet / cues are not built for
    the week. A timed cue whose text is still pending the Monday digest's
    finalized listen-for (cue_text_pending) is dropped — never shipped
    as scaffold text (#25). Never fabricates a cue.
    """
    try:
        from cues_due import due_cues
    except ImportError:
        pick["guided_cue"] = None
        return pick
    day_offset = (today or datetime.datetime.now(PT).date()).weekday()
    due = due_cues(pick.get("week"), day_offset)
    entry = None
    for item in due.get("cues", []):
        if (_norm(item.get("artist")) == _norm(pick.get("artist"))
                and _norm(item.get("album")) == _norm(pick.get("album"))):
            entry = item
            break
    if not entry:
        pick["guided_cue"] = None
        return pick
    timed = entry.get("timed") or {}
    liner = entry.get("liner") or {}
    # Defense in depth (#25): due_cues already filters scaffold text, but
    # the drip is a user-facing surface — never ship a cue whose text is
    # still pending the Monday digest's finalized listen-for.
    if timed.get("cue_text_pending"):
        timed = {}
    pick["guided_cue"] = {
        "timed": timed.get("cue"),
        "track_n": timed.get("track_n"),
        "track_title": timed.get("track_title"),
        "starts_at": timed.get("starts_at"),
        "liner": liner.get("text"),
    }
    return pick


def read_delivered():
    try:
        with open(DELIVERED) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def is_blind_week(week):
    """True when predictions.json flags this week blind. Fail-closed: any
    read error or missing week entry means not blind."""
    try:
        with open(PREDICTIONS) as f:
            weeks = json.load(f).get("weeks", {})
    except (FileNotFoundError, json.JSONDecodeError, AttributeError):
        return False
    entry = weeks.get(str(week), {})
    return bool(entry.get("blind"))


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


def main(today=None):
    mark_sent = "--mark-sent" in sys.argv
    today = today or datetime.datetime.now(PT).date()
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

    if is_blind_week(week):
        # #20: blind week — redact identity at the JSON source. The A–E
        # label follows file order, matching the digest's blind labeling.
        # Stay silent on the guided cue: its track titles and start times
        # are real tracklist data that could identify the album.
        label = "Album " + "ABCDE"[albums.index(drip_order[DRIP_DAYS[today.weekday()]])]
        pick["blind"] = True
        pick["artist"] = label
        pick["album"] = label
        pick["year"] = ""
        pick["listen_for"] = None
        pick["guided_cue"] = None
    else:
        pick["blind"] = False
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
