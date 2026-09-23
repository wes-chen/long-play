# CTX session model (L5)

Matches syllabus albums to listening sessions, so the week isn't just five
albums — it's five albums in a sensible order. CTX is the session-fit term
in `score = w_rel·REL + w_nov·NOV + w_fresh·FRESH + w_div·DIV + w_cult·CULT +
w_ctx·CTX` (see `reference/engine.md`).

## Sessions

Derived from the sampler's poll coverage windows (daily, all days):
07:19, 08:19, 09:19, 10:19, 15:19, 16:19, 17:19, 19:19, 21:19 PT.

Three sessions, by hour of poll:

| session     | hours (PT)     | character (v0 hypothesis)                       |
|-------------|----------------|-------------------------------------------------|
| morning     | 07:00–10:59    | short window before the day starts — get in, get out |
| afternoon   | 15:00–17:59    | tail of the work block — medium engagement      |
| evening     | 19:00–21:59    | unwinding — the deep-listening window           |

These are *coverage* windows, not observed listening. The observed pattern
comes from the rollup's `hour_of_day_pt` histogram bucketed into these
three sessions; `bin/ctx_profiles.py --sessions` will print the shares once
data accrues.

## Album profile: two axes

**duration_tier** — derived, never hand-set. `bin/ctx_profiles.py` sums
`duration_ms` across the album's `engine/tracklists/*.json`:

| tier   | minutes | reading                                   |
|--------|---------|-------------------------------------------|
| short  | < 40    | one commute leg, one errand run           |
| medium | 40–60   | the standard album sitting                |
| long   | 60–80   | needs a protected block                   |
| epic   | > 80    | an evening commitment, or two sessions    |

**energy_tier** — manual: `low` / `medium` / high`. Recorded in
`engine/album_tags.json` as `"energy": "low"`, set by the digest worker at
week-file build time using the rubric below. No guessing: an absent energy
tag means the worker hasn't verified the album, and CTX scores on duration
only. Absent ≠ low.

**Energy rubric** (sensory, genre-agnostic):

- **low** — sits still. Ambient, drone, solo piano, hushed folk. The room can
  stay quiet; nothing startles.
- **medium** — moves. Most pop, rock, jazz, funk, R&B. Has pulse, doesn't
  demand full attention.
- **high** — demands. Distortion walls, double-kick, club systems, free-jazz
  blowouts, anything mixed to be felt physically.

**Metadata-source decision (record).** Spotify's `/audio-features` and
`/audio-analysis` endpoints are removed for new apps since the November
2024 Web API change — no programmatic energy/danceability/tempo source
exists, and the connected `spotify-api` CLI exposes no audio-features
command either. So: duration is derived from our own tracklists
(deterministic, refresh-free); energy is a human tag with a fixed rubric.
This is a deliberate trade — a consistent human tier beats a dead API.

## v0 matching table (heuristic, UNVALIDATED)

Fit scores 0–2. Session × duration_tier, with an energy modifier applied
after: energy high → +0.5 in morning, −0.5 in evening; energy low → +0.5 in
evening, −0.5 in morning; medium → no change. Clamp to 0–2.

| session   | short | medium | long | epic |
|-----------|-------|--------|------|------|
| morning   | 2     | 1.5    | 0.75 | 0.25 |
| afternoon | 1.5   | 2      | 1    | 0.5  |
| evening   | 1     | 1.5    | 2    | 1.75 |

Read: mornings fit short, punchy records; afternoons fit standard albums;
evenings fit long-form records that reward a protected block. The table is
a hypothesis, flagged the same way as the v1 CULT scores — replace it with
fitted per-session completion rates once 3–4 weeks of per-album sampler
completion data exist (see "Calibration" below).

## How CTX enters the product

The Monday digest assigns five albums to one week, not to sessions — so CTX
does not gate picks. Its v1 consumers:

1. **The digest's "how to sequence this week" line** — one sentence telling
   the listener which album to start the week with (morning-fit) and which
   to save for a long evening (long/low fit).
2. **The Tue–Fri drip** (08:19, morning window) — when two albums are
   otherwise tied, spotlight the morning-fit one first.
3. **The future engine** — `CTX(album) = Σ_session session_share ·
   fit(session, duration_tier, energy_tier)`, weighted by `w_ctx` per slot
   (`reference/engine.md` slot table). A mild re-rank term, never a veto:
   with five albums a week the sample is too small to overfit.

## Calibration (when the data exists)

Once the sampler has 3–4 weeks of per-album completion proxies
(`rollup.py` album-level completion) plus explicit played/skipped feedback:
for each (session, duration_tier, energy_tier) cell, compute the completion
rate and replace the v0 table. If a cell has < 5 album-weeks of evidence,
keep the heuristic for that cell. Explicit feedback outranks sampler data
when they disagree.

## Anti-overfit note

Five albums a week is ~20 album-weeks a month. CTX is a tiebreaker with a
small weight, not a scheduler. If the fitted table ever starts
micro-managing ("Tuesdays are only for 43-minute medium-energy records"),
that's a bug in the weighting, not a discovery.
