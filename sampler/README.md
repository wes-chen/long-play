# Sampler: now-playing listening telemetry

The sampler is long-play's implicit-feedback stream. It watches what actually
gets played and turns it into the album-level signal the engine scores on.

## What it captures

Hourly snapshots of Spotify playback on weekdays during the listening windows
(7–10am, 3–5pm PT): track, artists, progress, playing/paused, playback
context. From these, the rollup derives:

- **Album play counts** — via the watchlist (track → album mapping) and
  album-context snapshots. The user–album interaction matrix starts here.
- **Completion proxies** — a track whose max observed progress clears 85%
  counts as completed. Skips and bounces are first-class data: negatives are
  structural, not just down-weights.
- **Recommended-album detection** — samples matching the current week's albums
  are flagged as watch hits. This is the listening-capacity signal: are the
  assignments actually getting played?
- **Time-of-day sessions** — hour-of-day histogram (PT) feeding the CTX scorer:
  commute vs. locked-in work listening matched against album energy/duration.

## Files

- `poll.py` — the hourly poll. Calls `spotify-api now-playing`, appends one
  JSON line to the private samples log. Dumb by design; never crashes the cron.
- `build_watchlist.py` — resolves the current week's albums to their track
  URIs (`python3 build_watchlist.py 1`). Re-run when the week changes.
- `rollup.py` — aggregates the trailing N days (`python3 rollup.py 7`):
  per-track and per-album stats, watch hits, peak hours. Writes to
  `rollups/YYYY-Www.json`.

## Privacy

Raw listening data **never enters this repo**. The poll script writes only to
the private state dir on the VM:

```
~/workspace/goals/album-recommender-music-digest/hidden_files/sampler/
    samples.jsonl    raw snapshots (private)
    watchlist.json   track -> album map for watched weeks (derived from the public syllabus)
    rollups/         weekly aggregates (private)
```

Only code and the public week/album lists are committed here.

## Schedule

Seven daily crons (Mon–Fri effective; weekend runs exit immediately):
07:00, 08:00, 09:00, 10:00, 15:00, 16:00, 17:00 PT — each pulls the repo and
runs `poll.py`. One weekly rollup, Monday 06:00 PT.

## Known limits (v1)

- No recently-played history endpoint in the Spotify CLI, so sampling is
  snapshot-only: anything played between polls is invisible.
- Album attribution depends on the watchlist or album-context playback;
  playlist listening to unwatched albums stays track-level.
- Completion is a proxy (max observed progress), not a true play-through event.
