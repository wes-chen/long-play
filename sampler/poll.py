#!/usr/bin/env python3
"""long-play now-playing sampler: hourly poll.

Captures one playback snapshot per run and appends it to the private
samples log (JSONL). Dumb by design — all aggregation lives in rollup.py.

State (private, never committed):
    ~/workspace/goals/album-recommender-music-digest/hidden_files/sampler/
        samples.jsonl      raw poll log
        watchlist.json     track URI -> {album, artist, week, slot, track}
        reported_hits.json albums already announced to chat today (ADV-LP-05)
        health.json        consecutive spotify-api failure counter (ADV-LP-11)
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOG_DIR = os.path.expanduser(
    "~/workspace/goals/album-recommender-music-digest/hidden_files/sampler"
)
LOG_FILE = os.path.join(LOG_DIR, "samples.jsonl")
WATCHLIST = os.path.join(LOG_DIR, "watchlist.json")
REPORTED_HITS = os.path.join(LOG_DIR, "reported_hits.json")
HEALTH = os.path.join(LOG_DIR, "health.json")
PT = ZoneInfo("America/Los_Angeles")

# ADV-LP-04: strips edition/remaster tags for name-normalized matching, so a
# track from the 2011 remaster still tags against a watchlist built on the
# 2016 remaster's URIs.
_EDITION_RE = re.compile(
    r"\s*[\(\[][^\)\]]*(remaster|remix|deluxe|anniversary|expanded|bonus|"
    r"live|mono|stereo|edition|version|master)[^\)\]]*[\)\]]", re.I)
# unbracketed trailing edition tags, e.g. "Money - 2011 Remaster"
_EDITION_TAIL_RE = re.compile(
    r"\s*[-––:]\s*(\d{4}\s+)?(remaster|remix|deluxe|anniversary|expanded|"
    r"bonus|live|mono|stereo|edition|version|master).*$", re.I)


def norm_name(s):
    s = _EDITION_RE.sub("", s or "")
    s = _EDITION_TAIL_RE.sub("", s)
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def now_playing():
    try:
        out = subprocess.run(
            ["spotify-api", "now-playing"],
            capture_output=True, text=True, timeout=30,
        )
        return json.loads(out.stdout)
    except Exception as e:  # noqa: BLE001 - poll must never crash the cron
        return {"ok": False, "error": f"poll failed: {e}"}


def load_watchlist():
    try:
        with open(WATCHLIST) as f:
            return json.load(f)
    except FileNotFoundError:
        return {"tracks": {}, "albums": {}}


def already_reported_today(album):
    """ADV-LP-05: one WATCH HIT chat line per album per day, max."""
    try:
        with open(REPORTED_HITS) as f:
            rep = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        rep = {}
    today = datetime.now(PT).strftime("%Y-%m-%d")
    return rep.get(today, {}).get(album, False)


def mark_reported_today(album):
    try:
        with open(REPORTED_HITS) as f:
            rep = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        rep = {}
    today = datetime.now(PT).strftime("%Y-%m-%d")
    rep.setdefault(today, {})[album] = True
    # keep a week of history, no more
    for day in sorted(rep)[:-7]:
        del rep[day]
    with open(REPORTED_HITS, "w") as f:
        json.dump(rep, f)


def health_streak():
    try:
        with open(HEALTH) as f:
            return int(json.load(f).get("consecutive_failures", 0))
    except (FileNotFoundError, json.JSONDecodeError, ValueError, TypeError):
        return 0


def set_health_streak(n):
    with open(HEALTH, "w") as f:
        json.dump({"consecutive_failures": n}, f)


def main():
    os.makedirs(LOG_DIR, exist_ok=True)
    data = now_playing()
    sample = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "ok": bool(data.get("ok")),
    }
    item = data.get("item") or {}
    if not sample["ok"]:
        # ADV-LP-11: consecutive-failure counter. Report the token problem
        # ONCE when the streak hits 3; stay silent until recovery so seven
        # daily polls don't produce seven identical errors.
        streak = health_streak() + 1
        set_health_streak(streak)
        sample["error"] = data.get("error", "unknown spotify-api error")
        sample["failure_streak"] = streak
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(sample) + "\n")
        if streak == 3:
            print(f"SAMPLER AUTH ALERT: spotify-api has failed {streak} polls "
                  f"in a row — likely an expired token. Last error: "
                  f"{sample['error']}")
        # streak < 3: silent (transient); streak > 3: silent until recovery
        return 0
    if health_streak() >= 3:
        print(f"sampler recovered: spotify-api ok after {health_streak()} "
              f"consecutive failures")
    set_health_streak(0)

    if not item:
        sample["note"] = "no playback item"
    else:
        artists = [c.get("name") for c in data.get("creators", []) if c.get("name")]
        ctx = data.get("context") or {}
        duration = item.get("duration_ms") or 0
        progress = data.get("progress_ms") or 0
        item_uri = item.get("uri") or ""
        # ADV-LP-08: record content type so rollup can exclude podcasts and
        # other non-music from the taste signal.
        item_type = ("podcast_episode" if item_uri.startswith("spotify:episode:")
                     else "track")
        sample.update({
            "track": item.get("name"),
            "track_uri": item_uri,
            "item_type": item_type,
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

        wl = load_watchlist()
        hit = None
        if item_type == "track":
            hit = wl.get("tracks", {}).get(item_uri)
            if not hit:
                # ADV-LP-04: name-normalized fallback for edition URI
                # mismatches (he plays the 2011 remaster; the watchlist was
                # built from the 2016 one). Flagged so the loop knows the
                # attribution is approximate.
                for t_uri, entry in wl.get("tracks", {}).items():
                    if (norm_name(entry.get("track")) == norm_name(item.get("name"))
                            and norm_name(entry.get("artist")) in
                            {norm_name(a) for a in artists}):
                        hit = dict(entry)
                        hit["edition_mismatch"] = True
                        break
            if hit:
                sample["watch_hit"] = hit

    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(sample) + "\n")

    # one-line summary for the cron worker
    wh = sample.get("watch_hit")
    if wh and item and sample["ok"]:
        if already_reported_today(wh["album"]):
            # ADV-LP-05: already announced today — stay silent.
            pass
        else:
            mark_reported_today(wh["album"])
            state = "playing" if sample.get("playing") else "paused"
            tag = " [edition-mismatch]" if wh.get("edition_mismatch") else ""
            print(f"WATCH HIT [{state}]: {sample['track']} — {wh['album']} "
                  f"(week {wh['week']}, {wh['slot']}){tag}")
    elif item and sample["ok"]:
        state = "playing" if sample.get("playing") else sample.get("playback_status", "?").lower()
        print(f"sampled: {sample['track']} — {', '.join(sample['artists'])} [{state}]")
    else:
        print(sample.get("note") or sample.get("error") or "no playback")
    return 0


if __name__ == "__main__":
    sys.exit(main())
