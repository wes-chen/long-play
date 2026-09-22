# long-play feedback record schema (ADV-LP-09)

Wesley's chat reactions to the Monday digest ("loved tago mago, skipped the
smile") are explicit ground truth for the adaptive loop. They must be
written to `~/workspace/goals/album-recommender-music-digest/listening-log.md`
in the same turn they arrive — never left to live only in chat history.

## Record schema

One row per album per reaction, appended under the current week's log
section:

| field | meaning |
|---|---|
| week | syllabus week number, e.g. `01` |
| album | album title |
| artist | artist name |
| slot | `anchor` / `adventurous` / `wild card` |
| reaction | one of `played` / `skipped` / `loved` / `bounced off`, plus an optional free-text note after a `;` |
| source | `chat` (digest reply), `sampler` never — sampler data is implicit, not a reaction |
| weight | `1.0`; `2.0` for wild-card reactions ("wild card counts double" — discomfort is the most informative signal) |
| ts | ISO date the reaction was logged |

Example row:

`| 01 | Tago Mago | Can | wild card | bounced off; checked out during Halleluwah | chat | 2.0 | 2026-09-29 |`

## Convention (parent agent)

When Wesley answers the digest feedback prompt in chat — one line per
album, played / skipped / loved / bounced off — append one structured row
per album to the listening log in the same turn, using this schema. Do not
rely on noticing it later. If a reaction mentions an album ambiguously
("the smile"), resolve it against the current week's picks before writing.
