#!/usr/bin/env python3
"""M2: implicit-feedback taste vector.

Turns skip timing, completion, and replays (sampler data; >=85% sampled
progress = proxy, not ground truth) plus explicit chat feedback into a
per-genre taste vector steering future picks.

Signal weights (his standing rules):
  - Explicit chat reactions: full weight, wild-card reactions 2x
    (docs/feedback-schema.md).
  - Implicit sampler signals: completion proxies, replays, early skips —
    medium weight. Completion is a PROXY (max observed progress >= 85%),
    never treated as ground truth.
  - Spotify library saves: DE-WEIGHTED (0.1x weak prior; his 2026-09-20
    ruling: the library is not a reliable taste proxy). Only used when a
    library snapshot exists at the private path below; otherwise "pending".

Output: engine/taste-vector.json — {generated_at, dimensions {genre: score},
context_modifiers, prediction_calibration, sources, pending [...]}.

Before the course starts (no feedback yet), dimensions are empty and the
file carries pending: ["explicit feedback", "sampler rollups"].
"""
import glob
import json
import os
import re
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOAL = os.path.expanduser("~/workspace/goals/album-recommender-music-digest")
LOG = os.path.join(GOAL, "listening-log.md")
ROLLUPS = os.path.join(GOAL, "hidden_files", "sampler", "rollups")
CONTEXT_TAGS = os.path.join(GOAL, "hidden_files", "context-tags.jsonl")
LIB_SNAPSHOT = os.path.join(GOAL, "hidden_files", "library-snapshot.json")
PREDICTIONS = os.path.join(GOAL, "hidden_files", "predictions.json")
OUT = os.path.join(REPO, "engine", "taste-vector.json")

REACTION_SCORE = {"loved": 1.0, "played": 0.4, "skipped": -0.2, "bounced off": -1.0}
ROW_RE = re.compile(
    r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(anchor|adventurous|wild[- ]card)\s*\|\s*"
    r"(played|skipped|loved|bounced off)\b([^|]*)\|\s*(chat|sampler)\s*\|\s*([\d.]+)\s*\|\s*([\d-]+)"
    , re.IGNORECASE | re.MULTILINE)
LIBRARY_WEIGHT = 0.1  # his ruling: library is a weak prior, never a signal


def norm(s):
    return " ".join(s.strip().lower().split())


def load_tags():
    with open(os.path.join(REPO, "engine", "album_tags.json")) as f:
        return json.load(f)


def explicit_feedback(tags):
    """Returns (genre_scores, n_reactions)."""
    scores = defaultdict(float)
    weights = defaultdict(float)
    n = 0
    if not os.path.exists(LOG):
        return scores, weights, n
    with open(LOG) as f:
        text = f.read()
    for m in ROW_RE.finditer(text):
        week, album, artist, slot, reaction, note, source, weight, ts = m.groups()
        if source.lower() != "chat":
            continue  # sampler rows are implicit, never a reaction (schema rule)
        key = f"{norm(artist)}|{norm(album)}"
        tag = tags.get(key)
        if not tag:
            continue
        w = float(weight)
        s = REACTION_SCORE[reaction.lower()] * w
        scores[tag["genre"]] += s
        weights[tag["genre"]] += w
        n += 1
    return scores, weights, n


def implicit_signals(tags):
    """Sampler rollups -> per-genre implicit scores.

    Completion proxy: max observed progress >= 85% (NOT ground truth).
    Early skip: max progress < 30% -> negative. Replays add positive.
    """
    scores = defaultdict(float)
    weights = defaultdict(float)
    n_albums = 0
    pending_reasons = []
    files = sorted(glob.glob(os.path.join(ROLLUPS, "*.json")))
    if not files:
        return scores, weights, 0, ["no sampler rollups yet"]
    for path in files:
        try:
            with open(path) as f:
                roll = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        for row in roll.get("albums", []):
            name = row.get("name", "")
            # rollup album rows key on watchlist: "Artist — Album"
            parts = re.split(r"\s+[—–-]\s+", name, maxsplit=1)
            if len(parts) != 2:
                continue
            key = f"{norm(parts[0])}|{norm(parts[1])}"
            tag = tags.get(key)
            if not tag:
                continue
            tracks = row.get("tracks", 0) or 0
            completed = row.get("completed_tracks", 0) or 0
            max_prog = row.get("max_progress_pct", 0) or 0
            hits = row.get("hits", 0) or 0
            if tracks == 0:
                continue
            n_albums += 1
            # completion proxy -> positive; early skip -> negative; replays boost
            comp_ratio = completed / tracks
            s = comp_ratio * 0.8
            if max_prog < 30 and completed == 0:
                s -= 0.5  # bounced early
            if hits > tracks:
                s += 0.3  # replays
            w = 0.5  # implicit is half the voice of an explicit reaction
            scores[tag["genre"]] += s * w
            weights[tag["genre"]] += w
    return scores, weights, n_albums, pending_reasons


def context_modifiers():
    """M9: one-tap context tags -> per-context genre modifiers."""
    mods = {}
    if not os.path.exists(CONTEXT_TAGS):
        return mods, ["no context tags yet"]
    counts = defaultdict(lambda: defaultdict(int))
    with open(CONTEXT_TAGS) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            ctx, genre, reaction = e.get("context"), e.get("genre"), e.get("reaction")
            if ctx and genre:
                counts[ctx][genre] += REACTION_SCORE.get(reaction, 0)
    for ctx, genres in counts.items():
        mods[ctx] = dict(sorted(genres.items(), key=lambda kv: -kv[1]))
    return mods, []


def library_prior():
    """De-weighted 0.1x library prior — only when a snapshot exists."""
    if not os.path.exists(LIB_SNAPSHOT):
        return {}, ["library snapshot absent (de-weighted by rule; pending)"]
    return {}, ["library snapshot handling not yet implemented"]


BLEND_OVERLAP = os.path.join(GOAL, "hidden_files", "taste-blend-overlap.json")


def blend_affinity():
    """M8: artists appearing in both his listening and a blend source
    are a weak artist-affinity signal (0.05x)."""
    if not os.path.exists(BLEND_OVERLAP):
        return {}, ["no taste-blend overlap yet"]
    try:
        with open(BLEND_OVERLAP) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}, ["taste-blend overlap unreadable"]
    return {a: 0.05 for a in data.get("artists", [])}, []


def prediction_calibration():
    """M4: prediction accuracy as a calibration signal for vector confidence."""
    if not os.path.exists(PREDICTIONS):
        return None, ["no predictions yet"]
    try:
        with open(PREDICTIONS) as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None, ["predictions file unreadable"]
    scored = [w for w in data.get("weeks", {}).values() if w.get("accuracy") is not None]
    if not scored:
        return {"weeks_scored": 0}, ["no scored prediction weeks yet"]
    acc = sum(w["accuracy"] for w in scored) / len(scored)
    return {"weeks_scored": len(scored), "mean_accuracy": round(acc, 3)}, []


def main():
    tags = load_tags()
    pending = []

    e_scores, e_weights, n_exp = explicit_feedback(tags)
    if n_exp == 0:
        pending.append("explicit feedback (course has not started)")

    i_scores, i_weights, n_imp, imp_pending = implicit_signals(tags)
    pending.extend(imp_pending)

    ctx_mods, ctx_pending = context_modifiers()
    pending.extend(ctx_pending)

    lib_scores, lib_pending = library_prior()
    pending.extend(lib_pending)

    blend_scores, blend_pending = blend_affinity()
    pending.extend(blend_pending)

    calib, calib_pending = prediction_calibration()
    pending.extend(calib_pending)

    # blend: explicit full voice, implicit half, library 0.1x
    dims = defaultdict(float)
    total_w = defaultdict(float)
    for genre, s in e_scores.items():
        dims[genre] += s
        total_w[genre] += e_weights[genre]
    for genre, s in i_scores.items():
        dims[genre] += s
        total_w[genre] += i_weights[genre]
    for genre, s in lib_scores.items():
        dims[genre] += s * LIBRARY_WEIGHT
        total_w[genre] += LIBRARY_WEIGHT

    dimensions = {}
    for genre in dims:
        w = total_w[genre]
        dimensions[genre] = round(max(-1.0, min(1.0, dims[genre] / w)), 3) if w else 0.0

    out = {
        "generated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc).isoformat(),
        "version": 1,
        "dimensions": dict(sorted(dimensions.items(), key=lambda kv: -kv[1])),
        "artist_affinity": dict(sorted(blend_scores.items())),
        "context_modifiers": ctx_mods,
        "prediction_calibration": calib,
        "sources": {
            "explicit_reactions": n_exp,
            "implicit_album_signals": n_imp,
            "library": "de-weighted 0.1x weak prior (standing rule)",
            "wild_card_weight": "2.0x (standing rule)",
        },
        "pending": sorted(set(pending)),
        "notes": "Explicit chat reactions are ground truth. Sampler completion is a "
                 "proxy (>=85% max progress), not ground truth. Library saves are "
                 "weak priors at most — never steering signals.",
    }
    with open(OUT, "w") as f:
        json.dump(out, f, indent=1)
    print(json.dumps({
        "out": OUT,
        "dimensions": len(dimensions),
        "explicit_reactions": n_exp,
        "implicit_albums": n_imp,
        "pending": out["pending"],
    }, indent=1))


if __name__ == "__main__":
    main()
