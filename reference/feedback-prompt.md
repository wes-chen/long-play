# Monday-digest feedback block (L8)

The exact feedback block the Monday digest appends, and how chat replies
to it parse into `listening-log.md` rows per `reference/feedback-schema.md`.
Design-only until the digest builder exists; the builder consumes this
spec when it is built.

## Exact block wording

The digest ends with this block, with `<WEEK>` and the five album lines
filled from the delivered week file (file order: anchor, adventurous ×3,
wild card):

```
---
How was week <WEEK>? One line per album — played / skipped / loved / bounced off:

- Anchor — <artist>, <album>:
- Adventurous — <artist>, <album>:
- Adventurous — <artist>, <album>:
- Adventurous — <artist>, <album>:
- Wild card — <artist>, <album>:

Anything else you want me to know goes on its own line after these five.
```

The reaction vocabulary is fixed to the four words — no stars, no scores.
The slot label on each line is load-bearing: it is how the parser assigns
the slot field without re-resolving.

## How a reply parses into log rows

Reactions arrive in chat (source = `chat`; sampler data is implicit and
never a reaction). The parser:

1. Splits the reply into lines. A line is a reaction line if it contains
   one of the four reaction words (case-insensitive; "bounced off" is two
   words). Lines without a reaction word are ignored.
2. Matches the album: normalized title (and artist) substring against the
   current week's five picks. "The Smile" resolves against the week file
   the way feedback-schema.md already requires — resolve ambiguity there,
   never guess, and drop lines that match nothing.
3. Reaction = the matched keyword. Extra text on the line after the
   keyword becomes a free-text note, joined as `reaction; note` (same
   shape as the schema's `bounced off; checked out during Halleluwah`).
   Common shapes: `loved: Tago Mago`, `Tago Mago — loved`,
   `skipped the smile — too sleepy`.
4. One row per album per reply. If a reply reacts to the same album
   twice, the last occurrence wins.
5. Writes each row to `listening-log.md` under the current week's section
   in the same turn the reply arrives (never left in chat history).

Field mapping per row:

| field    | value                                                                 |
|----------|-------------------------------------------------------------------------|
| week     | current syllabus week, zero-padded (`01`)                                |
| album    | album title                                                              |
| artist   | artist name                                                              |
| slot     | `anchor` / `adventurous` / `wild card` (schema spelling — space, no s)    |
| reaction | `played` / `skipped` / `loved` / `bounced off`, plus `; note` if present  |
| source   | `chat`                                                                   |
| weight   | `1.0`, or `2.0` when slot is `wild card` (see below)                      |
| ts       | date the reaction was logged (`YYYY-MM-DD`)                               |

Worked example (illustrative, not real feedback) — week 01 reply:

```
loved the dark side of the moon
animals — played
skipped a light for attracting attention; never found the hook
beautiful rewind — bounced off
tago mago — loved
```

parses to five rows, week `01`, source `chat`, the first four weight
`1.0`, and the Tago Mago row weight `2.0` (wild-card slot) with reaction
`loved`.

## The 2× wild-card weight

The weight applies to **every** reaction on a wild-card-slot album —
played, skipped, loved, or bounced off. Discomfort is the most informative
signal, but a loved wild card is equally strong evidence about range, so
the doubling is slot-based, not reaction-based.

Application rules:

- Applied **at write time** in the log row's `weight` field (`2.0` vs
  `1.0`). Consumers (taste vector, wild-card dial, CTX calibration) treat
  the stored weight as the multiplier — they do not re-derive it from the
  slot, so the log is the single source of truth for the doubling.
- Never applied to sampler data: `source` is always `chat` for weighted
  rows; implicit listening never carries a reaction weight.
- Never applied retroactively: if a week file's slot assignments are later
  revised, rows already written keep the weight they were logged with.

## Done-when

The digest builder (built separately) renders the block above verbatim and
hands replies to the parser in §"How a reply parses into log rows". Until
then this issue stays open.
