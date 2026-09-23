# Engine: recommendation design

_Opinionated engine design, synthesized from industry engineering blogs (Spotify, Deezer, Pandora, YouTube, ByteDance) and arXiv 2022–2026 papers on music recommendation — not a literature review._

## 1. What production systems actually weigh (ranked)

1. **Implicit interaction embeddings.** Spotify factors a user×song matrix of streams,
saves, and playlist adds into taste vectors; Deezer's whole stack is CF embedding
spaces where dot-product proximity = preference. *Everything else is augmentation or
fallback — the backbone is always user–item interaction geometry.*
2. **Item–item co-occurrence.** Spotify's Discover Weekly logic ("people who playlist A
and C together also play B"); Deezer's Transformer trained on playlist sequences beat
its CF baseline for new users. *The most reliable similarity signal that needs no user
profile.*
3. **Audio content embeddings.** Spotify trains CNNs on mel-spectrograms to *predict a
song's CF latent factors* — placing unheard tracks in the same space as warm ones.
*Not the primary ranker anywhere; the universal cold-start and long-tail fallback.*
4. **NLP / cultural vectors.** Spotify crawls reviews/blogs into per-artist "top terms";
playlist-title NLP captures intent ("focus", "workout"). *Adds cultural context audio
can't see — lyrical themes, scenes, use-cases.*
5. **Session + context features.** Time of day, device, short-term intent (TikTok's
real-time infra exists because what you watched 30 seconds ago dominates). *Mostly a
rerank/short-horizon effect.*
6. **Editorial / human signals.** Deezer's arc is the cautionary tale: editor hand-picks
meant most albums never got exposed, so they replaced editorial preselection with
fully personalized ranking — keeping editors only for "unmissable" anchors.
*Editorial for anchors and quality floors, never the candidate pool.*
7. **Social signals.** Weak production evidence everywhere; skip for v1.

## 2. What the research frontier says

- **Freshness ≠ novelty.** YouTube Music's 2026 A/B tests (2607.23749) show new-release
freshness and deep-catalog novelty are *separate objectives* that must be budgeted
separately — and serving-time tweaks get neutralized by the learning loop, so
intervene at the scoring/architecture layer.
- **Exploration saturates.** Novelty pressure has diminishing, non-monotonic returns
that vary per user (2604.16419). The wild-card dial must be *adaptive*: weeks of
skipped adventurous picks → back off; hits → push harder.
- **Serendipity = relevance floor × unexpectedness.** No serendipity algorithm wins
consistently (2508.17571), so don't over-engineer one — instead use a chain-of-thought
LLM-as-judge anchored to the taste profile as a cheap pre-digest wild-card gate.
- **The write-up is half the algorithm.** Narrative transportation — being pulled into
a story world — is the strongest predictor of taste-broadening interest (2604.08385);
facts and metadata are weaker. The wild card converts on story, not specs.
- **Negatives are structural.** Skipped/disliked albums should be *hard negatives
pushed away* in the embedding space, not merely down-weighted — gains compound over
time (2409.07367). The feedback UI is the highest-leverage component.
- **Cold items via warm neighbors.** SwapRec (2609.00913): recommend fresh releases as
stand-ins for their most similar warm album — zero history required.
- **Use audio-text-aligned encoders, geometry direct.** CLAP-family encoders with
similarity computed on raw embedding geometry beat everything else for cold-start
retrieval; downstream training won't fix a bad encoder (2608.06928).
- **His reactions are the only honest evaluation.** No offline metric design is
uniformly valid (2607.25097). At 5 albums/week, the listener's listen-throughs are dense
ground truth — re-validate every dial against them.

## 3. long-play engine: proposed design

**Candidate generation (album-level, like Deezer's production system).** Build a
user–album interaction matrix from now-playing sampler logs + explicit chat
feedback (ADV-LP-07: Wesley's 2026-09-20 correction — his Spotify library is
NOT a reliable taste proxy, so Liked Songs / saves may serve as weak priors
at most and must never drive the taste vector); album embeddings from
playlist co-occurrence + audio-text encoder
geometry. New albums get *predicted* embeddings from metadata (artist, label, genre
tags) à la Deezer's CF-Cold-Start — refreshed as sampler data accrues. Album is the
recommendable unit, full stop.

**Scoring formula (per slot):**

`score = w_rel·REL + w_nov·NOV + w_fresh·FRESH + w_div·DIV + w_cult·CULT + w_ctx·CTX`

- **REL** — dot product of taste vector with album embedding (collaborative core).
- **NOV** — inverse familiarity: unplayed, low co-occurrence with his library.
- **FRESH** — release recency, budgeted separately from NOV per the YouTube finding.
- **DIV** — marginal contribution to the week's diversity (quality-diversity trade-off).
- **CULT** — cultural-discourse score: 33⅓ canon membership, year-end-list appearances,
review volume, RYM rating counts. His explicit ask, first-class signal.
- **CTX** — session fit: sampler-derived time-of-day patterns matched against
album energy/duration profiles. Full model in
`reference/ctx-session-model.md`: duration tiers derived from
`engine/tracklists/` by `bin/ctx_profiles.py`, energy as a human tag with a
fixed rubric (Spotify's audio-features endpoint is gone, so no programmatic
energy source exists), and a heuristic session-fit table flagged UNVALIDATED
until 3–4 weeks of per-album completion data calibrate it.

**Slot weights (starting point, tuned by feedback):**

| slot | REL | NOV | FRESH | DIV | CULT | CTX |
|---|---|---|---|---|---|---|
| anchor | 0.70 | 0.05 | 0.05 | 0.00 | 0.10 | 0.10 |
| adventurous ×3 | 0.40 | 0.25 | 0.10 | 0.10 | 0.10 | 0.05 |
| wild card | 0.25 (hard floor) | 0.35 | 0.05 | 0.10 | 0.20 | 0.05 |

The wild card passes an LLM-as-judge serendipity gate (chain-of-thought against the
taste profile) before it ships. One slot's policy stays fixed as a control; the
adventurous slots vary week to week — the digest is a longitudinal self-experiment.

**Feedback loop.** Played/loved → positive pull in embedding space; skipped/disliked →
hard negative pushed away. Wild-card reactions weighted 2× ("discomfort means more
meaningful feedback"). Weekly engagement state modulates the novelty budget up/down
(saturation tracking). The now-playing sampler (daily, 07:19/08:19/09:19/10:19/
15:19/16:19/17:19/19:19/21:19 PT) is
the implicit-feedback stream: play counts, album completion proxies, and the session
patterns feeding CTX.

**What we deliberately do differently from Spotify:**
- **Album granularity** as the recommendable unit — Deezer proves it works in
production; the industry is track-level by UX habit, not technical constraint.
- **CULT as a scorer**, not decoration — Spotify's cultural vectors are a similarity
input; ours directly boosts historically significant records.
- **Academic-lens write-ups** (moment → lineage → discourse then-vs-now → one
"listen for" cue) because narrative transportation is the conversion mechanism.
- **No popularity-bias problem to solve** — the audience is one person, so we can
down-weight global popularity freely (Pandora's deliberate inoculation, taken further).
- **Explicit exploration budget** (20% of the slate) instead of Spotify's hidden
epsilon-greedy — Wesley *wants* to see the wild card labeled as such.

## 4. Sources

Industry:
- Ciocca, "Spotify's Discover Weekly" (2017) — https://hackernoon.com/spotifys-discover-weekly-how-machine-learning-finds-your-new-music-19a41ab76efe
- Dieleman, "Recommending music on Spotify with deep learning" (2014) — https://sander.ai/2014/08/05/spotify-cnns.html
- McInerney et al., "Explore, Exploit, Explain" (Spotify, RecSys 2018) — https://research.atspotify.com/publications/explore-exploit-explain-personalizing-explainable-recommendations-with-bandits
- Feijer et al., "Calibrated Recommendations with Contextual Bandits" (Spotify, 2025) — https://research.atspotify.com/2025/9/calibrated-recommendations-with-contextual-bandits-on-spotify-homepage
- Briand et al., "Fostering Discoverability of New Releases on Deezer" (ECIR 2024) — http://arxiv.org/pdf/2401.02827
- Salha-Galvan et al., user cold start on Deezer (KDD 2021) — https://arxiv.org/abs/2106.03819
- Deezer, "Track Mix Generation using Transformers" (RecSys 2023) — https://arxiv.org/pdf/2307.03045
- IEEE Spectrum, Pandora Music Genome Project write-up — https://spectrum.ieee.org/amp/how-machine-learning-is-reinventing-the-way-we-discover-music-2650278118

arXiv (music recsys 2022–2026):
- 2607.23749 — novelty vs freshness, YouTube Music A/Bs — https://arxiv.org/abs/2607.23749
- 2604.16419 — exploration saturation per user — https://arxiv.org/abs/2604.16419
- 2508.05198 — sub-item popularity, accuracy-vs-novelty dial — https://arxiv.org/abs/2508.05198
- 2604.08385 — narrative transportation drives taste-broadening — https://arxiv.org/abs/2604.08385
- 2508.17571 — LLM-as-judge for serendipity evaluation — https://arxiv.org/abs/2508.17571
- 2507.17356 — ACT-R memory + audio for unheard-item resonance — https://arxiv.org/abs/2507.17356
- 2409.07367 — negative-feedback contrastive learning — https://arxiv.org/abs/2409.07367
- 2608.06928 — audio embedding model benchmark for recommendation — https://arxiv.org/abs/2608.06928
- 2609.00913 — SwapRec, warming cold items — https://arxiv.org/abs/2609.00913
- 2607.25097 — convergent validity of offline evaluation — https://arxiv.org/abs/2607.25097
