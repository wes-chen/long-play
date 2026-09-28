#!/usr/bin/env python3
"""M3: guided-cue delivery query — "what cues are due now?"

This is the timing mechanism for engine/guided_cues.json. The mid-week
flow calls this script; it prints the current week's due cues as JSON to
stdout.

Intra-week day offsets count from the Monday digest (day 0):
    day 1 — liner drop (context, early-week)
    day 3 — timed cue (track-boundary prompt, mid-week)
The schedule lives in the "deliver" block each album entry carries
(built by bin/build_guided_cues.py).

Usage:
    python3 bin/cues_due.py --week N [--day-offset D] [--today YYYY-MM-DD]

Without --day-offset, D defaults to days elapsed since Monday (weekday()
of --today, or of today). An album's liner is due when
deliver.liner_day_offset <= D; its timed cue when
deliver.timed_day_offset <= D. Missing liner/timed entries are simply
absent from the output — never fabricated. A timed cue flagged
cue_text_pending (scaffold text awaiting the Monday digest's finalized
listen-for, #25) is never due, whatever the schedule says.

Relationship to the daily drip: bin/drip_pick.py (Tue-Fri spotlight) is
one delivery surface and attaches that day's cue; this script is the
schedule query the mid-week flow uses when it needs the full "due now"
set for the week. Scheduling itself is owned by the coordinator.
"""
import argparse
import json
import os
import sys
from datetime import date, datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUES = os.path.join(REPO, "engine", "guided_cues.json")


def day_offset_from(d):
    return d.weekday()  # Monday == 0, so days elapsed since Monday


def due_cues(week, day_offset):
    try:
        with open(CUES) as f:
            weeks = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"error": "engine/guided_cues.json missing or unreadable"}
    week_cues = weeks.get(str(week))
    if not week_cues:
        return {"week": week, "day_offset": day_offset, "cues": [],
                "note": "no cues built for this week"}
    out = []
    for entry in week_cues.values():
        deliver = entry.get("deliver") or {}
        timed_entry = entry.get("timed") or {}
        # A cue flagged cue_text_pending is scaffold text ("[the week's
        # listen-for lands with the Monday digest]"), not a finalized cue —
        # it is never due, whatever the schedule says (#25).
        timed_pending = bool(timed_entry.get("cue_text_pending"))
        liner_due = (deliver.get("liner_day_offset", 99) <= day_offset
                     and entry.get("liner"))
        timed_due = (deliver.get("timed_day_offset", 99) <= day_offset
                     and timed_entry and not timed_pending)
        if not (liner_due or timed_due):
            continue
        item = {"artist": entry.get("artist"), "album": entry.get("album"),
                "slot": entry.get("slot"), "deliver": deliver}
        if liner_due:
            item["liner"] = {"text": entry["liner"],
                             "source": entry.get("liner_source")}
        if timed_due:
            t = entry["timed"]
            item["timed"] = {
                "track_n": t.get("track_n"),
                "track_title": t.get("track_title"),
                "starts_at": t.get("starts_at"),
                "cue": t.get("cue"),
                "named_in_cue": t.get("named_in_cue"),
                "curated_moment": t.get("curated_moment"),
            }
        out.append(item)
    return {"week": week, "day_offset": day_offset, "cues": out}


def main():
    ap = argparse.ArgumentParser(description="Print this week's due guided cues as JSON.")
    ap.add_argument("--week", required=True, type=int)
    ap.add_argument("--day-offset", type=int, default=None)
    ap.add_argument("--today", default=None,
                    help="YYYY-MM-DD; used to derive --day-offset when not given")
    args = ap.parse_args()
    if args.day_offset is not None:
        d = args.day_offset
    else:
        try:
            day = (datetime.strptime(args.today, "%Y-%m-%d").date()
                   if args.today else date.today())
        except ValueError:
            print(json.dumps({"error": "--today must be YYYY-MM-DD"}))
            return 1
        d = day_offset_from(day)
    print(json.dumps(due_cues(args.week, d), indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
