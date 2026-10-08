#!/usr/bin/env python3
"""Weekly rollup of sampler data: album-level listening stats.

Reads the private samples.jsonl, aggregates over the trailing N days, and
writes a rollup JSON + prints a human summary. Feeds the engine's
user-album interaction matrix and the CTX time-of-day model (L5: per-album
session fit is read from engine/ctx_profiles.json and scored against the
hour-of-day histogram bucketed into sessions).

Usage:
    python3 rollup.py [days]     # default 7

The 7-day run writes the canonical rollups/YYYY-Www.json -- the weekly
aggregate the engine and capacity model read. Any other window (e.g.
`rollup.py 1` health checks) writes a sidecar rollups/YYYY-Www.Nd.json
instead, so a short-window run can never clobber the week's aggregate.
"""
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.expanduser(
    "~/workspace/goals/album-recommender-music-digest/hidden_files/sampler"
)
CTX_JSON = os.path.join(REPO, "engine", "ctx_profiles.json")
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


def load_ctx_profiles():
    # L5: the session-fit envelope written by bin/ctx_profiles.py. Missing
    # or malformed -> rollup runs without session fit, never crashes.
    try:
        with open(CTX_JSON) as f:
            env = json.load(f)
        profiles = {((p["week"], p["slot"], (p.get("artist") or "").lower(),
                     (p.get("album") or "").lower())): p
                    for p in env.get("profiles", [])
                    if p.get("week") is not None and p.get("slot")}
        return {
            "sessions": env.get("sessions", {}),
            "fit_table": env.get("fit_table", {}),
            "profiles": profiles,
        }
    except (FileNotFoundError, json.JSONDecodeError):
        return {"sessions": {}, "fit_table": {}, "profiles": {}}


def session_fit_scores(ctx, profile):
    """Fit score per session for one album profile (0-2, clamped).

    Base from the envelope's fit table [session][duration_tier]; the
    energy axis was removed (#28) so there is no modifier term. Returns
    None when the profile has no duration tier.
    """
    tier = profile.get("duration_tier")
    if tier is None:
        return None
    table = ctx["fit_table"]
    out = {}
    for session, tiers in table.items():
        base = tiers.get(tier)
        if base is None:
            continue
        out[session] = round(min(2.0, max(0.0, base)), 2)
    return out or None


def session_shares(ctx, hours):
    """Bucket the hour_of_day histogram into sessions; shares sum to 1.

    Hours outside any session (e.g. 11-14, 22-23) are reported under
    "off_session" and excluded from the shares.
    """
    sess_hours = {}
    for session, hs in ctx.get("sessions", {}).items():
        for h in hs:
            sess_hours[h] = session
    counts = Counter()
    off = 0
    for h, c in hours.items():
        if h in sess_hours:
            counts[sess_hours[h]] += c
        else:
            off += c
    total = sum(counts.values())
    shares = {s: round(c / total, 4) for s, c in counts.items()} if total else {}
    return shares, off


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
            a.update({"name": wh["album"], "artist": wh.get("artist"),
                      "week": wh["week"], "slot": wh["slot"]})
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
        album_max = max((tracks[uri]["max_pct"] for uri in a["tracks"]), default=0)
        artist = a.get("artist") or ""
        album_rows.append({
            # M2 taste vector keys album rows "Artist — Album" and reads
            # tracks / completed_tracks / max_progress_pct / hits.
            "name": f"{artist} — {a['name']}" if artist else a["name"],
            "artist": artist or None,
            "album": a["name"], "week": a["week"], "slot": a["slot"],
            "hits": a["hits"], "tracks": len(a["tracks"]),
            "distinct_tracks": len(a["tracks"]),
            "watchlist_track_count": track_count or None,
            "completed_tracks": done,
            "completion_pct": completion_pct,
            "max_progress_pct": round(album_max, 1),
        })

    # L5: session fit per watched album, from engine/ctx_profiles.json.
    # CTX(album) = sum_session session_share * fit(session, profile), the
    # engine's mild re-rank term; null when the profile has no duration.
    ctx = load_ctx_profiles()
    shares, off_session = session_shares(ctx, hours)
    for row in album_rows:
        prof = (ctx["profiles"].get(
            (row["week"], row["slot"], (row.get("artist") or "").lower(),
             (row["album"] or "").lower()))
            if row["week"] else None)
        fits = session_fit_scores(ctx, prof) if prof else None
        row["session_fit"] = fits
        row["ctx_score"] = (round(sum(shares.get(s, 0) * f for s, f in fits.items()), 3)
                            if fits and shares else None)
        if prof:
            row["duration_tier"] = prof.get("duration_tier")

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
        "session_shares": shares,  # L5: hour histogram bucketed to sessions
        "n_off_session_samples": off_session,  # hours outside any session
        "ctx_consumed": bool(ctx["profiles"]),  # L5: engine/ctx_profiles.json read
        "watch_hits": watch_hits,
        "n_watch_hits": len(watch_hits),
    }

    os.makedirs(ROLLUP_DIR, exist_ok=True)
    stamp = datetime.now(PT).strftime("%Y-W%V")
    # The canonical weekly file belongs to the scheduled 7-day run only.
    # Short windows (e.g. `rollup.py 1` health checks) write a window-suffixed
    # sidecar so they can never clobber the week's aggregate.
    fname = f"{stamp}.json" if days == 7 else f"{stamp}.{days}d.json"
    path = os.path.join(ROLLUP_DIR, fname)
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
    # L5: session <-> album match section — best session per watched album
    # per the spec's matching rule; null profile -> no row, not a guess.
    fitted = [a for a in album_rows if a.get("session_fit")]
    if fitted:
        print("session fit (morning / afternoon / evening, 0-2):")
        for a in fitted:
            f = a["session_fit"]
            best = max(f, key=f.get)
            meta = f"tier={a.get('duration_tier')}"
            ctx_s = f", ctx={a['ctx_score']}" if a["ctx_score"] is not None else ""
            print(f"  {a['album']} [{a['slot']}]: best {best} ({meta}){ctx_s}")
    elif ctx["profiles"]:
        print("session fit: no watched-album hits this window")
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
