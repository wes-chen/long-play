#!/usr/bin/env python3
"""M1: grower scheduler — second-chance re-queue for bounced albums.

Research: Madison & Schiölde (2017) — liking rises with repeated exposure.
Albums Wesley "bounced off" get automatically re-queued a few weeks later
for ONE scheduled second chance. Tracked privately; never re-queued more
than once per album.

State: ~/workspace/goals/album-recommender-music-digest/hidden_files/grower-state.json
  { "queue": [ {week, artist, album, slot, bounced_ts,
                requeue_due_week, requeued: bool, requeued_ts,
                second_reaction: null | "played"|"skipped"|"loved"|"bounced off"} ] }

Rules:
  - A bounced album becomes due 4 weeks after its bounce week.
  - Each album re-queued at most once, ever.
  - Only "bounced off" reactions qualify (skips are not bounces).
  - Full albums only (standing rule).

Commands:
  --scan    pick up new bounced-off reactions from the listening log
  --due     print albums due for re-queue this week (JSON)
  --mark-requeued <week> <artist> <album>
            record that the second chance was announced this week
  --record-second <week> <artist> <album> <reaction>
            record his reaction to the second chance (a loved/played here
            marks a "grower" for the M5 Wrapped)
"""
import json
import os
import re
import sys

GOAL = os.path.expanduser("~/workspace/goals/album-recommender-music-digest")
LOG = os.path.join(GOAL, "listening-log.md")
STATE = os.path.join(GOAL, "hidden_files", "grower-state.json")
CURRENT = os.path.expanduser("~/workspace/long-play/weeks/CURRENT")

REQUEUE_GAP_WEEKS = 4  # "a few weeks later"

ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(anchor|adventurous|wild[- ]card)\s*\|\s*"
    r"(played|skipped|loved|bounced off)\b[^|]*\|\s*chat\s*\|",
    re.IGNORECASE)


def load_state():
    try:
        with open(STATE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"queue": []}


def save_state(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    with open(STATE, "w") as f:
        json.dump(s, f, indent=1)


def current_week():
    try:
        with open(CURRENT) as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return None


def scan():
    """Pick up bounced-off reactions not yet in the queue."""
    state = load_state()
    known = {(e["week"], e["artist"].lower(), e["album"].lower()) for e in state["queue"]}
    added = 0
    if not os.path.exists(LOG):
        print(json.dumps({"added": 0, "note": "no listening log yet"}))
        return
    with open(LOG) as f:
        for line in f:
            m = ROW_RE.match(line)
            if not m:
                continue
            week_s, album, artist, slot, reaction = m.groups()
            week = int(week_s)
            if reaction.lower() != "bounced off":
                continue
            key = (week, artist.lower(), album.lower())
            if key in known:
                continue
            state["queue"].append({
                "week": week,
                "artist": artist.strip(),
                "album": album.strip(),
                "slot": slot.strip().lower().replace(" ", "_").replace("-", "_"),
                "bounced_ts": None,
                "requeue_due_week": week + REQUEUE_GAP_WEEKS,
                "requeued": False,
                "requeued_ts": None,
                "second_reaction": None,
                "grower": False,
            })
            known.add(key)
            added += 1
    save_state(state)
    print(json.dumps({"added": added, "queue_size": len(state["queue"])}))


def due():
    """Albums whose second chance falls this week (not yet requeued)."""
    state = load_state()
    week = current_week()
    due_list = [e for e in state["queue"]
                if not e["requeued"] and e["requeue_due_week"] <= (week or 0)]
    print(json.dumps({
        "current_week": week,
        "due": [{"artist": e["artist"], "album": e["album"],
                 "slot": e["slot"], "bounced_week": e["week"]} for e in due_list],
    }, indent=1))


def mark_requeued(week_s, artist, album):
    state = load_state()
    week = int(week_s)
    for e in state["queue"]:
        if (e["week"] == week and e["artist"].lower() == artist.lower()
                and e["album"].lower() == album.lower()):
            if e["requeued"]:
                print(json.dumps({"error": "already re-queued; refusing second re-queue"}))
                return
            e["requeued"] = True
            from datetime import datetime, timezone
            e["requeued_ts"] = datetime.now(timezone.utc).isoformat()
            save_state(state)
            print(json.dumps({"marked": f"{artist} — {album}", "week": week}))
            return
    print(json.dumps({"error": "entry not found"}))


def record_second(week_s, artist, album, reaction):
    state = load_state()
    week = int(week_s)
    reaction = reaction.lower()
    for e in state["queue"]:
        if (e["week"] == week and e["artist"].lower() == artist.lower()
                and e["album"].lower() == album.lower()):
            e["second_reaction"] = reaction
            # grower: bounced off first, then played/loved on the second chance
            e["grower"] = reaction in ("played", "loved")
            save_state(state)
            print(json.dumps({"recorded": reaction, "grower": e["grower"],
                              "album": f"{artist} — {album}"}))
            return
    print(json.dumps({"error": "entry not found"}))


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "--due"
    if cmd == "--scan":
        scan()
    elif cmd == "--due":
        due()
    elif cmd == "--mark-requeued" and len(sys.argv) == 5:
        mark_requeued(sys.argv[2], sys.argv[3], sys.argv[4])
    elif cmd == "--record-second" and len(sys.argv) == 6:
        record_second(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])
    else:
        print("usage: grower.py [--scan|--due|--mark-requeued W ARTIST ALBUM|"
              "--record-second W ARTIST ALBUM REACTION]")


if __name__ == "__main__":
    main()
