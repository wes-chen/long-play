#!/usr/bin/env python3
"""long-play now-playing sampler: hourly poll.

Captures one playback snapshot per run and appends it to the private
samples log (JSONL). Dumb by design — all aggregation lives in rollup.py.

State (private, never committed):
    ~/workspace/goals/album-recommender-music-digest/hidden_files/sampler/
        samples.jsonl    raw poll log
        watchlist.json   track URI -> {album, artist, week, slot}
        rollups/         weekly aggregation output
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

LOG_DIR = os.path.expanduser(
    "~/workspace/goals/album-recommender-music-digest/hidden_files/sampler"
)
LOG_FILE = os.path.join(LOG_DIR, "samples.jsonl")
WATCHLIST = os.path.join(LOG_DIR, "watchlist.json")


def now_playing():
    try:
        out = subprocess.run(
            ["spotify-api", "now-playing"],
            capture_output=True, text=True, timeout=30,
        )
        return json.loads(out.stdout)
    except Exception as e:  # noqa: BLE001 - poll must never crash the cron
        return {"ok": False, "error": f"poll failed: {e}"}


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    data = now_playing()
    sample = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ok": bool(data.get("ok")),
    }
    item = data.get("item") or {}
    if not sample["ok"]:
        sample["error"] = data.get("error", "unknown spotify-api error")
    elif not item:
        sample["note"] = "no playback item"
    else:
        artists = [c.get("name") for c in data.get("creators", []) if c.get("name")]
        ctx = data.get("context") or {}
        duration = item.get("duration_ms") or 0
        progress = data.get("progress_ms") or 0
        sample.update({
            "track": item.get("name"),
            "track_uri": item.get("uri"),
            "artists": artists,
            "duration_ms": duration,
            "progress_ms": progress,
            "progress_pct": round(100 * progress / duration, 1) if duration else 0,
            "playing": data.get("playback_status") == "PLAYING",
            "playback_status": data.get("playback_status"),
            "context_name": ctx.get("name"),
            "context_uri": ctx.get("uri"),
        })
        ctx_uri = ctx.get("uri") or ""
        if ctx_uri.startswith("spotify:album:"):
            sample["album_context_uri"] = ctx_uri
            sample["album_context_name"] = ctx.get("name")
        try:
            with open(WATCHLIST) as f:
                wl = json.load(f)
            hit = wl.get("tracks", {}).get(item.get("uri"))
            if hit:
                sample["watch_hit"] = hit
        except FileNotFoundError:
            pass

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(sample) + "\n")

    # one-line summary for the cron worker
    if sample.get("watch_hit"):
        wh = sample["watch_hit"]
        state = "playing" if sample.get("playing") else "paused"
        print(f"WATCH HIT [{state}]: {sample['track']} — {wh['album']} "
              f"(week {wh['week']}, {wh['slot']})")
    elif item and sample["ok"]:
        state = "playing" if sample.get("playing") else sample.get("playback_status", "?").lower()
        print(f"sampled: {sample['track']} — {', '.join(sample['artists'])} [{state}]")
    else:
        print(sample.get("note") or sample.get("error") or "no playback")


if __name__ == "__main__":
    sys.exit(main())
