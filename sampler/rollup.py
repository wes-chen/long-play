#!/usr/bin/env python3
"""Weekly rollup of sampler data: album-level listening stats.

Reads the private samples.jsonl, aggregates over the trailing N days, and
writes a rollup JSON + prints a human summary. Feeds (eventually) the engine's
user-album interaction matrix and the CTX time-of-day model.

Usage:
    python3 rollup.py [days]     # default 7
"""
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

LOG_DIR = os.path.expanduser(
    "~/workspace/goals/album-recommender-music-digest/hidden_files/sampler"
)
LOG_FILE = os.path.join(LOG_DIR, "samples.jsonl")
ROLLUP_DIR = os.path.join(LOG_DIR, "rollups")
PT = ZoneInfo("America/Los_Angeles")
COMPLETION_PCT = 85.0  # max progress_pct at/above this counts as "completed"


def load_samples(since):
    rows = []
    try:
        with open(LOG_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = datetime.fromisoformat(r["ts"])
                if ts >= since:
                    rows.append(r)
    except FileNotFoundError:
        pass
    return rows


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows = load_samples(since)
    active = [r for r in rows if r.get("playing") and r.get("track_uri")]

    tracks = defaultdict(lambda: {"hits": 0, "max_pct": 0, "name": "", "artists": []})
    albums = defaultdict(lambda: {"hits": 0, "tracks": set(), "name": "", "week": None, "slot": None})
    hours = Counter()
    watch_hits = []

    for r in active:
        t = tracks[r["track_uri"]]
        t["hits"] += 1
        t["name"] = r.get("track")
        t["artists"] = r.get("artists", [])
        t["max_pct"] = max(t["max_pct"], r.get("progress_pct", 0))
        pt_hour = datetime.fromisoformat(r["ts"]).astimezone(PT).hour
        hours[pt_hour] += 1

        wh = r.get("watch_hit")
        album_key = None
        if wh:
            album_key = f"{wh['album']} — {wh['artist']}"
            a = albums[album_key]
            a.update({"name": wh["album"], "week": wh["week"], "slot": wh["slot"]})
            watch_hits.append({
                "ts": r["ts"], "track": r.get("track"),
                "album": wh["album"], "slot": wh["slot"],
            })
        elif r.get("album_context_uri"):
            album_key = r["album_context_uri"]
            a = albums[album_key]
            a.update({"name": r.get("album_context_name") or album_key,
                      "week": None, "slot": None})
        if album_key:
            a = albums[album_key]
            a["hits"] += 1
            a["tracks"].add(r["track_uri"])

    completed_tracks = sum(1 for t in tracks.values() if t["max_pct"] >= COMPLETION_PCT)

    rollup = {
        "window_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n_samples": len(rows),
        "n_active_samples": len(active),
        "n_distinct_tracks": len(tracks),
        "n_completed_tracks": completed_tracks,
        "top_tracks": [
            {"track": t["name"], "artists": t["artists"], "hits": t["hits"],
             "max_progress_pct": t["max_pct"]}
            for _, t in sorted(tracks.items(), key=lambda kv: -kv[1]["hits"])[:15]
        ],
        "albums": [
            {"album": a["name"], "week": a["week"], "slot": a["slot"],
             "hits": a["hits"], "distinct_tracks": len(a["tracks"])}
            for _, a in sorted(albums.items(), key=lambda kv: -kv[1]["hits"])
        ],
        "hour_of_day_pt": dict(sorted(hours.items())),
        "watch_hits": watch_hits,
        "n_watch_hits": len(watch_hits),
    }

    os.makedirs(ROLLUP_DIR, exist_ok=True)
    stamp = datetime.now(PT).strftime("%Y-W%V")
    path = os.path.join(ROLLUP_DIR, f"{stamp}.json")
    with open(path, "w") as f:
        json.dump(rollup, f, indent=1)

    # human summary
    print(f"rollup {stamp}: {len(active)} active samples / {len(rows)} total, "
          f"{len(tracks)} tracks, {completed_tracks} completed")
    if rollup["albums"]:
        print("albums:")
        for a in rollup["albums"][:10]:
            tag = f" [week {a['week']} {a['slot']}]" if a["week"] else ""
            print(f"  {a['album']}{tag}: {a['hits']} samples, {a['distinct_tracks']} tracks")
    if watch_hits:
        print(f"WATCH HITS: {len(watch_hits)} samples on recommended albums")
    if hours:
        top_hours = sorted(hours.items(), key=lambda kv: -kv[1])[:5]
        print("peak hours (PT): " + ", ".join(f"{h}:00 ({c})" for h, c in top_hours))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
