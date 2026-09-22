# long-play features: NL-01 / NL-02 / NL-04 / M1–M11

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

---

## M1 — Grower scheduler (second-chance re-queue)

Research: Madison & Schiölde (2017) — liking rises with repeated exposure.
Albums Wesley "bounced off" are automatically re-queued ~4 weeks later for
ONE scheduled second chance. Only `bounced off` reactions qualify (skips are
not bounces); never re-queued more than once per album — the script refuses.

- State (private): `hidden_files/grower-state.json` — the queue with bounce
  week, due week, requeue flag, and second reaction.
- Helper: `bin/grower.py` (`--scan` picks up new bounces from the log;
  `--due` lists what's due; `--mark-requeued` records the announcement;
  `--record-second` logs the second-chance reaction — a flip to
  played/loved marks a "grower" for the M5 Wrapped).
- Cron: `long-play-grower`, weekly Monday ~08:30 PT, chat-only, silent when
  nothing is due. Announced as a bonus re-listen alongside the week's five
  albums — never a replacement pick.

## M2 — Implicit-feedback taste vector

Skip timing, completion, and replays (sampler data; ≥85% sampled progress
is a completion *proxy*, never ground truth) plus explicit chat reactions
become a per-genre taste vector steering future picks.

- Genre taxonomy: `engine/album_tags.json` (curator pass 2026-09-21, 115/116
  albums tagged; the week-20 LOONA placeholder is untaggable until it's a
  real pick).
- Helper: `bin/taste_vector.py` → `engine/taste-vector.json` (dimensions,
  context modifiers, prediction calibration, pending-data flags).
- Signal weights: explicit reactions full voice (wild card 2×), implicit
  half voice, library saves de-weighted 0.1× weak prior per his standing
  rule (pending until a library snapshot exists), taste-blend overlap
  artists 0.05×.
- Cron: `long-play-taste-vector`, weekly Monday ~06:35 PT, silent-on-success
  (reports only when new dimensions compute).

## M3 — Guided-listening cues

Timed prompts + liner-note drops during the week, wired into the Tue–Fri
drip and the Monday digest.

- Track data: `bin/album_tracks.py` resolves each syllabus album to its
  Spotify tracklist, cached in `engine/tracklists/` — real track titles and
  start offsets, never invented.
- Helper: `bin/build_guided_cues.py` → `engine/guided_cues.json`: per week,
  per album, a `timed` cue (track N + real start time paired with the
  week's curated "Listen for" text; points at a track named in the cue when
  one matches, else the opener) and a `liner` drop (first sentence of the
  album's week-file prose, verbatim). Intra-track moments ("2:14 on track
  4") are NOT generated — they need manual curation (`curated_moment` flag).
- Wiring: `bin/drip_pick.py` attaches the day's `guided_cue` to the pick
  JSON; the drip cron renders it as the 🎧 line. The Monday digest runs
  `build_guided_cues.py --week N` after finalizing the week's listen-for
  cues (weeks 2+ scaffold with a "(set by the digest)" placeholder, so the
  track pointer works before the cue text lands).

## M4 — Pre-listen prediction + blind week

Before the weekly picks, Wesley records his prediction per album
(love / play / bounce); occasionally a blind week runs (no artist, title,
cover, or play links until after he listens).

- State (private): `hidden_files/predictions.json` — predictions, blind
  flags, per-week accuracy once scored.
- Helper: `bin/predictions.py` (`--record`, `--set-blind`, `--score`,
  `--accuracy`). Match rules: love↔loved, play↔played, bounce↔bounced off;
  a skipped album is a half-miss except against a bounce prediction.
- Cron: `long-play-predictions`, weekly Sunday ~19:19 PT, chat-only. Blind
  weeks are proposed for weeks 8/14/20 unless he vetoes; the blind question
  is asked before the picks are shown.
- The Monday digest honors the blind flag (step 1b): albums A–E, no names,
  no play links until feedback arrives.
- Prediction accuracy is the calibration signal for the M2 taste vector.

## M5 — Course Wrapped finale

End-of-24-weeks personal review, one week after week 24 delivers
(2027-03-15 one-shot; the course is still underway at year-end, so this is
separate from the NL-04 year-end reckoning).

- Helper: `bin/course_wrapped.py` — totals, biggest M1 growers, genre map
  of taste movement (explicit reactions, weeks 1–4 vs 21–24), M4 prediction
  accuracy, closing M10 wild-card read. Anything uncomputable is marked
  pending, never invented. `--save` writes the private working copy.
- Cron: `long-play-course-wrapped` (runonce 2027-03-15 ~09:19 PT),
  chat-only, no Feed mirror.

## M6 — Syllabus gap analysis

Audit of the 24-week syllabus by era/genre/region; flags
underrepresentation and suggests rebalancing weeks. Pure analysis — never
edits the syllabus.

- Helper: `bin/syllabus_gap.py` (reads `engine/weeks.json` +
  `engine/album_tags.json`). Report saved to the goal's `files/`
  (`syllabus-gap-analysis.md`).
- Findings (2026-09-21 run): 1980s nearly absent (2 picks), 1990s light for
  the decade of his island albums, zero picks from Africa / Latin America /
  South Asia / Middle East / Oceania, ~US+UK dominance measured; data flags:
  the week-20 LOONA placeholder needs a real pick, and week 17/6 and week
  18/2 conditionally re-use albums (already marked in the syllabus).
- No cron — re-run when the syllabus changes.

## M7 — One-track telegram

Weekly standout track drafted for 1–2 friends. DRAFTING MECHANISM ONLY —
there is no send path in the code, by design; Wesley approves/sends himself.

- Helper: `bin/telegram_draft.py` — standout = strongest logged reaction
  (loved > played, ties → wild card); track = most-completed sampler track
  that month, else the opener from the tracklist cache; the one-line "why"
  is verbatim from the week's Listen-for cue. Drafts append to the private
  `hidden_files/telegram-drafts.md`.
- Recipients: `hidden_files/telegram-recipients.json` — STUBBED until
  Wesley names 1–2 friends. `--log-reaction` records lightweight friend
  reactions later.
- Cron: `long-play-telegram`, weekly Saturday ~18:19 PT, chat-only.

## M8 — Monthly taste-blend

A 10-track shared mix blending his recent listening with a friend's or
artist's playlist. DRAFT ONLY — nothing sent, no playlist created.

- Helper: `bin/taste_blend.py` — his side from the last 4 sampler rollups;
  their side from `hidden_files/taste-blend-source.json`
  (`{type: friend|artist, name, playlist_uri}`) — STUBBED until Wesley
  names a friend's playlist or picks an artist. Overlap artists feed
  `hidden_files/taste-blend-overlap.json`, which the M2 vector reads as a
  weak (0.05×) artist-affinity signal.
- Cron: `long-play-taste-blend`, weekly Saturday ~10:19 PT with a
  first-Saturday-of-month guard in the body, chat-only.

## M9 — Listening-context tags

One-tap tags on feedback: commute / focused / background / late-night.
They feed the M2 taste vector as per-context genre modifiers.

- Collection: the Monday digest's feedback prompt carries the optional tag
  line ("loved tago mago — late-night").
- Helper: `bin/tag_context.py <week> <artist> <album> <context> <reaction>`
  appends to the private `hidden_files/context-tags.jsonl` (with the
  album's genre resolved from `album_tags.json`).
- No separate cron — tags ride the existing feedback flow.

## M10 — Wild-card calibration report

Periodic check on whether the 2× wild-card weight is earned: do wild-card
picks predict taste better than curated slots?

- Helper: `bin/wildcard_calibration.py` — per-slot loved rate, mean
  weighted score, and discomfort signal strength (mean |score|) from
  explicit chat reactions; advisory recommendation only (≥1.5× signal ratio
  → suggest 2.5×; ≤0.8× → suggest 1.5×; else keep 2.0×). Weights are NEVER
  auto-changed — Wesley decides. Needs ≥4 weeks of reactions; before that it
  reports insufficient data honestly.
- State (private): `hidden_files/wildcard-calibration.json`.
- Cron: `long-play-wildcard-calibration`, monthly on the 1st ~09:19 PT,
  chat-only, silent until 4 weeks of data exist.

## M11 — Streaks + finisher rituals

Streak counter for consecutive full-listen weeks + the week-24 graduation
ritual. HARD RULE: never nagging (the finish-the-album nudge was vetoed) —
celebrations fire ONLY for new records (≥3 weeks) or milestones
(4/8/12/16/20/24); routine weeks stay silent.

- Full-listen week: all 5 albums have a logged reaction AND ≥3 are
  played/loved (listening log = ground truth).
- Helper: `bin/streak.py` (`--check`, `--ack-ignored`, `--graduate`).
- Kill switch: after a celebration, the next run checks whether feedback
  was logged for the celebrated week. Two consecutive ignored celebrations
  → reminders disable themselves permanently in
  `hidden_files/streak.json` (`enabled: false`); the cron exits silently
  while disabled. Wesley re-enables by saying so.
- Cron: `long-play-streak`, weekly Sunday ~19:45 PT, chat-only.
- Graduation: the `long-play-course-wrapped` one-shot runs
  `streak.py --graduate` for the week-24 ritual.
