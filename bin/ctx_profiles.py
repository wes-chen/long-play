#!/usr/bin/env python3
"""L5: CTX session model — derive album duration profiles from tracklists.

Duration is the one CTX axis we compute: sum of
track duration_ms from engine/tracklists/*.json, binned into the tiers in
reference/ctx-session-model.md. The energy axis was removed (#28): it was
documented as a manual curator tag but no writer ever produced it, so the
schema no longer promises the field. Re-add the axis only together with a
real writer (e.g. a curated tagging pass) and a regression test that every
profile carries it.

Usage:
    python3 bin/ctx_profiles.py            # every syllabus album
    python3 bin/ctx_profiles.py --week 1   # one week's five albums

Prints JSON: [{"artist", "album", "slot", "minutes", "duration_tier",
"tracklist": bool}].
Unresolved albums appear with "minutes": null so gaps are visible, not
silent.

Also writes engine/ctx_profiles.json (profiles + the v0 session fit table
from reference/ctx-session-model.md) — the consumer contract for
sampler/rollup.py's per-album "session fit".
"""
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACKLIST_DIR = os.path.join(REPO, "engine", "tracklists")
WEEKS_JSON = os.path.join(REPO, "engine", "weeks.json")
CTX_JSON = os.path.join(REPO, "engine", "ctx_profiles.json")

# v0 matching table from reference/ctx-session-model.md: fit scores 0-2,
# session x duration_tier. (#28: the energy axis was removed — no writer
# ever produced it, so ENERGY_MODIFIERS is gone; profiles are
# duration-only. Re-add together with a real energy writer.)
SESSIONS = {
    "morning": [7, 8, 9, 10],
    "afternoon": [15, 16, 17],
    "evening": [19, 20, 21],
}
FIT_TABLE = {
    "morning": {"short": 2.0, "medium": 1.5, "long": 0.75, "epic": 0.25},
    "afternoon": {"short": 1.5, "medium": 2.0, "long": 1.0, "epic": 0.5},
    "evening": {"short": 1.0, "medium": 1.5, "long": 2.0, "epic": 1.75},
}


def fit(session, duration_tier_):
    """Fit score 0-2 for one (session, album) pair per the spec table.

    Duration-only (energy axis removed, #28). Clamp to [0, 2].
    """
    base = FIT_TABLE.get(session, {}).get(duration_tier_)
    if base is None:
        return None
    return round(min(2.0, max(0.0, base)), 2)


def norm(s):
    return re.sub(r"[^a-z0-9]+", "-", s.strip().lower()).strip("-")


def slug(artist, album):
    return f"{norm(artist)}--{norm(album)}"


def duration_tier(minutes):
    if minutes is None:
        return None
    if minutes < 40:
        return "short"
    if minutes < 60:
        return "medium"
    if minutes < 80:
        return "long"
    return "epic"


def load_tracklist(artist, album):
    """Exact slug match, then fuzzy containment match on album name."""
    path = os.path.join(TRACKLIST_DIR, slug(artist, album) + ".json")
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    na = norm(album)
    for fname in sorted(os.listdir(TRACKLIST_DIR)):
        if not fname.endswith(".json"):
            continue
        if not fname.startswith(norm(artist).split("-")[0] + "-"):
            continue
        try:
            with open(os.path.join(TRACKLIST_DIR, fname)) as f:
                tl = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if na in norm(tl.get("album", "")) or norm(tl.get("album", "")) in na:
            return tl
    return None


def minutes_of(tl):
    tracks = tl.get("tracks") or []
    total = sum(t.get("duration_ms", 0) for t in tracks)
    return round(total / 60000, 1) if total else None


def main():
    week_filter = None
    for a in sys.argv[1:]:
        if a == "--week" or a.startswith("--week="):
            week_filter = a.split("=", 1)[1] if "=" in a else sys.argv[
                sys.argv.index(a) + 1]
        elif week_filter is None and a.isdigit():
            week_filter = a
    week_filter = int(week_filter) if week_filter else None

    with open(WEEKS_JSON) as f:
        weeks = json.load(f)["weeks"]

    out = []
    for w in weeks:
        if week_filter and w.get("n") != week_filter:
            continue
        picks = [("anchor", w["anchor"])]
        picks += [("adventurous", a) for a in w.get("adventurous", [])]
        picks.append(("wild_card", w["wild_card"]))
        for slot, p in picks:
            tl = load_tracklist(p["artist"], p["album"])
            mins = minutes_of(tl) if tl else None
            out.append({
                "artist": p["artist"],
                "album": p["album"],
                "week": w.get("n"),
                "slot": slot,
                "minutes": mins,
                "duration_tier": duration_tier(mins),
                "tracklist": tl is not None,
            })
    print(json.dumps(out, indent=1))

    # L5 consumer contract: persist the profiles plus the matching table
    # so sampler/rollup.py (and the digest) can consume session fit without
    # re-deriving it. Written atomically; stdout above keeps the old shape.
    envelope = {
        "sessions": SESSIONS,
        "fit_table": FIT_TABLE,
        "profiles": out,
    }
    tmp = CTX_JSON + ".tmp"
    with open(tmp, "w") as f:
        json.dump(envelope, f, indent=1)
    os.replace(tmp, CTX_JSON)


if __name__ == "__main__":
    main()
