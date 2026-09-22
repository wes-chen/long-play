# long-play features: NL-01 / NL-02 / NL-04

Built 2026-09-21. Each feature is a cron job plus (where noted) a helper in
`bin/`. Cron bodies live in the scheduler; this doc describes the design so
the repo stays the source of truth for *what the machine does*.

## NL-01 — Album-of-the-day drip (Tue–Fri)

The Monday digest drops five albums, then silence until next week. The drip
is a short midweek nudge: one chat message per day, Tuesday through Friday,
each spotlighting one of the current week's five albums with its listen-for
cue.

- Rotation: the five album sections appear in week-file order; the album at
  index `(week_number - 1) % 5` sits out that week (the anchor is known
  ground, so it sits out week 1). The remaining four map Tue → Fri in order.
  Every album gets a drip over any five-week span.
- Spotlight week = the highest delivered week in
  `~/workspace/goals/album-recommender-music-digest/hidden_files/digest-delivered.json`.
  Before the first digest delivers, the drip stays silent (no pre-empting
  the picks).
- Dedup: `hidden_files/drip-sent.json` records one spotlight per date; a
  rerun the same day stays silent.
- Never alters the week's picks — read-only on `weeks/week-NN.md`.
- Helper: `bin/drip_pick.py` (prints the pick as JSON, or
  `{"silent": reason}`; `--mark-sent` records the watermark).

## NL-02 — Concert proximity alert (weekly)

A Sunday scan: for artists in the syllabus, check tour announcements for
Bay Area shows (San Francisco, San Jose, Oakland, Berkeley, Mountain View
and surrounds). On a new show: alert with date, venue, and a ticket link.
Silent when nothing new.

- Artist universe = `bin/eligible_artists.py` output: unique artists from
  `engine/weeks.json` for **delivered weeks only**. Future, unreleased
  weeks are excluded — the alert must never spoil upcoming picks.
- Dedup: `hidden_files/concert-seen.json` — one alert per show, ever.
- Verification bar: the date must be in the future and the venue Bay Area;
  source from the artist, the venue, or a ticket seller — not a rumor.

## NL-04 — Year-end reckoning (one-shot, mid-December)

A season-finale report card, executed once in December after the major
year-end lists publish: collect the consensus 2026 lists, compare them
against the delivered syllabus weeks and the listener's logged feedback,
and deliver the verdict — which canon picks landed, which consensus
darlings the syllabus missed, and what the pattern says about the taste
model. Notes that the 24-week arc is still in progress. Chat delivery plus
a Feed mirror, same as the Monday digest.
