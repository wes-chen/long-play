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
WATCHLIST = os.path.join(LOG_DIR, "watchlist.json")
PT = ZoneInfo("America/Los_Angeles")
COMPLETION_PCT = 85.0  # max progress_pct at/above this counts as "completed"

# ADV-LP-03: the polls run on this schedule. The disclaimer below must stay
# in sync if it changes — zero hits describe coverage, not taste.
COVERAGE_LABEL = ("daily polls 07:19-10:19, 15:19-17:19, 19:19, 21:19 PT; "
                  "zero hits do not mean skipped")


def load_samples(since):
    rows = []
    malformed = 0
    try:
        with open(LOG_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    # ADV-LP-12: one malformed line must not kill the rollup.
                    r = json.loads(line)
                    ts = datetime.fromisoformat(r["ts"])
                except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                    malformed += 1
                    continue
                if ts >= since:
                    rows.append(r)
    except FileNotFoundError:
        pass
    return rows, malformed


def load_watchlist():
    try:
        with open(WATCHLIST) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"tracks": {}, "albums": {}}


def is_track(r):
    # ADV-LP-08: keep podcasts and other non-music out of the taste signal.
    uri = r.get("track_uri") or ""
    if r.get("item_type") == "podcast_episode":
        return False
    return uri.startswith("spotify:track:")


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    since = datetime.now(timezone.utc) - timedelta(days=days)
    rows, malformed = load_samples(since)
    music_rows = [r for r in rows if is_track(r)]
    n_excluded = len(rows) - len(music_rows)  # ADV-LP-08: observable filter
    # "active" (playing) drives hit counts and the hour histogram; progress
    # maxima consider paused snapshots too (ADV-LP-10) — a 22-min track
    # paused at 95% still counts toward album completion.
    active = [r for r in music_rows if r.get("playing") and r.get("track_uri")]
    progress_rows = [r for r in music_rows if r.get("track_uri")]

    tracks = defaultdict(lambda: {"hits": 0, "max_pct": 0, "name": "", "artists": []})
    albums = defaultdict(lambda: {"hits": 0, "tracks": set(), "name": "", "week": None, "slot": None})
    hours = Counter()
    watch_hits = []

    for r in progress_rows:
        t = tracks[r["track_uri"]]
        t["max_pct"] = max(t["max_pct"], r.get("progress_pct", 0))
        if t["name"] == "":
            t["name"] = r.get("track")
            t["artists"] = r.get("artists", [])

    for r in active:
        t = tracks[r["track_uri"]]
        t["hits"] += 1
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

    # ADV-LP-10: per-album completion against the watchlist — the unit the
    # course assigns. Edition fallbacks carry their own URIs, so a remaster
    # he actually played still counts toward the assigned album.
    wl = load_watchlist()
    wl_track_count = {}
    for a_uri, a in wl.get("albums", {}).items():
        wl_track_count[(a.get("album"), a.get("week"))] = a.get("track_count") or 0
    album_rows = []
    for key, a in sorted(albums.items(), key=lambda kv: -kv[1]["hits"]):
        track_count = wl_track_count.get((a["name"], a["week"])) or 0
        done = sum(1 for uri in a["tracks"]
                   if tracks[uri]["max_pct"] >= COMPLETION_PCT)
        completion_pct = round(100 * done / track_count, 1) if track_count else None
        album_rows.append({
            "album": a["name"], "week": a["week"], "slot": a["slot"],
            "hits": a["hits"], "distinct_tracks": len(a["tracks"]),
            "watchlist_track_count": track_count or None,
            "completed_tracks": done,
            "completion_pct": completion_pct,
        })

    rollup = {
        "window_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "coverage": COVERAGE_LABEL,  # ADV-LP-03
        "n_samples": len(rows),
        "n_active_samples": len(active),
        "n_excluded_non_music": n_excluded,  # ADV-LP-08
        "n_malformed_lines": malformed,  # ADV-LP-12
        "n_distinct_tracks": len(tracks),
        "n_completed_tracks": completed_tracks,
        "top_tracks": [
            {"track": t["name"], "artists": t["artists"], "hits": t["hits"],
             "max_progress_pct": t["max_pct"]}
            for _, t in sorted(tracks.items(), key=lambda kv: -kv[1]["hits"])[:15]
        ],
        "albums": album_rows,
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
            comp = (f", completion {a['completed_tracks']}/{a['watchlist_track_count']} "
                    f"({a['completion_pct']}%)") if a["completion_pct"] is not None else ""
            print(f"  {a['album']}{tag}: {a['hits']} samples, {a['distinct_tracks']} tracks{comp}")
    if watch_hits:
        print(f"WATCH HITS: {len(watch_hits)} samples on recommended albums")
    if hours:
        top_hours = sorted(hours.items(), key=lambda kv: -kv[1])[:5]
        print("peak hours (PT): " + ", ".join(f"{h}:00 ({c})" for h, c in top_hours))
    if malformed:
        print(f"skipped {malformed} malformed sample lines")
    if n_excluded:
        print(f"excluded {n_excluded} non-music samples (podcasts etc.)")
    # ADV-LP-03: zero hits describe coverage, not taste.
    print(f"coverage: {COVERAGE_LABEL}")
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
