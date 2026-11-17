# Sampler: now-playing listening telemetry

The sampler is long-play's implicit-feedback stream. It watches what actually
gets played and turns it into the album-level signal the engine scores on.

## What it captures

Nine daily Spotify playback snapshots (7–10am, 3–5pm, 7pm and 9pm PT, all days):
track, artists, progress, playing/paused, playback context. From these, the
rollup derives:

- **Album play counts** — via the watchlist (track → album mapping) and
  album-context snapshots. The user–album interaction matrix starts here.
- **Completion proxies** — a track whose max observed progress clears 85%
  counts as completed. Skips and bounces are first-class data: negatives are
  structural, not just down-weights.
- **Recommended-album detection** — samples matching the current week's albums
  are flagged as watch hits. This is the listening-capacity signal: are the
  assignments actually getting played?
- **Time-of-day sessions** — hour-of-day histogram (PT) feeding the CTX scorer:
  commute vs. locked-in work listening matched against album duration profiles.
- **Listening capacity** — per-window absorption of the watched (assigned)
  albums: how many picks got any sampled play (`capacity` section, L12).
  A lower bound — polls are snapshot-only — so it tunes the pick count
  and drip cadence as a floor, never a verdict.

## Files

- `poll.py` — the hourly poll. Calls `spotify-api now-playing`, appends one
  JSON line to the private samples log. Dumb by design; never crashes the cron.
- `build_watchlist.py` — resolves the current week's albums to their track
  URIs (`python3 build_watchlist.py 1`). Re-run when the week changes.
  Search is artist-scoped (`--artist` with a bare-title query — the old
  "{album} by {artist}" query text misdirected the backend and hid
  records). Albums search cannot surface at all are pinned to verified
  URIs in `pinned_albums.json` (currently Ride's Nowhere only; a pin is
  added only after the album's track list is verified via experience).
  Fail-closed: a build that resolves zero albums exits nonzero and leaves
  the existing watchlist untouched, so a transient resolver failure can
  never wipe the working watchlist (and `bin/rollover.py` refuses to
  advance on that failure).
- `rollup.py` — aggregates the trailing N days (`python3 rollup.py 7`):
  per-track and per-album stats, watch hits, peak hours. The 7-day run writes
  the canonical `rollups/YYYY-Www.json`; any other N writes a sidecar
  `rollups/YYYY-Www.Nd.json` so short-window runs never clobber the weekly
  aggregate.

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

Nine daily polls (all days, no weekend exit): 07:19, 08:19, 09:19, 10:19,
15:19, 16:19, 17:19, 19:19, 21:19 PT — each pulls the repo and runs
`poll.py`. One weekly rollup, Monday 06:00 PT.

The poll windows feed the CTX session model (`../reference/ctx-session-model.md`),
which buckets the `hour_of_day_pt` histogram into morning (7–11am),
afternoon (3–6pm), and evening (7–10pm) sessions.

## Listening capacity (L12)

Each rollup's `capacity` section measures watched-album absorption for the
window: albums/tracks touched vs. the watchlist, normalized to a per-week
rate. Touched = at least one sampled track at any progress; started = at
least one track reaching 10% (filters poll-window noise); completed = at
least one track reaching 85%. Polls are snapshot-only, so every number is
a lower bound — the model reads it as a floor for the pick count (currently
5/week) and drip cadence.

Status 2026-11-16 (canonical 7-day rollup W47, run 2026-11-16): 1 of 5 watched albums
touched (ODESZA — A Moment Apart: 3 of 95 watched tracks, 2 started, max progress
79.4%), 0 completed; capacity 1.0/week.
This breaks the sub-1.0 streak — W44, W45, W46 were all 0.0/week — so the capacity
side of the revisit bar below is no longer met and the three-consecutive counter
resets. The W43 read still stands as a caution: 2 of 5 touched at 0.4% max progress
— fleeting starts, not absorption — so read touched-rate alongside started.
Pick count explicitly HELD at 5 — the revisit bar also needs the explicit
feedback log to agree, and it holds no dated rows for weeks 3–8 (the only
explicit reaction on record remains the week-1 bounce-off; the week-8 feedback
prompt went out 2026-11-16 and no reactions are logged yet), so the capacity
read alone is a floor, not a verdict, and the feedback loop is still ramping.
Revisit bar: reduce the pick count only if `capacity_albums_per_week` stays
< 1.0 for three consecutive 7-day rollups AND the explicit feedback log
agrees (skipped/bounced-off rows outnumber played/loved).

## Known limits (v1)

- No recently-played history endpoint in the Spotify CLI, so sampling is
  snapshot-only: anything played between polls is invisible.
- Album attribution depends on the watchlist or album-context playback;
  playlist listening to unwatched albums stays track-level.
- Completion is a proxy (max observed progress), not a true play-through event.
