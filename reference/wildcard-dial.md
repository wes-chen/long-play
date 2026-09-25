# Wild-card adaptive dial (L4)

Research background: exploration saturates — novelty pressure has diminishing,
non-monotonic returns that vary per user (2604.16419), and freshness and
novelty are separate objectives that must be budgeted separately (2607.23749).
So the wild card's reach is not fixed: this dial moves it up and down week to
week based on what the listener actually did.

This is the adaptive half of the wild-card machinery:

- **This dial** controls novelty *reach*: how far from the listener's taste
  poles a wild-card pick may sit. Consumer: the Monday digest worker, when it
  finalizes upcoming weeks.
- `bin/wildcard_calibration.py` (M10) calibrates the *reaction weight*
  (whether the 2× wild-card weight is earned). Different question, different
  consumer.
- `engine/weights.json` NOV slot weight (dormant) is the scoring-layer
  version, for when candidate generation exists.

## Dial levels

| Level | Reach band | Meaning |
|---|---|---|
| D1 | Close | Wild card one hop from an adventurous pick this week (adjacent genre/era, same unit) |
| D2 | Adjacent | Adjacent unit, familiar lineage bridge |
| D3 | Leap *(default)* | Cross-unit leap with a lineage bridge |
| D4 | Far | Cross-unit leap, thin lineage bridge |
| D5 | Unbounded | No bridge required — instructor's choice |

Reach is human-judged against the week file's concept + lineage until album
embeddings exist; then it becomes cosine distance from the taste vector.

## Update rule (evaluated at digest step 0, weekly)

Inputs (both already exist):

- Sampler: per-album completion = distinct watched tracks with max_pct ≥ 85 /
  watchlist track count (see ADV-LP-10).
- Explicit: `listening-log.md` rows — week, album, slot, reaction, weight
  (wild-card reactions carry 2×, see `feedback-schema.md`).

Move at most **±1 per week**. Explicit feedback outranks sampler data on
conflict (same evidence bar as the syllabus revision process).

**Advance (+1, max D5)** if any of:

- wild card "loved" in chat (explicit, weight 2×)
- wild-card per-album completion ≥ 0.85 two consecutive weeks
- two consecutive weeks with all three adventurous picks played (novelty
  appetite demonstrated)

**Retreat (−1, min D1)** if any of:

- wild card "bounced off" in chat (explicit)
- wild-card per-album completion < 0.40 two consecutive weeks
- ≥2 of 3 adventurous picks with completion < 0.40 two weeks running
  (novelty saturation — back off the whole budget, per 2607.23749)

**Saturation floor:** the wild card never disappears — `weights.json` sets a
hard REL floor of 0.25 for the slot regardless of tuning, and the dial floor
is D1, not D0.

**Cold start:** D3 until 2 delivered weeks exist (no move before then); week 1
has no prior data so the dial cannot fire.

## How it changes picks

The 24-week syllabus is pre-assigned, so the dial applies to *future* weeks
through the syllabus revision process (`reference/syllabus-revision-process.md`):
if the next delivered week's wild card sits outside the current reach band,
the digest worker proposes a swap at digest step 0; listener feedback vetoes
as usual. Published week files are never edited.

## Worked example

Week 3 digest: weeks 1–2 logged. Week 1 wild card "loved" (chat), week 2 wild
card completion 0.92 in the sampler. Explicit loved → advance D3→D4. Week 4's
wild card must now sit in the D4 band or the worker proposes a swap.

Week 5 digest: weeks 3–4 wild-card completion 0.31, 0.22; no chat feedback.
Sampler retreat fires two consecutive sub-0.40 weeks → retreat D4→D3.

## Status

Mechanism designed; thresholds are **UNVALIDATED** — calibrate against 3–4
weeks of rollup + listening-log data before treating the 0.85/0.40 cutoffs as
ground truth. Then fold the calibrated numbers into L7's completion-proxy
validation and the L12 capacity model.
