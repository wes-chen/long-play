# Cult Scoring Rubric — long-play weeks 1–12

Companion to `/tmp/cult_weeks01-12.json` (60 entries, one per syllabus slot,
weeks 1–12, `calibration: "unvalidated"` on every entry).

## Formula (exact)

```
cult_score_0_1 = round(0.4*canon + 0.35*lists + 0.25*reception, 2)
lists          = min(1.0, log10(1 + list_count) / 2)
```

- `canon`: 1.0 / 0.5 / 0.0 (see tiers below)
- `list_count`: number of **verified** notable year-end or all-time list
  appearances, each named in the entry's `evidence`. Aggregator roll-ups
  (BestEverAlbums) are counted but flagged as aggregators; mid-year lists are
  never counted; a claim found only on a retailer blurb or forum post is not
  counted.
- `reception`: normalized 0–1 critical score.
  - 0–100 aggregates (Metacritic, Album of the Year): score / 100.
  - Pitchfork-style /10 scores: score / 10.
  - AllMusic star ratings (where used): 5→1.0, 4.5→0.9, 4→0.8, 3.5→0.7.
  - **0.5 with `confidence: "low"`** when no verifiable reception data was
    available in this pass.

## Canon tiers

- `canon = 1.0` — **major canon membership**, any of:
  - a 33⅓ book volume dedicated to the album,
  - Rolling Stone 500 placement (any edition; edition noted in evidence),
  - Acclaimed Music all-time top tier,
  - Grammy Hall of Fame induction,
  - National Recording Registry selection.
- `canon = 0.5` — **artist-canonical** (the act's defining statement) or
  **strong genre-canon presence** (e.g., top placements on reputable
  all-time genre lists: Pitchfork's genre lists, Prog Magazine UK top 100,
  Julian Cope's Krautrock Top 50).
- `canon = 0.0` — neither. Underground cult status alone does not earn 0.5.

## Confidence meanings

- `high`: list appearances and reception verified from named sources this
  pass; canon tier supported by a major-canon fact or multiple genre lists.
- `medium`: canon tier is well-established reference knowledge (e.g.,
  AllMusic star ratings) but was not re-verified in this pass, or one
  evidence pillar is thinner than ideal.
- `low`: evidence is thin — typically `list_count = 0` and/or
  `reception = 0.5` (neutral default). Scores are conservative by design;
  **no list appearance is ever invented to fill a gap.**

## Sources consulted (2026-09-26)

- Rolling Stone 500 (2020): via acclaimedmusic.net forum mirror and
  MusicBrainz RS 2020 series pages.
- 33⅓ series list: en.wikipedia.org/wiki/33_1/3.
- Grammy Hall of Fame (A–D): Wikipedia list (Abbey Road, inducted 1995).
- National Recording Registry: Library of Congress selections — Kind of Blue
  (2002); Bitches Brew (2025, via jambands.com report).
- Pitchfork year-end lists via albumoftheyear.org and yearendlists.com:
  2014 (#6 To Be Kind), 2015 (#1 To Pimp a Butterfly, #2 In Colour),
  2016 (#1 A Seat at the Table, #2 Blonde), 2018 (#18 Oil of Every Pearl's),
  2019 (#42 1000 gecs), 2020 (#41 KiCk i), 2022 (#21 A Light for Attracting
  Attention); Pitchfork 2010s decade list; Pitchfork 2010–14 retrospective;
  Pitchfork 50 Best Ambient Albums of All Time (2016) (#18 ATRotD);
  Pitchfork best progressive rock albums all-time (AOTY mirror).
- Pitchfork perfect-score database (AOTY): 10/10s for Kid A, OK Computer,
  Homogenic, Laughing Stock, Heaven or Las Vegas.
- AOTY critic aggregates: To Pimp a Butterfly 95 (47 reviews), To Be Kind 88
  (38), In Colour 83 (46), SOS critic-lists page, MAGDALENE 94 (2019),
  A Light for Attracting Attention reviews page, 100 Gecs page.
- Metacritic: A Light for Attracting Attention 86; And Their Refinement of
  the Decline 87 (Wikipedia reception tables).
- AnyDecentMusic: A Light for Attracting Attention 8.3; Oil of Every Pearl's
  8.2.
- Wikipedia accolades tables: 1000 Gecs (Pitchfork, Rolling Stone, NYT,
  Noisey, Paper, Stereogum, Crack, PopMatters 2019 lists), A Light for
  Attracting Attention (Rolling Stone, Pitchfork, Consequence, BrooklynVegan,
  Paste, Uncut #1, Rough Trade US #1/UK #2).
- Prog all-time lists: Prog Magazine UK Top 100 (Louder), Rolling Stone 50
  Greatest Prog Rock (2015, via Acclaimed forums), uDiscover Music 50 Greatest
  Prog (2021), AllMusic Best Progressive Rock (AOTY mirror).
- Krautrock: Far Out Magazine 10 best krautrock (#1 Tago Mago), Julian Cope's
  Krautrock Top 50 (reproduced in search), Discogs essential krautrock digs,
  LiveAbout top 10 krautrock.
- BestEverAlbums aggregate accolades (flagged as aggregators in evidence):
  Hellfire (2022 #5), Preacher's Daughter (2022 #23).
- Retail/record-store notes used only for non-list facts: Elusive Disc
  (Smile 2022 list roundup), Crash Records/Banquet/Vinilo (Preacher's
  Daughter cult following, May 2022 acclaim), Midheaven/Hi-Voltage/Deejay
  (ATRotD Pitchfork 8.6 quotes).

## Notes and known limitations

- The week 1 and week 3 Pink Floyd `Animals` entries are duplicates by
  syllabus design and score identically (0.50).
- Reception values drawn from standard reference knowledge (e.g., AllMusic
  star ratings for classic albums) are marked `confidence: "medium"` where
  they were not re-verified in this pass.
- Thirteen entries are `confidence: "low"` — overwhelmingly the electronic,
  underground, and jazz-fusion deep cuts where no notable list appearances
  could be verified. Their scores sit at the formula floor (0.12–0.48) rather
  than being inflated.
- `list_count` counts distinct publications/editions; the same publication's
  year-end and decade lists count separately when both are verified.

## Revalidation procedure

1. For each entry, re-check `list_count` against the named evidence sources;
   only keep appearances that resolve to a real published list.
2. Recompute `lists = min(1.0, log10(1 + list_count)/2)` and
   `cult_score_0_1 = round(0.4*canon + 0.35*lists + 0.25*reception, 2)`.
3. Re-derive `canon` from current major-canon facts (RS 500 editions change;
   new 33⅓ volumes, HOF inductions, and NRR selections accrue).
4. Replace `reception = 0.5` placeholders with a verified aggregate where one
   exists (AOTY critic score preferred), adjusting `confidence` upward.
5. On any change, set `calibration` to a dated validation tag
   (e.g., `"validated-2026-10"`) instead of `"unvalidated"`.
6. Re-run `python3 -m json.tool` on the JSON and the build-script assertions
   (unique (week, slot, artist, album); enum bounds; 2–5 evidence strings;
   exact week/slot/artist/album match against `engine/weeks.json`).
