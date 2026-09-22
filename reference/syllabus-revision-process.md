# Syllabus living-doc process

The syllabus (`syllabus.md`) is a living document: it moves as the listening
log shows what lands and what bounces. This file defines **who** revises it,
**what triggers** a revision, and **how** revisions are recorded — so the
adaptation is evidence-driven and reversible, never ad-hoc.

## Roles

- **Proposer:** the Monday digest worker. It reads the newest rollup plus
  `listening-log.md` (feedback schema: `reference/feedback-schema.md`) and,
  when a trigger below fires, drafts the revision with its evidence.
- **Committer:** the daily improve loop. Applies the draft, records it in the
  changelog, and pushes via `bin/push_to_github.py`. Small, reversible diffs
  only; weeks are swapped whole, never half-edited.
- **Veto:** the listener. Any chat message like "keep *<album>*" overrides a
  pending or applied revision for that album — no justification required. A
  veto is logged as evidence (it is strong taste signal, not an exception).

## Scope: future weeks only

- A **published** week — any `weeks/week-NN.md` where N is in the delivered
  marker (`hidden_files/digest-delivered.json`) or equals the CURRENT week —
  is the assignment of record and is **never edited**.
- Revisions apply only to **undelivered future weeks**. `syllabus.md` and
  `engine/weeks.json` must be updated in the **same commit** (the rollover
  rebuilds `build_watchlist.py` input from `engine/weeks.json`; a split
  leaves the syllabus and the watchlist disagreeing).
- Tracklist files (`engine/tracklists/`) for swapped-in albums must exist
  before the commit; guided cues (`engine/guided_cues.json`) are refreshed by
  `bin/build_guided_cues.py --week <N>` after the swap.
- Concert-alert and drip helpers read delivered weeks only, so swapping a
  future week can never spoil an upcoming pick.

## Triggers

Every trigger requires **evidence** (listening-log rows by week/album/reaction
plus rollup per-album completion) and the **minimum data** bar. Sampler data
alone never triggers a revision: zero watch hits do not mean skipped
(coverage is snapshot-based), and explicit chat feedback outranks it.
A single skip is noise. No T1–T4 trigger fires before **2 delivered weeks**
(week 1 is calibration, not evidence).

- **T1 — wild-card bounce streak.** Two consecutive bounced wild cards →
  swap the remaining wild-card picks in that unit for less extreme
  alternatives. The Kraftwerk law still holds: the new wild card gets its
  story first.
- **T2 — adventurous skip cluster.** Two or more adventurous picks skipped in
  one week with sampler per-album completion under 25% → replace one pick
  with a closer-adjacent reading. Until the embedding stage exists, the
  replacement is curator judgment with the rationale written into the
  changelog entry.
- **T3 — anchor miss.** An anchor explicitly skipped or under 50% completed →
  re-sequence: move that unit's concept later in the course rather than
  pushing harder. Flagged for the syllabus owner in the changelog entry.
- **T4 — unit wipe.** Zero of four non-wild-card picks loved or played across
  a unit → insert a bridge week (an adjacent unit's reading) before the unit
  continues.
- **T5 — concept check-in miss.** The ~4-week "can you hear X now?" check-in
  misses a concept → re-teach that concept in a new context later in the
  course (spaced repetition), never by repeating the same listen-for cue.
- **T6 — glossary friction.** A glossary term repeatedly asked about or
  misused in feedback → mark it "needs re-teaching" and give it a glossary
  slot in a future write-up.

## Changelog

Append-only `## Syllabus changelog` section at the end of `syllabus.md`.
One terse entry per revision:

```
- 2026-10-12 — weeks 5–6 — evidence: week-03/04 wild cards bounced (log) + <25%
  completion (rollup 2026-W41) — swapped week 6 wild card: Black Midi —
  Hellfire → Talk Talk — Laughing Stock (tamer doorway) — run: improve-loop.
```

Each entry names: date, weeks affected, the evidence (log rows + rollup id),
the change, and the run that made it. The header line in `syllabus.md` ("Draft
vX") bumps minor version on each revision.

## Relation to the other adaptive machinery

- The wild-card **adaptive dial** (`bin/wildcard_calibration.py`, L4) sets
  *intensity* (how far out the wild card reaches); this process sets
  *content* (which albums occupy the slots). A dial report is advisory;
  a trigger here is an action.
- `engine/weights.json` is dormant until candidate generation is built
  (ADV-LP-15) — revision outcomes do not touch it.
- Year-end reckoning (NL-04) re-audits the syllabus against critical
  consensus; it proposes revisions through this same process, not around it.
